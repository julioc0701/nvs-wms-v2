import re
import logging

logger = logging.getLogger(__name__)

_DUPLICATE_PAIR_THRESHOLD = 0.60


def _duplicate_pair_ratio(text: str) -> float:
    """Fraction of adjacent char pairs that are equal (ignoring spaces)."""
    chars = [c for c in text if c != " "]
    if len(chars) < 4:
        return 0.0
    pairs = len(chars) - 1
    dupes = sum(1 for i in range(pairs) if chars[i] == chars[i + 1])
    return dupes / pairs


def dedupe_overlapping_text(text: str) -> str:
    """
    Remove consecutive duplicate characters produced by Skia/Chromium double-layer rendering.
    Only fires when >60% of adjacent char pairs are equal — guards against legitimate
    double letters like 'rr' in 'Ferrari' or 'oo' in 'ool'.
    """
    if not text or _duplicate_pair_ratio(text) < _DUPLICATE_PAIR_THRESHOLD:
        return text

    # Collapse runs of identical chars: AABBCC -> ABC, FF aa rr oo ll -> F a r o l
    deduped = re.sub(r"(.)\1+", r"\1", text)
    return deduped


def dedupe_cell(value: str | None) -> str:
    """Apply dedupe to a single table cell value."""
    if not value:
        return value or ""
    cleaned = dedupe_overlapping_text(str(value))
    return cleaned.strip()


def fix_broken_digits(value: str) -> str:
    """
    Re-join digit sequences split across lines by buggy pages.
    '1\\n0\\n0' -> '100'
    Only fires when every token between newlines is a single digit.
    """
    if not value or "\n" not in value:
        return value
    parts = [p.strip() for p in value.split("\n")]
    if all(len(p) == 1 and p.isdigit() for p in parts if p):
        return "".join(p for p in parts if p)
    return value


def dedupe_pdfplumber_page(page):
    """
    Apply pdfplumber built-in dedupe_chars with Skia-safe settings.
    extra_attrs=[] is critical — Skia layers may differ in fontname/size,
    so the default extra_attrs would silently fail to deduplicate.
    """
    try:
        return page.dedupe_chars(tolerance=1, extra_attrs=[])
    except Exception:
        return page
