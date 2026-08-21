"""
Stage 1 – Image Quality Assessment (IQA)

Evaluates the raw input image before any preprocessing.
Returns a QualityResult containing:
  • Per-metric statistics (resolution, DPI, brightness, contrast, blur, noise, shadow, skew, perspective, uniformity)
  • Overall quality score (0–1) and classification (Excellent / Good / Acceptable / Poor)
  • Recommended adaptive preprocessing parameters for Stage 2
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple


@dataclass
class QualityResult:
    # ── Raw image metrics ────────────────────────────────────────────────────
    width: int              = 0
    height: int             = 0
    dpi_estimate: float     = 0.0
    brightness: float       = 0.0     # mean pixel value [0–255]
    contrast: float         = 0.0     # std of pixel values
    blur_score: float       = 0.0     # Laplacian variance (higher = sharper)
    noise_level: float      = 0.0     # estimated noise σ
    shadow_detected: bool   = False
    skew_angle: float       = 0.0     # degrees (absolute)
    perspective_score: float= 0.0     # 0 = flat, 1 = highly distorted
    background_uniformity: float = 0.0  # 0–1

    # ── Overall assessment ───────────────────────────────────────────────────
    score: float            = 0.0
    classification: str     = "Unknown"  # Excellent / Good / Acceptable / Poor

    # ── Recommended preprocessing parameters for Stage 2 ────────────────────
    params: Dict[str, Any]  = field(default_factory=dict)


def assess_quality(img_bgr: np.ndarray) -> QualityResult:
    """
    Compute IQA metrics for a BGR OpenCV image and return a QualityResult.
    """
    result = QualityResult()
    h, w = img_bgr.shape[:2]
    result.width  = w
    result.height = h

    # ── 1. Resolution / DPI estimate ─────────────────────────────────────────
    # Assume standard A4/Letter page (~8.5 inches wide): DPI ≈ width / 8.5
    result.dpi_estimate = w / 8.5

    # ── 2. Grayscale for metric computation ──────────────────────────────────
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # ── 3. Brightness (mean) ─────────────────────────────────────────────────
    result.brightness = float(np.mean(gray))

    # ── 4. Contrast (std of pixel values) ───────────────────────────────────
    result.contrast = float(np.std(gray))

    # ── 5. Blur score (Variance of Laplacian) ────────────────────────────────
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    result.blur_score = float(lap.var())

    # ── 6. Noise level (MAD-based σ estimate) ────────────────────────────────
    lap_flat = lap.ravel()
    result.noise_level = float(np.median(np.abs(lap_flat - np.median(lap_flat))) / 0.6745)

    # ── 7. Shadow detection ──────────────────────────────────────────────────
    # Divide image into a 4×4 grid; large std of cell means → shadow/gradient
    grid_rows, grid_cols = 4, 4
    cell_h = max(1, h // grid_rows)
    cell_w = max(1, w // grid_cols)
    cell_means = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            cell = gray[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
            cell_means.append(float(np.mean(cell)))
    result.shadow_detected = bool(float(np.std(cell_means)) > 30.0)

    # ── 8. Background uniformity ─────────────────────────────────────────────
    # Sample the four corners (assumed background)
    corner_size = max(10, min(h // 8, w // 8, 60))
    corners = [
        gray[:corner_size, :corner_size],
        gray[:corner_size, -corner_size:],
        gray[-corner_size:, :corner_size],
        gray[-corner_size:, -corner_size:],
    ]
    corner_vals = np.concatenate([c.ravel() for c in corners])
    result.background_uniformity = max(0.0, 1.0 - float(np.std(corner_vals)) / 128.0)

    # ── 9. Skew angle estimate ────────────────────────────────────────────────
    result.skew_angle = _estimate_skew(gray)

    # ── 10. Perspective distortion estimate ───────────────────────────────────
    result.perspective_score = _estimate_perspective(gray)

    # ── 11. Overall score & classification ───────────────────────────────────
    result.score = _compute_score(result)
    if result.score >= 0.85:
        result.classification = "Excellent"
    elif result.score >= 0.65:
        result.classification = "Good"
    elif result.score >= 0.45:
        result.classification = "Acceptable"
    else:
        result.classification = "Poor"

    # ── 12. Derive adaptive preprocessing parameters ─────────────────────────
    result.params = _derive_params(result)

    return result


# ── Metric helpers ────────────────────────────────────────────────────────────

def _estimate_skew(gray: np.ndarray) -> float:
    """Return absolute skew angle in degrees."""
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    y_idx, x_idx = np.where(thresh > 0)
    if len(y_idx) < 100:
        return 0.0
    coords = np.column_stack((x_idx, y_idx))
    rect    = cv2.minAreaRect(coords)
    angle   = rect[-1]
    rw, rh  = rect[1]
    if rw < rh:
        angle = angle + 90 if angle < 0 else angle - 90
    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90
    return float(abs(angle))


def _estimate_perspective(gray: np.ndarray) -> float:
    """
    Heuristic perspective score.
    Detects if the largest contour is a skewed quadrilateral rather than a rectangle.
    Returns 0 (flat) to 1 (highly distorted).
    """
    h, w = gray.shape[:2]
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0

    largest = max(contours, key=cv2.contourArea)
    area    = cv2.contourArea(largest)
    if area < 0.3 * h * w:
        return 0.0

    peri  = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4:
        return 0.0

    # Measure how non-rectangular the quad is
    pts = approx.reshape(4, 2).astype(np.float32)
    x_r, y_r, w_r, h_r = cv2.boundingRect(pts)
    rect_area = max(w_r * h_r, 1)
    score = 1.0 - (area / rect_area)
    return float(np.clip(score, 0.0, 1.0))


# ── Scoring ───────────────────────────────────────────────────────────────────

def _compute_score(r: QualityResult) -> float:
    """Weighted quality score [0, 1]."""
    blur_s       = min(1.0, r.blur_score / 200.0)
    bright_s     = max(0.0, 1.0 - abs(r.brightness - 150) / 150.0)
    contrast_s   = min(1.0, r.contrast / 60.0)
    noise_s      = max(0.0, 1.0 - r.noise_level / 50.0)
    skew_s       = max(0.0, 1.0 - r.skew_angle / 15.0)
    bg_s         = r.background_uniformity
    perspective_s = 1.0 - r.perspective_score
    shadow_pen   = 0.15 if r.shadow_detected else 0.0

    score = (
        blur_s        * 0.25 +
        bright_s      * 0.15 +
        contrast_s    * 0.15 +
        noise_s       * 0.15 +
        skew_s        * 0.10 +
        bg_s          * 0.10 +
        perspective_s * 0.10
    ) - shadow_pen

    return float(np.clip(score, 0.0, 1.0))


# ── Parameter derivation ──────────────────────────────────────────────────────

def _derive_params(r: QualityResult) -> Dict[str, Any]:
    """Derive adaptive preprocessing parameters from quality metrics."""
    p: Dict[str, Any] = {}

    # CLAHE clip limit — increase for low contrast
    if r.contrast < 30:
        p["clahe_clip"] = 4.0
    elif r.contrast < 50:
        p["clahe_clip"] = 3.0
    else:
        p["clahe_clip"] = 2.0

    # CLAHE tile grid — finer tiles for uneven illumination / shadow
    if r.shadow_detected or r.background_uniformity < 0.5:
        p["clahe_tile"] = (4, 4)
    else:
        p["clahe_tile"] = (8, 8)

    # Gamma correction — brighten dark images, darken over-exposed ones
    if r.brightness < 90:
        p["gamma"] = 0.65       # lower gamma → brightens the image
    elif r.brightness < 120:
        p["gamma"] = 0.80
    elif r.brightness > 210:
        p["gamma"] = 1.40       # higher gamma → darkens
    elif r.brightness > 180:
        p["gamma"] = 1.20
    else:
        p["gamma"] = 1.0        # no correction

    # Denoising strategy
    if r.noise_level > 20:
        p["denoise_method"]   = "bilateral"
        p["bilateral_d"]      = 9
        p["bilateral_sigma"]  = 75
    elif r.noise_level > 8:
        p["denoise_method"]   = "bilateral"
        p["bilateral_d"]      = 5
        p["bilateral_sigma"]  = 50
    else:
        p["denoise_method"]   = "gaussian"
        p["gaussian_k"]       = 3

    # Shadow removal
    p["remove_shadow"] = bool(r.shadow_detected or r.background_uniformity < 0.6)

    # Perspective correction
    p["correct_perspective"] = bool(r.perspective_score > 0.15)

    # Deskew
    p["deskew"] = bool(r.skew_angle > 0.5)

    # Working height — boost for low-res images
    p["working_height"] = 1200 if r.height < 800 else 1600

    return p
