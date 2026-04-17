from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz
import pdfplumber


@dataclass
class TextBlock:
    """A single block of text extracted from a PDF."""

    text: str
    page_num: int
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float = 0.0
    is_bold: bool = False
    is_italic: bool = False
    block_type: str = "body"

    @property
    def area(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)


@dataclass
class ExtractedPage:
    """All content extracted from a single PDF page."""

    page_num: int
    width: float
    height: float
    blocks: list[TextBlock] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    """Full document extracted from a PDF."""

    filepath: str
    title: str = ""
    author: str = ""
    page_count: int = 0
    pages: list[ExtractedPage] = field(default_factory=list)


def _clean_text(text: str) -> str:
    """Clean up extracted text: normalize whitespace, remove soft hyphens."""
    text = text.replace("\xad", "")  # soft hyphen
    text = text.replace("\u200b", "")  # zero-width space
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_flags(flags: int) -> tuple[bool, bool]:
    """Parse PyMuPDF font flags to determine bold/italic."""
    is_bold = bool(flags & 2 ** 4)  # FTEXT_BOLD
    is_italic = bool(flags & 2 ** 6)  # FTEXT_ITALIC
    return is_bold, is_italic


def _is_header_footer(block: TextBlock, page_height: float, header_ratio: float = 0.08, footer_ratio: float = 0.92) -> bool:
    """Detect if a block is in the header or footer region."""
    center_y = (block.y0 + block.y1) / 2
    return center_y < page_height * header_ratio or center_y > page_height * footer_ratio


def extract_pdf(
    filepath: str | Path,
    page_range: tuple[int, int] | None = None,
    strip_headers: bool = True,
) -> ExtractedDocument:
    """Extract structured text from a PDF file.

    Args:
        filepath: Path to the PDF file.
        page_range: Optional (start, end) 1-based page numbers.
        strip_headers: Remove text in header/footer regions.

    Returns:
        ExtractedDocument with structured blocks per page.
    """
    path = Path(filepath)
    doc = fitz.open(str(path))

    result = ExtractedDocument(
        filepath=str(path),
        title=doc.metadata.get("title", ""),
        author=doc.metadata.get("author", ""),
        page_count=len(doc),
    )

    start_page = page_range[0] - 1 if page_range else 0
    end_page = page_range[1] if page_range else len(doc)

    for page_idx in range(start_page, min(end_page, len(doc))):
        page = doc[page_idx]
        page_num = page_idx + 1
        page_rect = page.rect

        ep = ExtractedPage(
            page_num=page_num,
            width=page_rect.width,
            height=page_rect.height,
        )

        # Extract text blocks with layout info
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES)["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                for span in line["spans"]:
                    text = _clean_text(span["text"])
                    if not text:
                        continue

                    is_bold, is_italic = _parse_flags(span["flags"])

                    tb = TextBlock(
                        text=text,
                        page_num=page_num,
                        x0=span["bbox"][0],
                        y0=span["bbox"][1],
                        x1=span["bbox"][2],
                        y1=span["bbox"][3],
                        font_size=span["size"],
                        is_bold=is_bold,
                        is_italic=is_italic,
                    )

                    if strip_headers and _is_header_footer(tb, page_rect.height):
                        continue

                    ep.blocks.append(tb)

        # Extract tables with pdfplumber
        with pdfplumber.open(str(path)) as plumber_doc:
            if page_idx < len(plumber_doc.pages):
                tables = plumber_doc.pages[page_idx].extract_tables()
                if tables:
                    ep.tables = tables

        result.pages.append(ep)

    doc.close()
    return result
