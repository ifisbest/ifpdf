from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ifpdf.pagemap import format_page_comment

if TYPE_CHECKING:
    from ifpdf.extractor import ExtractedDocument, ExtractedPage, TextBlock
    from ifpdf.layout import Section


def _escape_md(text: str) -> str:
    """Escape Markdown special characters."""
    chars = ["\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", "!", "|"]
    for ch in chars:
        text = text.replace(ch, "\\" + ch)
    return text


def _format_table(table: list[list[str | None]]) -> str:
    """Convert a pdfplumber table into a Markdown table."""
    if not table or not table[0]:
        return ""

    # Normalize cells
    rows = []
    for row in table:
        cells = [cell.strip().replace("\n", " ") if cell else "" for cell in row]
        rows.append(cells)

    if not rows:
        return ""

    col_count = max(len(r) for r in rows)

    # Pad short rows
    for row in rows:
        while len(row) < col_count:
            row.append("")

    lines = []
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _is_list_item(text: str) -> tuple[bool, int, str]:
    """Detect if text is a list item. Returns (is_list, indent_level, content)."""
    # Numbered list: "1. ", "(a) ", etc.
    numbered = re.match(r"^(\s*)(\d+\.|[a-zA-Z]\.|\([\da-zA-Z]\))\s+(.*)", text)
    if numbered:
        indent = len(numbered.group(1)) // 4
        return True, indent, numbered.group(3)

    # Bullet list: "- ", "* ", "• "
    bullet = re.match(r"^(\s*)[-*•]\s+(.*)", text)
    if bullet:
        indent = len(bullet.group(1)) // 4
        return True, indent, bullet.group(2)

    return False, 0, text


def format_page_blocks(blocks: list[TextBlock]) -> str:
    """Format a list of text blocks into clean Markdown."""
    lines: list[str] = []
    in_code_block = False

    for i, block in enumerate(blocks):
        text = block.text.strip()
        if not text:
            continue

        # Skip standalone page numbers
        if re.match(r"^\d+$", text) and len(text) <= 3:
            continue

        # Detect list items
        is_list, _, content = _is_list_item(text)
        if is_list:
            lines.append(text)
            continue

        # Try to detect code blocks by monospace font or indentation pattern
        if block.is_bold and block.font_size < 10:
            # Could be code
            pass

        lines.append(text)

    # Join paragraphs
    result: list[str] = []
    buf: list[str] = []

    for line in lines:
        if line.startswith(("| ", "- ", "* ", "• ", "1. ", "2. ", "3. ")):
            if buf:
                result.append(" ".join(buf))
                buf = []
            result.append(line)
        else:
            buf.append(line)

    if buf:
        result.append(" ".join(buf))

    return "\n\n".join(result)


def format_document(
    doc: ExtractedDocument,
    include_metadata: bool = True,
    include_tables: bool = True,
    content_starts_at: int = 1,
    publisher: str = "",
    year: str = "",
    isbn: str = "",
) -> str:
    """Format an entire extracted document as Markdown.

    Args:
        doc: The extracted document.
        include_metadata: Whether to include the metadata header.
        include_tables: Whether to include extracted tables.
        content_starts_at: 1-based PDF page number where the main content starts.
        publisher: Publisher name for metadata header.
        year: Publication year for metadata header.
        isbn: ISBN for metadata header.
    """
    lines: list[str] = []

    # Metadata header matching PRD style
    if include_metadata:
        title = doc.title or Path(doc.filepath).stem
        lines.append(f"# {title}")
        lines.append("")
        meta_items: list[tuple[str, str]] = []
        if doc.author:
            meta_items.append(("作者", doc.author))
        if publisher:
            meta_items.append(("出版社", publisher))
        if year:
            meta_items.append(("出版年", year))
        if isbn:
            meta_items.append(("ISBN", isbn))
        meta_items.append(("总页数", str(doc.page_count)))
        meta_items.append(("OCR日期", datetime.now().strftime("%Y-%m-%d")))
        if content_starts_at > 1:
            meta_items.append(("正文起始页", f"{content_starts_at} (PDF页)"))

        for label, value in meta_items:
            lines.append(f"**{label}**: {value}")
        lines.append("")
        lines.append("---")
        lines.append("")

    for page in doc.pages:
        if len(doc.pages) > 1:
            lines.append(format_page_comment(page.page_num, content_starts_at))

        page_lines: list[str] = []
        body_buf: list[str] = []

        def _flush_body() -> None:
            nonlocal body_buf
            if body_buf:
                merged = _merge_body_lines(body_buf)
                if merged:
                    page_lines.append(merged)
                body_buf = []

        for block in page.blocks:
            if block.block_type.startswith("heading_"):
                _flush_body()
                level = int(block.block_type.split("_")[1])
                prefix = "#" * level
                page_lines.append(f"{prefix} {block.text.strip()}")
                continue

            text = block.text.strip()
            if not text:
                continue
            # Skip standalone page numbers
            if re.match(r"^\d+$", text) and len(text) <= 3:
                continue
            body_buf.append(text)

        _flush_body()

        # Merge page lines with paragraph handling
        formatted = _finalize_page_lines(page_lines)
        if formatted:
            lines.append(formatted)

        # Tables
        if include_tables and page.tables:
            for table in page.tables:
                md_table = _format_table(table)
                if md_table:
                    lines.append("\n" + md_table + "\n")

    return "\n".join(lines)


