from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ifpdf.extractor import ExtractedDocument, ExtractedPage, TextBlock


@dataclass
class LayoutConfig:
    """Tunable parameters for layout analysis."""

    heading_size_ratio: float = 1.3
    heading_min_size: float = 12.0
    bold_is_heading: bool = True
    body_font_tolerance: float = 0.5
    min_heading_length: int = 3
    max_heading_length: int = 200


@dataclass
class Section:
    """A semantic section of the document."""

    heading: str = ""
    level: int = 0
    blocks: list[TextBlock] = field(default_factory=list)


def _detect_body_font_size(page: ExtractedPage) -> float:
    """Find the most common font size on a page (assumed to be body text)."""
    sizes = [b.font_size for b in page.blocks if b.font_size > 6]
    if not sizes:
        return 11.0
    counter = Counter(sizes)
    # When ties, pick the smallest (body text is typically smaller than headings)
    most_common = counter.most_common()
    max_count = most_common[0][1]
    candidates = [size for size, count in most_common if count == max_count]
    return min(candidates)


def _is_heading(block: TextBlock, body_size: float, config: LayoutConfig) -> bool:
    """Determine if a text block is a heading."""
    import re

    text = block.text.strip()

    # Length filters
    if len(text) < config.min_heading_length:
        return False
    if len(text) > config.max_heading_length:
        return False

    # Skip list markers
    if text in ("•", "-", "*") or re.match(r"^[-*•]\s", text):
        return False

    # Size-based heading detection (strong signal)
    if block.font_size >= max(body_size * config.heading_size_ratio, config.heading_min_size):
        # Reject if it looks like a sentence (too many punctuations)
        punct_ratio = sum(1 for c in text if c in "，。、；：！？,.;:!?") / max(len(text), 1)
        if punct_ratio > 0.3:
            return False
        return True

    # Bold text at same size: very conservative
    if config.bold_is_heading and block.is_bold and block.font_size >= body_size:
        # Must be short to be a heading
        if len(text) > 60:
            return False
        # Must not contain sentence-like punctuation
        if any(c in text for c in "，。、；：！？"):
            return False
        # Must not look like a list item or label
        if re.match(r"^\d+\.\s+", text) or ":" in text[-1]:
            return False
        return True

    return False


def _heading_level(block: TextBlock, body_size: float) -> int:
    """Determine heading level (1-4) based on font size."""
    ratio = block.font_size / body_size if body_size > 0 else 1.0

    if ratio >= 1.8:
        return 1
    if ratio >= 1.5:
        return 2
    if ratio >= 1.3:
        return 3
    if block.is_bold and ratio >= 1.1:
        return 4
    return 2  # default for detected headings


def analyze_layout(
    doc: ExtractedDocument,
    config: LayoutConfig | None = None,
) -> ExtractedDocument:
    """Analyze document layout and tag each block with its semantic type.

    Modifies the document in-place, setting block.block_type and
    grouping blocks into sections.
    """
    if config is None:
        config = LayoutConfig()

    for page in doc.pages:
        body_size = _detect_body_font_size(page)

        for block in page.blocks:
            if _is_heading(block, body_size, config):
                block.block_type = f"heading_{_heading_level(block, body_size)}"
            else:
                block.block_type = "body"

    return doc


def group_into_sections(doc: ExtractedDocument) -> list[Section]:
    """Group blocks into sections separated by headings."""
    sections: list[Section] = []
    current = Section()

    for page in doc.pages:
        for block in page.blocks:
            if block.block_type.startswith("heading_"):
                if current.blocks or current.heading:
                    sections.append(current)
                level = int(block.block_type.split("_")[1])
                current = Section(heading=block.text, level=level)
            else:
                current.blocks.append(block)

    if current.blocks or current.heading:
        sections.append(current)

    return sections
