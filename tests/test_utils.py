"""Tests for utility functions."""

from ifpdf.utils import parse_page_range


def test_parse_page_range_none():
    assert parse_page_range(None) is None


def test_parse_page_range_single():
    assert parse_page_range("5") == (5, 5)


def test_parse_page_range_range():
    assert parse_page_range("1-10") == (1, 10)


def test_parse_page_range_whitespace():
    assert parse_page_range("  3 - 7  ") == (3, 7)
