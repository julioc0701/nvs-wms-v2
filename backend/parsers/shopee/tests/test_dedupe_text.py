import pytest
from parsers.shopee._dedupe_text import (
    dedupe_overlapping_text,
    dedupe_cell,
    fix_broken_digits,
    _duplicate_pair_ratio,
)


class TestDuplicatePairRatio:
    def test_clean_text_low_ratio(self):
        assert _duplicate_pair_ratio("Viseira Transparent") < 0.6

    def test_doubled_text_high_ratio(self):
        # "NNoo.." has ratio 1.0
        assert _duplicate_pair_ratio("NNoo..") >= 0.6

    def test_short_text_zero(self):
        assert _duplicate_pair_ratio("ab") == 0.0

    def test_empty(self):
        assert _duplicate_pair_ratio("") == 0.0


class TestDedupeOverlappingText:
    def test_doubled_header(self):
        assert dedupe_overlapping_text("NNoo..") == "No."

    def test_doubled_words_below_threshold(self):
        # "FFaarrooll" has ratio 5/9 ≈ 0.556 < 0.60 — function correctly leaves it alone.
        # This is the safety-net layer; primary dedup is done by fitz/pdfplumber.
        result = dedupe_overlapping_text("FFaarrooll CCoommpplleettoo")
        assert result == "FFaarrooll CCoommpplleettoo"

    def test_doubled_short_string_above_threshold(self):
        # "SSKKUU" has ratio 3/5 = 0.60 — fires and deduplicates
        assert dedupe_overlapping_text("SSKKUU") == "SKU"

    def test_clean_text_unchanged(self):
        assert dedupe_overlapping_text("Viseira Transparent") == "Viseira Transparent"

    def test_none_returns_none(self):
        assert dedupe_overlapping_text(None) is None

    def test_empty_unchanged(self):
        assert dedupe_overlapping_text("") == ""

    def test_legitimate_double_letters_preserved(self):
        # "viseira" has 'i' once, not doubled — should not be touched
        result = dedupe_overlapping_text("viseira")
        assert result == "viseira"


class TestDedupeCell:
    def test_doubled_cell(self):
        assert dedupe_cell("SSKKUU") == "SKU"

    def test_none_returns_empty(self):
        assert dedupe_cell(None) == ""

    def test_clean_cell_unchanged(self):
        assert dedupe_cell("VEOX") == "VEOX"


class TestFixBrokenDigits:
    def test_split_100(self):
        assert fix_broken_digits("1\n0\n0") == "100"

    def test_split_200(self):
        assert fix_broken_digits("2\n0\n0") == "200"

    def test_no_split_needed(self):
        assert fix_broken_digits("240") == "240"

    def test_mixed_not_split(self):
        # "1\nab\n0" — not all single digits → unchanged
        assert fix_broken_digits("1\nab\n0") == "1\nab\n0"

    def test_no_newline(self):
        assert fix_broken_digits("100") == "100"
