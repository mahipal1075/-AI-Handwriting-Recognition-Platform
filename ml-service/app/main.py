"""
Stage 12 – OCR Pipeline Orchestrator

Wires all 12 stages together and exposes the FastAPI endpoint.

Pipeline per image:
  Stage 1  Quality Assessment        ← inside preprocess_image / preprocess_cv2_image
  Stage 2  Adaptive Preprocessing    ← inside preprocess_image / preprocess_cv2_image
  Stage 3  Page Layout Analysis      ← analyze_layout()
  Stage 4  Text Region Detection     ← detect_text_regions()
  Stage 5  Region Optimization       ← optimize_region()
  Stage 6  Line Segmentation         ← segment_lines()
  Stage 7  Recognition Preprocessing ← prepare_patch()  (inside transcribe_patch)
  Stage 8  TrOCR Large Recognition   ← _run_trocr()      (inside transcribe_patch)
  Stage 9  Confidence Retry          ← transcribe_patch()
  Stage 10 Error Correction          ← correct_text()
  Stage 11 Text Reconstruction       ← reconstruct_text()
  Stage 12 Structured JSON output    ← this file

Response shape (backward-compatible + extended):
{
  "extractedText":  str,          ← backward compat
  "confidence":     float,        ← backward compat
  "modelUsed":      str,          ← backward compat
  "processingMs":   int,          ← backward compat
  "annotations":    [...],        ← backward compat
  "quality":        {...},        ← NEW
  "layout":         {...},        ← NEW
  "lines":          [...],        ← NEW (per-line structured output)
  "detector":       str           ← NEW
}
"""

import time
import os
from typing import Optional, List, Dict, Any

import cv2
import numpy as np
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware


def _sanitize(obj: Any) -> Any:
    """
    Recursively convert numpy scalars / booleans to Python-native types
    so FastAPI / Pydantic can serialize the response without errors.
    """
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

from app.pipeline.preprocessing      import preprocess_image, preprocess_cv2_image
from app.pipeline.layout_analysis    import analyze_layout
from app.pipeline.detection          import detect_text_regions
from app.pipeline.region_optimizer   import optimize_region
from app.pipeline.line_segmentation  import segment_lines
from app.pipeline.recognition        import transcribe_patch, transcribe_batch, prepare_patch, load_model
from app.pipeline.postprocessing     import correct_text, correct_spelling
from app.pipeline.text_reconstruction import reconstruct_text
from app.config                      import HTR_MODEL_NAME

app = FastAPI(title="AI Handwriting Recognition Platform — ML Service v2.0")

@app.on_event("startup")
def startup_event():
    print("[Startup] Pre-loading TrOCR model into memory...")
    try:
        load_model()
        print("[Startup] TrOCR model pre-loaded successfully.")
    except Exception as e:
        print(f"[Startup Warning] Failed to pre-load model: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INTERNAL_KEY = os.environ.get(
    "ML_SERVICE_KEY", "handwriting_platform_internal_secret_key"
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def _verify_auth(x_service_key: Optional[str]) -> None:
    if x_service_key != INTERNAL_KEY:
        raise HTTPException(status_code=401, detail="Invalid service authorization key.")


# ── Confidence highlight colour ───────────────────────────────────────────────

def _highlight(conf: float) -> str:
    if conf < 0.60:
        return "red"
    if conf < 0.90:
        return "amber"
    return "green"


# Max regions & lines to process per page (prevents runaway CPU usage)
_MAX_REGIONS = 20
_MAX_LINES   = 30


# ── Per-page OCR pipeline (Stages 3-11, batched) ─────────────────────────────

def _run_pipeline_on_gray(
    gray: np.ndarray,
    quality_info: Dict[str, Any],
    line_records: List[Dict],
    annotations: List[Dict],
    page: Optional[int] = None,
) -> None:
    """
    Execute Stages 3–11 on a single preprocessed grayscale image.
    Uses BATCHED TrOCR inference — collects all line crops first, then runs
    the model once per page instead of once per line.

    Appends recognised line records to `line_records` and annotation dicts
    to `annotations`. Both lists are modified in-place.
    """
    # ── Stage 3: Layout analysis ─────────────────────────────────────────────
    try:
        _layout = analyze_layout(gray)
    except Exception:
        _layout = {}

    # ── Stage 4: Text region detection ───────────────────────────────────────
    bboxes = detect_text_regions(gray)
    if not bboxes:
        bboxes = [{
            "x": 0, "y": 0,
            "w": gray.shape[1], "h": gray.shape[0],
            "confidence": 0.5, "detector": "fallback",
        }]

    # Cap number of regions to avoid runaway processing on dense pages
    bboxes = bboxes[:_MAX_REGIONS]

    # ── Stages 5 & 6: Collect all line crops + metadata ──────────────────────
    all_pil_images   = []
    all_line_meta    = []  # (bbox_dict, original_bbox_dict)

    for bbox in bboxes:
        x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]

        # Stage 5: Region optimization
        try:
            optimized_crop = optimize_region(gray, bbox)
        except Exception:
            optimized_crop = gray[y:y + h, x:x + w].copy()

        if optimized_crop.size == 0:
            continue

        # Stage 6: Line segmentation
        try:
            line_crops = segment_lines(optimized_crop)
        except Exception:
            line_crops = [optimized_crop]

        for line_crop in line_crops:
            if line_crop.size == 0:
                continue
            if len(all_pil_images) >= _MAX_LINES:
                break

            # Stage 7: Preprocessing → PIL image
            try:
                pil = prepare_patch(line_crop)
            except Exception:
                pil = None

            if pil is not None:
                all_pil_images.append(pil)
                all_line_meta.append({"x": x, "y": y, "w": w, "h": h})

        if len(all_pil_images) >= _MAX_LINES:
            break

    if not all_pil_images:
        return

    # ── Stage 8: Batched TrOCR inference (ONE model call for whole page) ─────
    try:
        batch_results = transcribe_batch(all_pil_images)
    except Exception as exc:
        print(f"[Pipeline] transcribe_batch error: {exc}")
        return

    # ── Stages 9 & 10: Assemble results, error correction ────────────────────
    for i, (line_text, line_conf) in enumerate(batch_results):
        if not line_text.strip():
            continue

        record_bbox = all_line_meta[i]

        # Stage 10: Error correction
        corrected = correct_text(line_text)

        record: Dict[str, Any] = {
            "text":       corrected,
            "confidence": line_conf,
            "bbox":       record_bbox,
            "raw_text":   line_text,
        }
        if page is not None:
            record["page"] = page

        line_records.append(record)

        # Backward-compat annotation
        ann: Dict[str, Any] = {
            "bboxCoords":     record_bbox,
            "correctedText":  corrected,
            "highlightColor": _highlight(line_conf),
        }
        if page is not None:
            ann["page"] = page
        annotations.append(ann)



