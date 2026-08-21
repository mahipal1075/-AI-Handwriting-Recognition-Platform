"""
Stage 6 – Line Segmentation

Since Stage 4 (detection.py) now returns tight line-level bounding boxes
using word-polygon grouping, most crops are already single lines.

This stage acts as a safety net:
  • If crop height / estimated line height < 1.6  →  return [crop] (already one line)
  • Otherwise use horizontal projection profile to split
"""

import cv2
import numpy as np
from typing import List


# Height ratio above which we attempt to split (1.6 = probably 2 lines)
_MULTI_LINE_RATIO = 1.6


def segment_lines(crop: np.ndarray) -> List[np.ndarray]:
    """
    Split a crop into single-line sub-crops if it appears to contain
    more than one handwriting line.

    Returns a list of grayscale crops (may be just [crop]).
    """
    h, w = crop.shape[:2]
    if h < 20 or w < 20:
        return [crop]

    # Estimate single line height from the crop itself
    est_line_h = _estimate_line_height(crop)

    # If crop height is close to one line → skip segmentation
    if est_line_h <= 0 or h / est_line_h < _MULTI_LINE_RATIO:
        return [crop]

    # Binarize
    _, thresh = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Horizontal projection
    h_proj   = np.sum(thresh > 0, axis=1)
    ink_rows = h_proj[h_proj > 0]
    mean_dens = float(np.mean(ink_rows)) if ink_rows.size > 0 else 1.0
    gap_thresh = max(1.0, mean_dens * 0.08)
    is_gap    = h_proj <= gap_thresh

    bands = _find_text_bands(is_gap, h)
    if len(bands) <= 1:
        return [crop]

    lines: List[np.ndarray] = []
    for (top, bottom) in bands:
        if bottom - top < 6:
            continue
        y1 = max(0, top - 3)
        y2 = min(h, bottom + 3)
        lc = crop[y1:y2, :]
        if lc.size > 0:
            lines.append(lc)

    return lines if lines else [crop]


def _estimate_line_height(crop: np.ndarray) -> int:
    """Estimate single-line height using connected component analysis."""
    _, thresh = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(thresh, connectivity=8)
    if num_labels <= 1:
        return crop.shape[0]
    heights = stats[1:, cv2.CC_STAT_HEIGHT]  # skip background
    heights = heights[heights > 3]
    if len(heights) == 0:
        return crop.shape[0]
    # Median component height ≈ typical character/ascender height
    median_h = int(np.percentile(heights, 75))
    # A single line height ≈ 2x the median char height
    return max(10, int(median_h * 2.0))


def _find_text_bands(is_gap: np.ndarray, total_h: int) -> List[tuple]:
    bands: List[tuple] = []
    in_text   = False
    start_row = 0
    for i, gap in enumerate(is_gap):
        if not gap and not in_text:
            in_text   = True
            start_row = i
        elif gap and in_text:
            in_text = False
            if i - start_row >= 8:
                bands.append((start_row, i))
    if in_text and total_h - start_row >= 8:
        bands.append((start_row, total_h))
    return bands
