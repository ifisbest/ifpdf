"""Tests for metadata extraction."""

import pytest

from ifpdf.metadata import BookMetadata, _clean_publisher, _extract_isbn, _extract_year, parse_filename


class TestExtractYear:
    def test_extract_year(self):
        assert _extract_year("Published in 2007 by Foo") == "2007"
        assert _extract_year("1999年") == "1999"
        assert _extract_year("No year here") == ""


class TestExtractISBN:
    def test_extract_isbn13(self):
        assert _extract_isbn("9787301122303") == "9787301122303"
        assert _extract_isbn("foo 9787301122303 bar") == "9787301122303"

    def test_extract_isbn10(self):
        assert _extract_isbn("0306406152") == "0306406152"
        assert _extract_isbn("123456789X") == "123456789X"


class TestCleanPublisher:
    def test_remove_location(self):
        assert _clean_publisher("北京市：北京大学出版社") == "北京大学出版社"
        assert _clean_publisher("上海:上海古籍出版社") == "上海古籍出版社"

    def test_remove_parentheses(self):
        assert _clean_publisher("中华书局（北京）") == "中华书局"


class TestParseFilename:
    def test_anna_archive_style(self):
        name = "中国古代小说史叙论-_刘勇强著_2007_--_北京市：北京大学出版社_--_9787301122303"
        meta = parse_filename(name)
        assert meta.title == "中国古代小说史叙论"
        assert meta.author == "刘勇强"
        assert meta.year == "2007"
        assert meta.publisher == "北京大学出版社"
        assert meta.isbn == "9787301122303"

    def test_simple_name(self):
        meta = parse_filename("红楼梦.pdf")
        assert meta.title == "红楼梦"

    def test_with_underscores(self):
        meta = parse_filename("史记_司马迁.pdf")
        assert meta.title == "史记"
        assert meta.author == "司马迁"