# ── Root / Health endpoints ───────────────────────────────────────────────────

@app.get("/")
def root() -> Dict[str, Any]:
    from app.config import HTR_MODEL_NAME
    return {
        "name":    "AI Handwriting Recognition Platform – ML Service",
        "version": "2.0.0",
        "status":  "UP",
        "model":   HTR_MODEL_NAME,
        "device":  "cuda" if __import__("torch").cuda.is_available() else "cpu",
        "endpoints": {
            "health":      "GET  /health",
            "ocr_process": "POST /ocr/process  (multipart/form-data, X-Service-Key header)",
        },
    }

@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "UP", "service": "Python FastAPI ML Service v2.0"}


# ── OCR endpoint ──────────────────────────────────────────────────────────────

@app.post("/ocr/process")
async def process_ocr(
    file: UploadFile = File(...),
    x_service_key: Optional[str] = Header(None),
) -> Dict[str, Any]:
    _verify_auth(x_service_key)
    start_time = time.time()

    try:
        file_bytes = await file.read()

        line_records: List[Dict] = []
        annotations:  List[Dict] = []
        quality_dict: Dict       = {}
        layout_dict:  Dict       = {}

        # ════════════════════════════════════════════════════════════════════
        # PDF path
        # ════════════════════════════════════════════════════════════════════
        if file_bytes.startswith(b'%PDF'):
            import fitz  # PyMuPDF

            doc = fitz.open(stream=file_bytes, filetype="pdf")

            # Check for selectable (digital) text first
            pdf_text_parts = []
            for pg in doc:
                txt = pg.get_text()
                if txt and len(txt.strip()) > 10:
                    pdf_text_parts.append(txt)

            if pdf_text_parts:
                full_text = "\n".join(pdf_text_parts)
                lines_out = [l.strip() for l in full_text.split("\n") if l.strip()]
                anns      = [
                    {"bboxCoords": {"x": 0, "y": 0, "w": 0, "h": 0},
                     "correctedText": l, "highlightColor": "green"}
                    for l in lines_out
                ]
                line_recs = [
                    {"text": l, "confidence": 1.0,
                     "bbox": {"x": 0, "y": 0, "w": 0, "h": 0}}
                    for l in lines_out
                ]
                return _build_response(
                    line_records=line_recs,
                    annotations=anns,
                    quality_dict={"score": 1.0, "classification": "Excellent"},
                    layout_dict={},
                    model_used="Digital PDF Text Extractor",
                    processing_ms=int((time.time() - start_time) * 1000),
                )

            # Scanned / handwritten PDF — OCR each page
            for page_num, pg in enumerate(doc):
                pix = pg.get_pixmap(dpi=200)
                img_data = np.frombuffer(
                    pix.samples, dtype=np.uint8
                ).reshape((pix.height, pix.width, pix.n))

                img_bgr = (
                    cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
                    if pix.n == 4
                    else cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
                )

                # Stages 1 & 2
                gray, quality = preprocess_cv2_image(img_bgr)

                if page_num == 0:
                    quality_dict = {
                        "score":            round(quality.score, 4),
                        "classification":   quality.classification,
                        "blur_score":       round(quality.blur_score, 2),
                        "brightness":       round(quality.brightness, 2),
                        "contrast":         round(quality.contrast, 2),
                        "noise_level":      round(quality.noise_level, 2),
                        "shadow_detected":  quality.shadow_detected,
                        "skew_angle":       round(quality.skew_angle, 2),
                        "dpi_estimate":     round(quality.dpi_estimate, 1),
                    }

                # Stages 3–11
                _run_pipeline_on_gray(
                    gray, quality_dict, line_records, annotations,
                    page=page_num + 1
                )

        # ════════════════════════════════════════════════════════════════════
        # Image path (JPG, PNG, BMP, TIFF, WebP, …)
        # ════════════════════════════════════════════════════════════════════
        else:
            # Stages 1 & 2
            gray, quality = preprocess_image(file_bytes)

            quality_dict = {
                "score":           round(quality.score, 4),
                "classification":  quality.classification,
                "blur_score":      round(quality.blur_score, 2),
                "brightness":      round(quality.brightness, 2),
                "contrast":        round(quality.contrast, 2),
                "noise_level":     round(quality.noise_level, 2),
                "shadow_detected": quality.shadow_detected,
                "skew_angle":      round(quality.skew_angle, 2),
                "dpi_estimate":    round(quality.dpi_estimate, 1),
            }

            # Stage 3
            try:
                layout_dict = analyze_layout(gray)
            except Exception:
                layout_dict = {}

            # Stages 4–11
            _run_pipeline_on_gray(gray, quality_dict, line_records, annotations)

        # ════════════════════════════════════════════════════════════════════
        # Nothing recognised
        # ════════════════════════════════════════════════════════════════════
        if not line_records:
            return _sanitize({
                "extractedText":  "",
                "confidence":     0.0,
                "modelUsed":      HTR_MODEL_NAME,
                "processingMs":   int((time.time() - start_time) * 1000),
                "annotations":    [],
                "quality":        quality_dict,
                "layout":         layout_dict,
                "lines":          [],
                "detector":       "opencv",
                "warning": (
                    "No text regions were detected. "
                    "Try a clearer image with higher contrast between ink and background."
                ),
            })

        # ════════════════════════════════════════════════════════════════════
        # Stage 11: Text Reconstruction
        # ════════════════════════════════════════════════════════════════════
        full_text = reconstruct_text(line_records)

        # Fallback: simple join if reconstruction returns empty
        if not full_text.strip():
            full_text = "\n".join(r["text"] for r in line_records)

        overall_confidence = float(np.mean([r["confidence"] for r in line_records]))

        # ════════════════════════════════════════════════════════════════════
        # Stage 12: Build structured JSON response
        # ════════════════════════════════════════════════════════════════════
        return _build_response(
            line_records=line_records,
            annotations=annotations,
            quality_dict=quality_dict,
            layout_dict=layout_dict,
            model_used=HTR_MODEL_NAME,
            processing_ms=int((time.time() - start_time) * 1000),
            full_text=full_text,
            overall_confidence=overall_confidence,
        )

    except Exception as exc:
        print(f"[ERROR] process_ocr: {exc}")
        raise HTTPException(status_code=500, detail=f"Inference failure: {str(exc)}")


