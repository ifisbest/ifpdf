"""Metadata extraction from filenames and interactive completion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BookMetadata:
    """Structured metadata for a PDF document."""

    title: str = ""
    author: str = ""
    publisher: str = ""
    year: str = ""
    isbn: str = ""
    content_starts_at: int = 1

    def is_complete(self) -> bool:
        return bool(self.title and self.author)


def _clean_publisher(raw: str) -> str:
    """Clean up publisher strings like '北京市：北京大学出版社'."""
    raw = raw.strip()
    # Remove location prefix like "北京市："
    if "：" in raw or ":" in raw:
        raw = re.split(r"[：:]", raw, 1)[-1]
    # Remove trailing location info in parentheses
    raw = re.sub(r"[（(].*?[）)]", "", raw)
    return raw.strip()


def _extract_year(text: str) -> str:
    """Extract a 4-digit year from text."""
    # Use lookahead/lookbehind that works with both word boundaries and CJK characters
    match = re.search(r"(?:^|[^\d])(19\d{2}|20\d{2})(?:[^\d]|$)", text)
    return match.group(1) if match else ""


def _extract_isbn(text: str) -> str:
    """Extract ISBN-10 or ISBN-13 from text."""
    # ISBN-13 (allow surrounding by non-alphanumeric chars like _ -)
    match = re.search(r"(?:^|[^A-Za-z0-9])(97[89]\d{10})(?:[^A-Za-z0-9]|$)", text)
    if match:
        return match.group(1)
    # ISBN-10
    match = re.search(r"(?:^|[^A-Za-z0-9])(\d{9}[\dXx])(?:[^A-Za-z0-9]|$)", text)
    if match:
        return match.group(1)
    return ""


def parse_filename(filename: str) -> BookMetadata:
    """Parse metadata from a PDF filename.

    Handles common naming conventions from Anna's Archive and similar sources:
        中国古代小说史叙论-_刘勇强著_2007_--_北京市：北京大学出版社_--_9787301122303
    """
    stem = Path(filename).stem
    meta = BookMetadata()

    # Try ISBN first (works anywhere in the string)
    meta.isbn = _extract_isbn(stem)

    # Split by common separators: _ , -- , - , 《》
    # First, protect the ISBN if found
    working = stem
    if meta.isbn:
        working = working.replace(meta.isbn, "")

    # Split by strong separators like "_--_" or " -- " or "__"
    parts = re.split(r"_--_| -- |__|_-_", working)
    if len(parts) == 1:
        # Fallback to single underscores
        parts = [p.strip("_- ") for p in working.split("_") if p.strip("_- ")]

    if not parts:
        meta.title = stem.strip()
        return meta

    # Heuristic: first part is usually the title, but may still contain separators
    title_candidate = parts[0].strip("_- 《》")
    # Further split on mixed separators to get the cleanest title
    title_fragments = [f.strip("_- 《》") for f in re.split(r"[_\-]", title_candidate) if f.strip("_- 《》")]
    if title_fragments:
        meta.title = title_fragments[0]
    else:
        meta.title = title_candidate

    # Try to find author/year in the first part first (e.g. "书名-_作者著_年份")
    # This is more reliable than parts[1] which may be publisher info
    if len(title_fragments) > 1:
        for frag in title_fragments[1:]:
            frag = frag.strip()
            if not meta.author and re.search(r"[著编撰译]$", frag):
                author_clean = re.sub(r"[著编撰译主编]+$", "", frag).strip()
                if author_clean and len(author_clean) < 50:
                    meta.author = author_clean
            if not meta.year:
                meta.year = _extract_year(frag)

    # Fallback: second part may contain author
    if not meta.author and len(parts) > 1:
        author_part = parts[1].strip("_- ")
        # Skip if it looks like publisher info
        if not ("出版社" in author_part or "书局" in author_part or "出版" in author_part or len(author_part) > 30):
            # Remove suffixes like "著", "编", "译", "主编"
            author_clean = re.sub(r"[著编撰译主编]+$", "", author_part).strip()
            if author_clean and len(author_clean) < 50:
                meta.author = author_clean

    # Look for year and publisher in remaining parts
    for part in parts[1:]:
        part = part.strip("_- ")
        if not part:
            continue
        if not meta.year:
            meta.year = _extract_year(part)
        if not meta.publisher and len(part) > 3:
            # Exclude author-like parts and pure years
            if not re.match(r"^\d{4}$", part) and len(part) < 80:
                # If it looks like a publisher string
                if "出版社" in part or "书局" in part or "出版" in part or "：" in part or ":" in part:
                    meta.publisher = _clean_publisher(part)

    return meta


def interactive_complete(meta: BookMetadata) -> BookMetadata:
    """Interactively prompt the user for missing metadata fields."""
    import sys

    def _ask(label: str, default: str) -> str:
        prompt = f"{label}"
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        try:
            value = input(prompt).strip()
        except EOFError:
            # Non-interactive environment
            value = ""
        return value if value else default

    print("\n请确认或补全文献信息：", file=sys.stderr)
    meta.title = _ask("书名", meta.title)
    meta.author = _ask("作者", meta.author)
    meta.publisher = _ask("出版社", meta.publisher)
    meta.year = _ask("出版年", meta.year)
    meta.isbn = _ask("ISBN", meta.isbn)

    content_default = str(meta.content_starts_at) if meta.content_starts_at > 1 else ""
    cs = _ask("正文起始页（PDF页号）", content_default)
    if cs.isdigit():
        meta.content_starts_at = int(cs)

    return meta
