"""Page number mapping: PDF physical pages -> document content pages."""

from __future__ import annotations


def map_page_number(pdf_page: int, content_starts_at: int) -> int | None:
    """Map a PDF physical page number to a content page number.

    Args:
        pdf_page: 1-based physical page number in the PDF.
        content_starts_at: 1-based PDF page where the main content starts.

    Returns:
        The content page number, or None if this is a front-matter page.
    """
    if pdf_page < content_starts_at:
        return None
    return pdf_page - content_starts_at + 1


def format_page_comment(pdf_page: int, content_starts_at: int = 1) -> str:
    """Return a Markdown HTML comment for the given page.

    Front matter is labeled with the physical page number.
    Content pages use Chinese-style "第 X 页" comments.
    """
    content_page = map_page_number(pdf_page, content_starts_at)
    if content_page is None:
        return f"\n<!-- PDF 第 {pdf_page} 页（前言/目录） -->\n"
    return f"\n<!-- 第 {content_page} 页 -->\n"


def format_chunk_comment(chunk_index: int, total_chunks: int, start_page: int | None, end_page: int | None) -> str:
    """Format a chunk separator comment with page range info.

    Args:
        chunk_index: 1-based chunk index.
        total_chunks: Total number of chunks.
        start_page: Content page number where the chunk starts (inclusive).
        end_page: Content page number where the chunk ends (inclusive).
    """
    if start_page is not None and end_page is not None:
        return f"\n<!-- === CHUNK {chunk_index}/{total_chunks}（第 {start_page}-{end_page} 页）=== -->\n"
    return f"\n<!-- === CHUNK {chunk_index}/{total_chunks} === -->\n"
