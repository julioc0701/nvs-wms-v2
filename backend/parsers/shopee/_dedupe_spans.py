import logging
from typing import List, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

_BBOX_TOLERANCE = 3.0  # px — Skia offset is typically 1-3px on one edge


def _bboxes_overlap(b1: tuple, b2: tuple, tol: float = _BBOX_TOLERANCE) -> bool:
    """True when two bboxes are within tol on all four edges (i.e. nearly identical position)."""
    return all(abs(b1[i] - b2[i]) <= tol for i in range(4))


def dedupe_spans_on_page(page: fitz.Page) -> Tuple[List[dict], int]:
    """
    Extract spans from a fitz page and remove duplicates caused by Skia double-layer.
    Returns (clean_spans, n_deduped).

    Algorithm from PyMuPDF maintainer Discussion #2319:
    - Sort spans by (y0, x0, text)
    - Walk in reverse; mark span for deletion if previous span shares bbox within tolerance
      and has same or prefix-matching text
    - Keep first occurrence (lowest index after sort)
    """
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    spans: List[dict] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                spans.append({
                    "bbox": tuple(round(v, 2) for v in span["bbox"]),
                    "text": span["text"],
                    "origin": (span["origin"][0], span["origin"][1]),
                })

    if not spans:
        return spans, 0

    # Sort by y0, x0 — group visually adjacent spans
    spans.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))

    to_delete = set()
    for i in range(1, len(spans)):
        prev = spans[i - 1]
        curr = spans[i]
        if (
            _bboxes_overlap(prev["bbox"], curr["bbox"])
            and (
                prev["text"] == curr["text"]
                or curr["text"].startswith(prev["text"])
                or prev["text"].startswith(curr["text"])
            )
        ):
            # Keep prev (first seen), discard curr
            to_delete.add(i)

    clean = [s for idx, s in enumerate(spans) if idx not in to_delete]
    n_deduped = len(to_delete)
    return clean, n_deduped


def reconstruct_lines(spans: List[dict], y_tolerance: float = 3.0) -> List[str]:
    """
    Group spans by y-coordinate (same line) and join into text lines sorted by x.
    """
    if not spans:
        return []

    # Group by y0 within tolerance
    lines: List[List[dict]] = []
    current_line: List[dict] = []
    last_y = None

    for span in sorted(spans, key=lambda s: (s["bbox"][1], s["bbox"][0])):
        y0 = span["bbox"][1]
        if last_y is None or abs(y0 - last_y) <= y_tolerance:
            current_line.append(span)
            last_y = y0
        else:
            if current_line:
                lines.append(current_line)
            current_line = [span]
            last_y = y0

    if current_line:
        lines.append(current_line)

    return [" ".join(s["text"] for s in sorted(line, key=lambda s: s["bbox"][0])).strip()
            for line in lines if any(s["text"].strip() for s in line)]


def extract_clean_text_from_page(page: fitz.Page) -> Tuple[str, int]:
    """
    Full pipeline: dedupe spans → reconstruct lines → join.
    Returns (clean_text, n_deduped).
    """
    clean_spans, n_deduped = dedupe_spans_on_page(page)
    lines = reconstruct_lines(clean_spans)
    return "\n".join(lines), n_deduped