def format_sections(sections: list[Section]) -> str:
    """Format grouped sections into Markdown."""
    lines: list[str] = []

    for section in sections:
        if section.heading:
            prefix = "#" * max(1, min(section.level, 6))
            lines.append(f"\n{prefix} {section.heading}\n")

        text = "\n".join(b.text for b in section.blocks)
        text = _merge_paragraphs(text)
        if text.strip():
            lines.append(text)

    return "\n".join(lines)


def _merge_body_lines(lines: list[str]) -> str:
    """Merge body text lines into proper paragraphs, handling list items."""
    result: list[str] = []
    buf: list[str] = []
    in_list = False

    def _flush_buf() -> None:
        nonlocal buf
        if buf:
            result.append(" ".join(buf))
            buf = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            _flush_buf()
            continue

        # Detect list items
        is_list_item = bool(re.match(r"^[-*•]\s+", stripped))
        is_numbered = bool(re.match(r"^\d+\.\s+", stripped))

        if is_list_item or is_numbered:
            _flush_buf()
            result.append(stripped)
            in_list = True
            continue

        # If current line is just "•" or "-" (bullet separated from content),
        # merge with next line
        if stripped in ("•", "-", "*") and not in_list:
            buf.append(stripped)
            continue

        # Check if previous buffer ended with a bullet
        if buf and buf[-1].strip() in ("•", "-", "*"):
            buf.append(stripped)
            result.append(" ".join(buf))
            buf = []
            in_list = True
            continue

        in_list = False

        # Short line likely ends a paragraph
        if len(stripped) < 50 and not stripped.endswith(("-", ",", ";", ":", "、")):
            buf.append(stripped)
            _flush_buf()
            continue

        buf.append(stripped)

    _flush_buf()
    return "\n\n".join(result)


def _finalize_page_lines(page_lines: list[str]) -> str:
    """Clean up and join page lines, ensuring proper spacing."""
    cleaned: list[str] = []
    for line in page_lines:
        if line.startswith("#"):
            cleaned.append("\n" + line + "\n")
        else:
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def _merge_paragraphs(text: str) -> str:
    """Merge broken lines into proper paragraphs."""
    lines = text.split("\n")
    result: list[str] = []
    buf: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buf:
                result.append(" ".join(buf))
                buf = []
            continue

        # Don't merge headings or list items or table rows
        if stripped.startswith(("#", "|", "-", "*", "•", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "0.")):
            if buf:
                result.append(" ".join(buf))
                buf = []
            result.append(stripped)
            continue

        # Short line might be end of paragraph
        if len(line) < 50 and not line.endswith(("-", ",", ";", ":")):
            buf.append(stripped)
            if buf:
                result.append(" ".join(buf))
                buf = []
            continue

        buf.append(stripped)

    if buf:
        result.append(" ".join(buf))

    return "\n\n".join(result)