def _build_response(
    line_records:       List[Dict],
    annotations:        List[Dict],
    quality_dict:       Dict,
    layout_dict:        Dict,
    model_used:         str,
    processing_ms:      int,
    full_text:          str = "",
    overall_confidence: float = 1.0,
) -> Dict[str, Any]:
    """Assemble the final Stage 12 structured JSON response."""

    if not full_text:
        full_text = "\n".join(r.get("text", "") for r in line_records)
    if overall_confidence == 1.0 and line_records:
        confs = [r.get("confidence", 1.0) for r in line_records]
        overall_confidence = float(np.mean(confs)) if confs else 1.0

    # Per-line structured output
    lines_out = [
        {
            "text":       r.get("text", ""),
            "confidence": round(r.get("confidence", 0.0), 4),
            "bbox":       r.get("bbox", {}),
            **({"page": r["page"]} if "page" in r else {}),
        }
        for r in line_records
    ]

    # Determine which detector was used (report dominant)
    response = {
        # ── Backward-compatible fields ────────────────────────────────────
        "extractedText":  full_text,
        "confidence":     round(overall_confidence, 4),
        "modelUsed":      model_used,
        "processingMs":   processing_ms,
        "annotations":    annotations,
        # ── New Stage 12 fields ───────────────────────────────────────────
        "quality": quality_dict,
        "layout":  layout_dict,
        "lines":   lines_out,
        "processing": {
            "model":    model_used,
            "detector": "paddleocr+opencv" if "paddleocr" in str(annotations) else "opencv",
        },
    }
    # Sanitize all numpy types before FastAPI/Pydantic serializes the response
    return _sanitize(response)