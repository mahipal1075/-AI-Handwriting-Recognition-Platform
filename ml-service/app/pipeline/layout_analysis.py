"""
Stage 3 – Page Layout Analysis

Heuristic layout detector using projection profiles and connected components.
Does not require a separate ML model — fully offline and fast.

Returns a layout map dict describing:
  • page_size, margins, writing_region
  • paragraph_blocks
  • has_table, has_header, has_footer
"""

import cv2
import numpy as np
from typing import List, Dict, Any


def analyze_layout(gray_img: np.ndarray) -> Dict[str, Any]:
    """
    Analyze the page layout of a preprocessed grayscale image.
    Returns a layout map.
    """
    h, w = gray_img.shape[:2]

    # Binary mask: text = white, background = black
    _, thresh = cv2.threshold(
        gray_img, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    margins        = _detect_margins(thresh)
    writing_region = _detect_writing_region(thresh, margins)
    para_blocks    = _detect_paragraph_blocks(thresh, writing_region)
    has_header, has_footer = _detect_header_footer(thresh, h)
    has_table      = _detect_table(thresh, w)

    return {
        "page_size":         {"width": w, "height": h},
        "margins":           margins,
        "writing_region":    writing_region,
        "paragraph_blocks":  para_blocks,
        "has_table":         has_table,
        "has_header":        has_header,
        "has_footer":        has_footer,
    }


# ── Layout helpers ────────────────────────────────────────────────────────────

def _detect_margins(thresh: np.ndarray) -> Dict[str, int]:
    """Detect page margins as the bounding box of all content pixels."""
    h, w = thresh.shape[:2]
    rows = np.any(thresh > 0, axis=1)
    cols = np.any(thresh > 0, axis=0)

    if not np.any(rows) or not np.any(cols):
        return {"top": 0, "bottom": h, "left": 0, "right": w}

    top    = int(np.argmax(rows))
    bottom = int(h - np.argmax(rows[::-1]))
    left   = int(np.argmax(cols))
    right  = int(w - np.argmax(cols[::-1]))

    return {"top": top, "bottom": bottom, "left": left, "right": right}


def _detect_writing_region(thresh: np.ndarray, margins: Dict) -> Dict[str, int]:
    """Main writing region with a small inset from the detected margins."""
    pad = 5
    return {
        "x": max(0, margins["left"] - pad),
        "y": max(0, margins["top"]  - pad),
        "w": max(0, margins["right"]  - margins["left"] + 2 * pad),
        "h": max(0, margins["bottom"] - margins["top"]  + 2 * pad),
    }


def _detect_paragraph_blocks(
    thresh: np.ndarray, writing_region: Dict
) -> List[Dict[str, Any]]:
    """
    Detect paragraph blocks using the horizontal projection profile.
    Rows with near-zero density are treated as paragraph separators.
    """
    if not writing_region:
        return []

    h_img, w_img = thresh.shape[:2]
    x  = writing_region.get("x", 0)
    y  = writing_region.get("y", 0)
    ww = writing_region.get("w", w_img)
    hh = writing_region.get("h", h_img)

    roi    = thresh[y:y + hh, x:x + ww]
    h_proj = np.sum(roi > 0, axis=1)  # non-zero pixels per row

    # A row is "text" if at least 1% of its width contains ink
    threshold = max(1, ww * 0.01)
    is_text   = h_proj >= threshold

    blocks   = []
    in_block = False
    blk_start = 0

    for i, has_text in enumerate(is_text):
        if has_text and not in_block:
            in_block  = True
            blk_start = i
        elif not has_text and in_block:
            in_block = False
            blk_h    = i - blk_start
            if blk_h > 10:
                blocks.append({
                    "x": x, "y": y + blk_start,
                    "w": ww, "h": blk_h,
                    "type": "paragraph"
                })

    if in_block:
        blk_h = len(is_text) - blk_start
        if blk_h > 10:
            blocks.append({
                "x": x, "y": y + blk_start,
                "w": ww, "h": blk_h,
                "type": "paragraph"
            })

    return blocks


def _detect_header_footer(thresh: np.ndarray, total_h: int) -> tuple:
    """
    Detect header/footer by checking if the top/bottom 10% has isolated content
    with a lower density than the main body.
    """
    band = max(1, total_h // 10)
    header_region = thresh[:band, :]
    footer_region = thresh[-band:, :]
    main_region   = thresh[band:-band, :]

    def density(region):
        return np.sum(region > 0) / max(region.size, 1)

    h_d = density(header_region)
    f_d = density(footer_region)
    m_d = density(main_region)

    has_header = bool(h_d > 0.002 and h_d < m_d * 0.6)
    has_footer = bool(f_d > 0.002 and f_d < m_d * 0.6)
    return has_header, has_footer


def _detect_table(thresh: np.ndarray, w: int) -> bool:
    """
    Simple table detection: look for 3+ horizontal line structures.
    """
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(1, w // 3), 1))
    h_lines  = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)
    line_rows = np.sum(h_lines > 0, axis=1)
    line_count = int(np.sum(line_rows > w * 0.3))
    return bool(line_count >= 3)
