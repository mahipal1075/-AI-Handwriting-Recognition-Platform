"""
Stage 5 – Region Optimization

Simple, clean crop of the detected bounding box with a small margin.
All image enhancement (CLAHE, contrast stretch, sharpening) is done once
in Stage 7 (recognition.py prepare_patch()) to avoid double-processing
which degrades TrOCR recognition quality.
"""

import numpy as np
from typing import Dict


def optimize_region(gray_img: np.ndarray, bbox: Dict) -> np.ndarray:
    """
    Crop a detected text region with a small margin for context.
    No image processing is done here — enhance once in prepare_patch().
    """
    img_h, img_w = gray_img.shape[:2]
    x, y, w, h   = bbox["x"], bbox["y"], bbox["w"], bbox["h"]

    # Small margin for context
    mx = max(4, int(w * 0.03))
    my = max(4, int(h * 0.05))
    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(img_w, x + w + mx)
    y2 = min(img_h, y + h + my)

    return gray_img[y1:y2, x1:x2].copy()
