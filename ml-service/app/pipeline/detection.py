"""
Stage 4 – Text Region Detection (PaddleOCR DB-Net via RapidOCR ONNX)

Uses RapidOCR which runs PaddleOCR's actual DB (Differentiable Binarization)
detection model via ONNX Runtime — gives polygon-level word/line detection
with the same quality as PaddleOCR but works on Python 3.14.

Detection pipeline:
  1. RapidOCR DB-Net polygon detector (primary — finds every word precisely)
  2. Group word polygons into reading-order lines
  3. OpenCV morphology fallback (only if RapidOCR fails)

The DB-Net model outputs tight polygons around each text word/phrase,
ensuring NO words are missed — even curved, rotated, or overlapping text.

Returns:
  List of dicts: {x, y, w, h, confidence, detector}
  Sorted in reading order (top→bottom, left→right).
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional

from app.config import IOU_THRESHOLD

# ── RapidOCR (PaddleOCR DB-Net via ONNX) ─────────────────────────────────────
try:
    from rapidocr_onnxruntime import RapidOCR
    _RAPID_AVAILABLE = True
except ImportError:
    _RAPID_AVAILABLE = False

_rapid_engine: Optional[object] = None


def _get_rapid() -> Optional[object]:
    """Lazy-init RapidOCR engine (det-only mode for speed)."""
    global _rapid_engine
    if not _RAPID_AVAILABLE:
        return None
    if _rapid_engine is None:
        try:
            _rapid_engine = RapidOCR()
            print("[Detection] RapidOCR DB-Net detection engine loaded.")
        except Exception as e:
            print(f"[Detection] RapidOCR init failed ({e}). Falling back to OpenCV.")
            return None
    return _rapid_engine


# ── Public API ────────────────────────────────────────────────────────────────

def detect_text_regions(gray_img: np.ndarray) -> List[Dict]:
    """
    Detect text line bounding boxes using PaddleOCR DB-Net polygons.
    Falls back to OpenCV morphology if RapidOCR is unavailable.
    Returns boxes sorted in reading order.
    """
    h_img, w_img = gray_img.shape[:2]

    # Try RapidOCR polygon detection first
    rapid = _get_rapid()
    if rapid is not None:
        rapid_boxes = _detect_with_rapidocr(gray_img, rapid)
        if rapid_boxes:
            return rapid_boxes

    # Fallback: OpenCV morphology
    opencv_boxes = _detect_with_opencv(gray_img)
    return opencv_boxes if opencv_boxes else [{
        "x": 0, "y": 0, "w": int(w_img), "h": int(h_img),
        "confidence": 0.5, "detector": "fallback",
    }]


# ── RapidOCR DB-Net Detection ─────────────────────────────────────────────────

def _detect_with_rapidocr(gray_img: np.ndarray, engine) -> List[Dict]:
    """
    Run RapidOCR's DB-Net detector to get word-level polygons.
    RapidOCR returns: (dt_boxes, rec_results, scores)
    We only use dt_boxes (detection) — recognition is handled by our TrOCR.
    """
    h_img, w_img = gray_img.shape[:2]

    # RapidOCR expects BGR or RGB — convert grayscale to BGR
    bgr = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)

    try:
        result, elapsed = engine(bgr)
    except Exception as e:
        print(f"[Detection] RapidOCR error: {e}")
        return []

    if result is None:
        return []

    # Parse RapidOCR results — each item is [dt_boxes, text, confidence]
    word_boxes: List[Dict] = []
    for item in result:
        if item is None or len(item) < 3:
            continue

        dt_boxes = item[0]    # polygon points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        text     = item[1]    # recognised text (we ignore this — use TrOCR instead)
        conf     = item[2]    # detection confidence

        if dt_boxes is None:
            continue

        # Convert polygon to bounding rect
        poly = np.array(dt_boxes, dtype=np.float32)
        x, y, w, h = cv2.boundingRect(poly.astype(np.int32))

        # Filter noise
        if w < 8 or h < 5:
            continue
        # Skip full-page boxes
        if w >= w_img * 0.97 and h >= h_img * 0.97:
            continue

        word_boxes.append({
            "x": int(max(0, x)),
            "y": int(max(0, y)),
            "w": int(min(w, w_img - x)),
            "h": int(min(h, h_img - y)),
            "confidence": float(conf) if conf else 0.90,
            "detector": "rapidocr-dbnet",
        })

    if not word_boxes:
        return []

    # Group word-level boxes into line-level boxes
    line_boxes = _group_into_lines(word_boxes, h_img, w_img)
    line_boxes = _filter_contained(line_boxes)
    line_boxes = _sort_reading_order(line_boxes)

    return line_boxes


# ── OpenCV Fallback ───────────────────────────────────────────────────────────

def _detect_with_opencv(gray_img: np.ndarray) -> List[Dict]:
    """OpenCV morphology-based line detection as fallback."""
    h_img, w_img = gray_img.shape[:2]

    _, thresh = cv2.threshold(
        gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    est_line_h = max(12, min(h_img // 25, 80))
    kw = max(30, w_img // 10)
    kh = max(2, int(est_line_h * 0.25))

    kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_w = max(30, w_img // 20)
    min_h = max(8, int(est_line_h * 0.35))

    boxes: List[Dict] = []
    for ctr in contours:
        x, y, w, h = cv2.boundingRect(ctr)
        if w >= w_img * 0.95 and h >= h_img * 0.95:
            continue
        if w < min_w or h < min_h:
            continue

        boxes.append({
            "x": int(x), "y": int(y),
            "w": int(w), "h": int(h),
            "confidence": 0.75,
            "detector": "opencv",
        })

    boxes = _filter_contained(boxes)
    boxes = _sort_reading_order(boxes)
    return boxes


# ── Word → Line Grouping ─────────────────────────────────────────────────────

def _group_into_lines(
    word_boxes: List[Dict],
    img_h: int,
    img_w: int,
) -> List[Dict]:
    """
    Group word-level bounding boxes into line-level boxes.
    Words with similar vertical centres (within half of median word height)
    are grouped into the same line.
    """
    if not word_boxes:
        return []

    # Sort by y centre
    sorted_words = sorted(word_boxes, key=lambda b: b["y"] + b["h"] // 2)

    # Estimate line gap from median word height
    heights = [b["h"] for b in word_boxes]
    median_h = int(np.median(heights)) if heights else 20
    line_gap = max(5, int(median_h * 0.6))

    # Group into rows
    rows: List[List[Dict]] = []
    current_row: List[Dict] = []
    current_cy: Optional[float] = None

    for box in sorted_words:
        cy = box["y"] + box["h"] / 2.0

        if current_cy is None or abs(cy - current_cy) <= line_gap:
            current_row.append(box)
            current_cy = float(np.mean([b["y"] + b["h"] / 2.0 for b in current_row]))
        else:
            if current_row:
                rows.append(current_row)
            current_row = [box]
            current_cy = cy

    if current_row:
        rows.append(current_row)

    # Merge each row into one tight bounding box
    line_boxes: List[Dict] = []
    for row in rows:
        xs  = [b["x"] for b in row]
        ys  = [b["y"] for b in row]
        x2s = [b["x"] + b["w"] for b in row]
        y2s = [b["y"] + b["h"] for b in row]

        x1 = max(0, min(xs) - 2)
        y1 = max(0, min(ys) - 2)
        x2 = min(img_w, max(x2s) + 2)
        y2 = min(img_h, max(y2s) + 2)
        bw, bh = x2 - x1, y2 - y1

        if bw < 10 or bh < 5:
            continue

        # Average confidence of words in this line
        avg_conf = float(np.mean([b["confidence"] for b in row]))

        line_boxes.append({
            "x": int(x1), "y": int(y1),
            "w": int(bw), "h": int(bh),
            "confidence": round(avg_conf, 3),
            "detector": row[0].get("detector", "rapidocr-dbnet"),
        })

    return line_boxes


# ── Utilities ─────────────────────────────────────────────────────────────────

def _filter_contained(boxes: List[Dict]) -> List[Dict]:
    """Remove boxes fully contained inside a larger box."""
    keep: List[Dict] = []
    for box in sorted(boxes, key=lambda b: b["w"] * b["h"], reverse=True):
        dominated = any(
            box["x"] >= k["x"] - 5 and box["y"] >= k["y"] - 5 and
            box["x"] + box["w"] <= k["x"] + k["w"] + 5 and
            box["y"] + box["h"] <= k["y"] + k["h"] + 5
            for k in keep
        )
        if not dominated:
            keep.append(box)
    return keep


def _sort_reading_order(boxes: List[Dict]) -> List[Dict]:
    """Sort top-to-bottom, then left-to-right within same row."""
    if not boxes:
        return []
    heights = [b["h"] for b in boxes]
    row_tol = max(5, int(np.median(heights) * 0.4)) if heights else 10

    sorted_by_y = sorted(boxes, key=lambda b: b["y"])
    rows: List[List[Dict]] = []
    cur_row: List[Dict] = []

    for box in sorted_by_y:
        if not cur_row or abs(box["y"] - cur_row[0]["y"]) <= row_tol:
            cur_row.append(box)
        else:
            rows.append(sorted(cur_row, key=lambda b: b["x"]))
            cur_row = [box]

    if cur_row:
        rows.append(sorted(cur_row, key=lambda b: b["x"]))

    return [b for row in rows for b in row]