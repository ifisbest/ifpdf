"""Tests for layout analysis."""

from ifpdf.extractor import ExtractedPage, TextBlock
from ifpdf.layout import (
    LayoutConfig,
    _detect_body_font_size,
    _is_heading,
    analyze_layout,
)


def test_detect_body_font_size():
    page = ExtractedPage(page_num=1, width=612, height=792)
    page.blocks = [
        TextBlock(text="Heading", page_num=1, x0=0, y0=0, x1=100, y1=20, font_size=18),
        TextBlock(text="Body one", page_num=1, x0=0, y0=30, x1=100, y1=45, font_size=11),
        TextBlock(text="Body two", page_num=1, x0=0, y0=50, x1=100, y1=65, font_size=11),
    ]
    assert _detect_body_font_size(page) == 11.0


def test_is_heading_by_size():
    config = LayoutConfig()
    block = TextBlock(
        text="Introduction", page_num=1, x0=0, y0=0, x1=100, y1=20,
        font_size=16, is_bold=False,
    )
    assert _is_heading(block, body_size=11.0, config=config) is True


def test_is_heading_bold_conservative():
    config = LayoutConfig()
    # Long bold text with colon should NOT be a heading
    block = TextBlock(
        text="Product Planning and Strategy Development:", page_num=1, x0=0, y0=0, x1=500, y1=20,
        font_size=11, is_bold=True,
    )
    assert _is_heading(block, body_size=11.0, config=config) is False


def test_is_heading_bold_short():
    config = LayoutConfig()
    block = TextBlock(
        text="Education", page_num=1, x0=0, y0=0, x1=100, y1=20,
        font_size=11, is_bold=True,
    )
    assert _is_heading(block, body_size=11.0, config=config) is True


def test_is_heading_list_marker():
    config = LayoutConfig()
    block = TextBlock(
        text="•", page_num=1, x0=0, y0=0, x1=10, y1=20,
        font_size=11, is_bold=False,
    )
    assert _is_heading(block, body_size=11.0, config=config) is False


def test_is_heading_long_sentence():
    config = LayoutConfig()
    block = TextBlock(
        text="This is a very long sentence with many words and commas, not a heading.",
        page_num=1, x0=0, y0=0, x1=500, y1=20,
        font_size=11, is_bold=True,
    )
    assert _is_heading(block, body_size=11.0, config=config) is False


def test_analyze_layout():
    from ifpdf.extractor import ExtractedDocument

    doc = ExtractedDocument(filepath="test.pdf")
    page = ExtractedPage(page_num=1, width=612, height=792)
    page.blocks = [
        TextBlock(text="Title", page_num=1, x0=0, y0=0, x1=100, y1=30, font_size=20),
        TextBlock(text="Body text here.", page_num=1, x0=0, y0=40, x1=200, y1=55, font_size=11),
    ]
    doc.pages.append(page)

    analyze_layout(doc)

    assert doc.pages[0].blocks[0].block_type == "heading_1"
    assert doc.pages[0].blocks[1].block_type == "body"
