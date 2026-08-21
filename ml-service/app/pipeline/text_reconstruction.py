"""
Stage 11 – Text Reconstruction

Restores the original reading order and merges lines/paragraphs.

Steps:
  1. Sort recognized lines by reading order (top-to-bottom, left-to-right)
  2. Group into rows based on y-proximity (handles multi-column layouts)
  3. Detect paragraph breaks (gaps significantly larger than average line spacing)
  4. Reconstruct the final document text, preserving line breaks and paragraph spacing
"""

import numpy as np
from typing import List, Dict, Any


def reconstruct_text(lines: List[Dict[str, Any]]) -> str:
    """
    Stage 11: Reconstruct the full document text from recognized line records.

    Args:
        lines: List of dicts, each with keys:
               - "text":       recognised (and corrected) line text
               - "confidence": float confidence score
               - "bbox":       dict with x, y, w, h  (page-level coordinates)

    Returns:
        Final document text string with preserved line breaks and paragraph
        spacing (blank line between paragraphs).
    """
    if not lines:
        return ""

    # Filter out empty lines
    lines = [l for l in lines if l.get("text", "").strip()]
    if not lines:
        return ""

    # ── 1. Sort by reading order ──────────────────────────────────────────────
    ordered = _sort_reading_order(lines)

    # ── 2. Merge with paragraph detection ────────────────────────────────────
    parts = _merge_with_paragraphs(ordered)

    # ── 3. Join paragraphs with a blank line ─────────────────────────────────
    return "\n\n".join(parts)


# ── Reading order ─────────────────────────────────────────────────────────────

def _sort_reading_order(lines: List[Dict]) -> List[Dict]:
    """
    Group lines into rows based on y-proximity, then sort each row left-to-right.
    The threshold for same-row grouping is derived from the median bbox height.
    """
    heights = [l.get("bbox", {}).get("h", 20) for l in lines]
    med_h   = float(np.median(heights)) if heights else 20.0
    thresh  = med_h * 0.55  # y-difference within this → same row

    sorted_y = sorted(lines, key=lambda l: l.get("bbox", {}).get("y", 0))
    rows: List[List[Dict]] = []
    current_row: List[Dict] = []
    current_y_avg: float = 0.0

    for line in sorted_y:
        y = float(line.get("bbox", {}).get("y", 0))
        if not current_row:
            current_row.append(line)
            current_y_avg = y
        elif abs(y - current_y_avg) <= thresh:
            current_row.append(line)
            current_y_avg = (current_y_avg * (len(current_row) - 1) + y) / len(current_row)
        else:
            rows.append(sorted(current_row, key=lambda l: l.get("bbox", {}).get("x", 0)))
            current_row  = [line]
            current_y_avg = y

    if current_row:
        rows.append(sorted(current_row, key=lambda l: l.get("bbox", {}).get("x", 0)))

    return [line for row in rows for line in row]


# ── Paragraph detection ───────────────────────────────────────────────────────

def _merge_with_paragraphs(lines: List[Dict]) -> List[str]:
    """
    Merge ordered lines into paragraphs.

    A paragraph break is detected when the vertical gap between two consecutive
    lines exceeds 2× the average line spacing.
    """
    if not lines:
        return []

    # Compute vertical gaps: bottom of line[i] to top of line[i+1]
    gaps: List[float] = []
    for i in range(1, len(lines)):
        prev = lines[i - 1].get("bbox", {})
        curr = lines[i].get("bbox",  {})
        prev_bottom = prev.get("y", 0) + prev.get("h", 0)
        curr_top    = curr.get("y", 0)
        gaps.append(max(0.0, float(curr_top - prev_bottom)))

    avg_gap   = float(np.mean(gaps)) if gaps else 0.0
    para_thr  = avg_gap * 2.0  # gap > 2× average → paragraph break

    paragraphs: List[str]  = []
    current_lines: List[str] = []

    for i, line in enumerate(lines):
        text = line.get("text", "").strip()
        if not text:
            continue
        current_lines.append(text)

        # Check if next line starts a new paragraph
        if i < len(lines) - 1 and i < len(gaps):
            if gaps[i] > para_thr and para_thr > 0:
                paragraphs.append("\n".join(current_lines))
                current_lines = []

    if current_lines:
        paragraphs.append("\n".join(current_lines))

    return paragraphs
