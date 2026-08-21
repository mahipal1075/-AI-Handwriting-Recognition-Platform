"""
Stages 7, 8, 9 – Recognition (CPU-balanced: quality vs speed)

Key design decisions:
  • num_beams = 3 on CPU  (vs 1 greedy → big quality boost, ~2x slower but still fast)
  • early_stopping = False when num_beams=1 to suppress transformers warning
  • Each image is processed INDIVIDUALLY — no cross-image padding that distorts output
  • max_new_tokens = 64  (one line of handwriting never needs more)
  • No multi-pass retry on CPU (too slow); single pass is sufficient
  • Strong preprocessing: CLAHE + contrast stretch + sharpening + inversion detection

Expected time per page: 5-20 seconds depending on number of detected lines.
"""

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

from app.config import (
    HTR_MODEL_NAME, LOCAL_MODEL_DIR,
    BEAM_NUM_BEAMS, BEAM_MAX_NEW_TOKENS, BEAM_EARLY_STOPPING,
    TROCR_TARGET_H,
)

# ── Runtime constants ─────────────────────────────────────────────────────────
_device     = "cuda" if torch.cuda.is_available() else "cpu"
_IS_CPU     = _device == "cpu"

# 3 beams on CPU balances quality vs speed well (~3-4s per line)
# 5 beams on GPU is essentially free
_BEAMS      = 3 if _IS_CPU else BEAM_NUM_BEAMS
_MAX_TOKENS = 64 if _IS_CPU else BEAM_MAX_NEW_TOKENS
# early_stopping only valid when num_beams > 1
_EARLY_STOP = (BEAM_EARLY_STOPPING and _BEAMS > 1)

# ── Global model state ────────────────────────────────────────────────────────
_processor: Optional[TrOCRProcessor]            = None
_model:     Optional[VisionEncoderDecoderModel] = None


# ── Model loading ─────────────────────────────────────────────────────────────

def load_model() -> Tuple[TrOCRProcessor, VisionEncoderDecoderModel]:
    """Lazy-load TrOCR. Saves to LOCAL_MODEL_DIR after first download."""
    global _processor, _model
    if _model is not None and _processor is not None:
        return _processor, _model

    load_path = LOCAL_MODEL_DIR if os.path.isdir(LOCAL_MODEL_DIR) else HTR_MODEL_NAME
    print(f"[Model] Loading '{HTR_MODEL_NAME}' from {'local cache' if load_path == LOCAL_MODEL_DIR else 'HuggingFace Hub'}...")

    _processor = TrOCRProcessor.from_pretrained(load_path)
    _model     = VisionEncoderDecoderModel.from_pretrained(load_path).to(_device)
    _model.eval()

    if not os.path.isdir(LOCAL_MODEL_DIR):
        print(f"[Model] Caching to '{LOCAL_MODEL_DIR}'...")
        _processor.save_pretrained(LOCAL_MODEL_DIR)
        _model.save_pretrained(LOCAL_MODEL_DIR)

    print(f"[Model] Ready on {_device.upper()} | beams={_BEAMS} | max_tokens={_MAX_TOKENS}")
    return _processor, _model


# ── Stage 7: Per-line preprocessing ──────────────────────────────────────────

def prepare_patch(cropped_gray: np.ndarray) -> Optional[Image.Image]:
    """
    Prepare a single grayscale line crop for TrOCR.
    Returns PIL RGB image or None if the crop is invalid/blank.
    """
    h, w = cropped_gray.shape[:2]
    if h < 8 or w < 8:
        return None

    # Blank check — skip crops with almost no ink
    _, thresh_check = cv2.threshold(
        cropped_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    if np.sum(thresh_check > 0) < 30:
        return None

    img = cropped_gray.copy()

    # 1. Contrast stretch to full [0,255] range
    lo = int(np.percentile(img, 2))
    hi = int(np.percentile(img, 98))
    if hi - lo > 10:
        img = np.clip(
            (img.astype(np.float32) - lo) / (hi - lo) * 255.0, 0, 255
        ).astype(np.uint8)

    # 2. CLAHE for local contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    img   = clahe.apply(img)

    # 3. Unsharp mask for stroke sharpening
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=1.5)
    img     = np.clip(cv2.addWeighted(img, 1.8, blurred, -0.8, 0), 0, 255).astype(np.uint8)

    # 4. Invert if background is dark (TrOCR expects white bg / dark text)
    top_band = img[:max(1, h // 5), :]
    if int(np.median(top_band)) < 128:
        img = cv2.bitwise_not(img)

    # 5. White padding
    img = cv2.copyMakeBorder(img, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)

    # 6. Resize to TrOCR target height (keeping aspect ratio)
    ph, pw = img.shape[:2]
    if ph != TROCR_TARGET_H:
        scale  = TROCR_TARGET_H / ph
        new_pw = max(1, int(pw * scale))
        img    = cv2.resize(img, (new_pw, TROCR_TARGET_H), interpolation=cv2.INTER_LANCZOS4)

    # 7. Grayscale → RGB PIL
    rgb = np.stack([img, img, img], axis=-1)
    return Image.fromarray(rgb.astype(np.uint8))


# ── Stage 8: Single-image TrOCR inference ────────────────────────────────────

def _run_trocr(pil_img: Image.Image) -> Tuple[str, float]:
    """Run TrOCR on one PIL image. Returns (text, confidence)."""
    proc, mdl = load_model()
    pixel_values = proc(images=pil_img, return_tensors="pt").pixel_values.to(_device)

    with torch.no_grad():
        gen_kwargs = dict(
            return_dict_in_generate=True,
            output_scores=True,
            num_beams=_BEAMS,
            max_new_tokens=_MAX_TOKENS,
        )
        if _BEAMS > 1:
            gen_kwargs["early_stopping"] = _EARLY_STOP

        outputs = mdl.generate(pixel_values, **gen_kwargs)

    text = proc.batch_decode(outputs.sequences, skip_special_tokens=True)[0].strip()
    conf = _sequence_confidence(outputs.sequences, outputs.scores)
    return text, conf


def _sequence_confidence(gen_ids: torch.Tensor, scores) -> float:
    """Average token probability for the generated sequence."""
    if not scores:
        return 0.85
    probs = []
    for i, logits in enumerate(scores):
        if i + 1 >= gen_ids.shape[1]:
            break
        p      = torch.softmax(logits, dim=-1)
        tok_id = gen_ids[0][i + 1].item()
        if tok_id < p.shape[-1]:
            probs.append(float(p[0][tok_id].item()))
    return float(np.mean(probs)) if probs else 0.85


# ── Stage 9: Public API ───────────────────────────────────────────────────────

def transcribe_patch(cropped_gray: np.ndarray) -> Tuple[str, float]:
    """
    Stage 9: Transcribe a single line crop.
    Single-pass (no retry on CPU — already 3x faster than original).
    """
    pil = prepare_patch(cropped_gray)
    if pil is None:
        return "", 0.0
    return _run_trocr(pil)


def transcribe_batch(pil_images: List[Image.Image]) -> List[Tuple[str, float]]:
    """
    Process a list of PIL images individually (NOT padded-batch).
    Each image is run through TrOCR separately to avoid padding artifacts
    that degrade recognition quality.
    Returns list of (text, confidence) tuples.
    """
    return [_run_trocr(img) for img in pil_images]