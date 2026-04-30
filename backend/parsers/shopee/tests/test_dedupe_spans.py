import pytest
from parsers.shopee._dedupe_spans import (
    _bboxes_overlap,
    dedupe_spans_on_page,
    reconstruct_lines,
)
import fitz

FIXTURE_PDF = "parsers/shopee/tests/fixtures/FBSINBR2026042800054.pdf"


class TestBboxOverlap:
    def test_identical_bboxes_overlap(self):
        b = (10.0, 20.0, 100.0, 30.0)
        assert _bboxes_overlap(b, b)

    def test_offset_within_tolerance(self):
        b1 = (10.0, 20.0, 100.0, 30.0)
        b2 = (10.0, 20.0, 102.0, 30.0)  # 2px diff on x1
        assert _bboxes_overlap(b1, b2, tol=3.0)

    def test_offset_outside_tolerance(self):
        b1 = (10.0, 20.0, 100.0, 30.0)
        b2 = (10.0, 20.0, 110.0, 30.0)  # 10px diff on x1
        assert not _bboxes_overlap(b1, b2, tol=3.0)

    def test_completely_different_bboxes(self):
        b1 = (10.0, 20.0, 100.0, 30.0)
        b2 = (200.0, 300.0, 400.0, 500.0)
        assert not _bboxes_overlap(b1, b2)


class TestDedupeSpansOnPage:
    @pytest.fixture
    def doc(self):
        d = fitz.open(FIXTURE_PDF)
        yield d
        d.close()

    def test_clean_page_no_dedup(self, doc):
        page = doc[0]  # page 1: clean
        _, n_deduped = dedupe_spans_on_page(page)
        assert n_deduped == 0

    def test_returns_spans(self, doc):
        page = doc[0]
        spans, _ = dedupe_spans_on_page(page)
        assert len(spans) > 0
        assert "text" in spans[0]
        assert "bbox" in spans[0]


class TestReconstructLines:
    def test_empty_spans(self):
        assert reconstruct_lines([]) == []

    def test_single_span(self):
        spans = [{"text": "hello", "bbox": (0, 10, 50, 20)}]
        lines = reconstruct_lines(spans)
        assert lines == ["hello"]

    def test_two_spans_same_line(self):
        spans = [
            {"text": "hello", "bbox": (0, 10, 50, 20)},
            {"text": "world", "bbox": (60, 10, 120, 20)},
        ]
        lines = reconstruct_lines(spans)
        assert len(lines) == 1
        assert "hello" in lines[0]
        assert "world" in lines[0]

    def test_two_spans_different_lines(self):
        spans = [
            {"text": "line1", "bbox": (0, 10, 50, 20)},
            {"text": "line2", "bbox": (0, 30, 50, 40)},
        ]
        lines = reconstruct_lines(spans)
        assert len(lines) == 2
