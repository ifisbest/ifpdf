"""Tests for page mapping."""

from ifpdf.pagemap import format_chunk_comment, format_page_comment, map_page_number


class TestMapPageNumber:
    def test_front_matter(self):
        assert map_page_number(1, content_starts_at=25) is None
        assert map_page_number(24, content_starts_at=25) is None

    def test_content_page(self):
        assert map_page_number(25, content_starts_at=25) == 1
        assert map_page_number(26, content_starts_at=25) == 2
        assert map_page_number(100, content_starts_at=25) == 76

    def test_default_start(self):
        assert map_page_number(1, content_starts_at=1) == 1
        assert map_page_number(5, content_starts_at=1) == 5


class TestFormatPageComment:
    def test_front_matter_comment(self):
        assert "PDF 第 10 页（前言/目录）" in format_page_comment(10, content_starts_at=25)

    def test_content_comment(self):
        assert "第 1 页" in format_page_comment(25, content_starts_at=25)
        assert "第 2 页" in format_page_comment(26, content_starts_at=25)


class TestFormatChunkComment:
    def test_with_pages(self):
        s = format_chunk_comment(1, 5, 10, 20)
        assert "CHUNK 1/5" in s
        assert "第 10-20 页" in s

    def test_without_pages(self):
        s = format_chunk_comment(2, 5, None, None)
        assert "CHUNK 2/5" in s
        assert "第" not in s
