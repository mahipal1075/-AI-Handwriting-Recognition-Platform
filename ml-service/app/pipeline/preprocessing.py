"""
Stage 2 – Adaptive Image Preprocessing

The preprocessing pipeline is fully parameter-driven by the QualityResult from Stage 1.
No fixed kernel sizes — everything adapts to image resolution, noise level, etc.

Pipeline:
  RGB conversion → Grayscale → Adaptive Resize → Gamma Correction →
  Shadow Removal → CLAHE → Illumination Normalization →
  Bilateral / Gaussian Denoising → Global Deskew → Perspective Correction →
  Output clean grayscale image

Returns (clean_gray: np.ndarray, quality: QualityResult)
"""

import cv2
import numpy as np
from typing import Tuple

from app.pipeline.quality_assessment import QualityResult, assess_quality


def preprocess_image(image_bytes: bytes) -> Tuple[np.ndarray, QualityResult]:
    """
    Decode image bytes, run Stage 1 IQA, then the full adaptive preprocessing pipeline.
    Returns (clean_grayscale_image, quality_result).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes.")
    return preprocess_cv2_image(img)


def preprocess_cv2_image(img: np.ndarray) -> Tuple[np.ndarray, QualityResult]:
    """
    Full adaptive preprocessing pipeline on a BGR OpenCV image.
    Returns (clean_grayscale_image, quality_result).
    """
    # ── Stage 1: assess quality ──────────────────────────────────────────────
    quality = assess_quality(img)
    params  = quality.params

    # ── 1. Convert BGR → RGB → Grayscale ────────────────────────────────────
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ── 2. Adaptive Resize ───────────────────────────────────────────────────
    TARGET_H = params.get("working_height", 1600)
    h, w = gray.shape[:2]
    if h > TARGET_H:
        scale = TARGET_H / h
        gray  = cv2.resize(gray, (int(w * scale), TARGET_H), interpolation=cv2.INTER_AREA)
        img   = cv2.resize(img,  (int(w * scale), TARGET_H), interpolation=cv2.INTER_AREA)

    # ── 3. Gamma Correction ──────────────────────────────────────────────────
    gamma = params.get("gamma", 1.0)
    if gamma != 1.0:
        gray = _apply_gamma(gray, gamma)

    # ── 4. Shadow Removal ────────────────────────────────────────────────────
    if params.get("remove_shadow", False):
        gray = _remove_shadow(gray)

    # ── 5. CLAHE contrast enhancement ────────────────────────────────────────
    clahe = cv2.createCLAHE(
        clipLimit=params.get("clahe_clip", 2.0),
        tileGridSize=params.get("clahe_tile", (8, 8))
    )
    gray = clahe.apply(gray)

    # ── 6. Illumination Normalization ────────────────────────────────────────
    gray = _normalize_illumination(gray)

    # ── 7. Denoising ─────────────────────────────────────────────────────────
    denoise = params.get("denoise_method", "gaussian")
    if denoise == "bilateral":
        d     = params.get("bilateral_d",     9)
        sigma = params.get("bilateral_sigma", 75)
        gray  = cv2.bilateralFilter(gray, d, sigma, sigma)
    else:
        k    = params.get("gaussian_k", 3)
        gray = cv2.GaussianBlur(gray, (k, k), 0)

    # ── 8. Global Deskew ─────────────────────────────────────────────────────
    if params.get("deskew", True):
        gray = deskew(gray)

    # ── 9. Perspective Correction ─────────────────────────────────────────────
    if params.get("correct_perspective", False):
        gray = _correct_perspective(gray)

    return gray, quality


# ── Helper functions ──────────────────────────────────────────────────────────

def _apply_gamma(gray: np.ndarray, gamma: float) -> np.ndarray:
    """Apply gamma correction via a lookup table (fast, no per-pixel ops)."""
    inv_gamma = 1.0 / gamma
    table = np.array(
        [((i / 255.0) ** inv_gamma) * 255 for i in range(256)],
        dtype=np.uint8
    )
    return cv2.LUT(gray, table)


def _remove_shadow(gray: np.ndarray) -> np.ndarray:
    """
    Remove illumination gradients / shadows via morphological background estimation.
    A large-kernel dilation estimates the smooth background; dividing removes it.
    """
    h, w   = gray.shape[:2]
    ksize  = max(31, (min(h, w) // 10) | 1)   # must be odd
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    bg     = cv2.morphologyEx(gray, cv2.MORPH_DILATE, kernel)

    gray_f = gray.astype(np.float32)
    bg_f   = bg.astype(np.float32)
    result = np.clip((gray_f / (bg_f + 1e-6)) * 255.0, 0, 255)
    return result.astype(np.uint8)


def _normalize_illumination(gray: np.ndarray) -> np.ndarray:
    """
    Subtract a heavily-blurred background model and re-centre at 127.
    This handles gradual illumination drift across the page.
    """
    h, w   = gray.shape[:2]
    ksize  = max(51, (min(h, w) // 6) | 1)    # must be odd

    smooth = cv2.GaussianBlur(gray, (ksize, ksize), 0)
    result = gray.astype(np.float32) - smooth.astype(np.float32) + 127.0
    return np.clip(result, 0, 255).astype(np.uint8)


def deskew(gray_img: np.ndarray) -> np.ndarray:
    """
    Estimate text skew angle via minAreaRect and rotate to straighten.
    Skips extreme angles (>15°) which are more likely a detection error.
    """
    _, thresh = cv2.threshold(
        gray_img, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    y_idx, x_idx = np.where(thresh > 0)
    if len(y_idx) < 100:
        return gray_img

    coords = np.column_stack((x_idx, y_idx))
    rect   = cv2.minAreaRect(coords)
    angle  = rect[-1]

    rw, rh = rect[1]
    if rw < rh:
        angle = angle + 90 if angle < 0 else angle - 90
    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90

    if abs(angle) > 15:
        return gray_img

    h, w = gray_img.shape[:2]
    M    = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        gray_img, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )


def _correct_perspective(gray: np.ndarray) -> np.ndarray:
    """
    Attempt perspective correction by detecting the largest quadrilateral and
    applying a perspective transform. Falls back to original if detection fails.
    """
    h, w   = gray.shape[:2]
    edges  = cv2.Canny(gray, 50, 150)
    edges  = cv2.dilate(edges, None, iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return gray

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    page_quad = None
    for ctr in contours[:5]:
        if cv2.contourArea(ctr) < 0.3 * h * w:
            continue
        peri  = cv2.arcLength(ctr, True)
        approx = cv2.approxPolyDP(ctr, 0.02 * peri, True)
        if len(approx) == 4:
            page_quad = approx.reshape(4, 2).astype(np.float32)
            break

    if page_quad is None:
        return gray

    ordered = _order_points(page_quad)
    tl, tr, br, bl = ordered

    max_w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    max_h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if max_w <= 0 or max_h <= 0:
        return gray

    dst = np.array([
        [0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]
    ], dtype=np.float32)
    M = cv2.getPerspectiveTransform(ordered, dst)
    return cv2.warpPerspective(gray, M, (max_w, max_h))


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff    = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect