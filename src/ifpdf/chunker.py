from __future__ import annotations

import tiktoken


def get_tokenizer(model: str = "cl100k_base") -> tiktoken.Encoding:
    """Get a tiktoken tokenizer. cl100k_base is used by GPT-4, GPT-3.5-turbo, text-embedding-ada-002."""
    return tiktoken.get_encoding(model)


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in a text string."""
    enc = get_tokenizer(model)
    return len(enc.encode(text))


def chunk_markdown(
    markdown: str,
    chunk_size: int = 4000,
    chunk_overlap: int = 200,
    model: str = "cl100k_base",
) -> list[str]:
    """Split Markdown text into token-sized chunks.

    Splits on paragraph boundaries first, then falls back to sentence boundaries
    if a paragraph is too large. Never splits in the middle of a Markdown table.

    Args:
        markdown: The full Markdown text.
        chunk_size: Maximum tokens per chunk.
        chunk_overlap: Tokens to overlap between chunks for continuity.
        model: Tiktoken encoding name.

    Returns:
        List of Markdown chunks.
    """
    enc = get_tokenizer(model)

    # Split into paragraphs, preserving table blocks as atomic units
    paragraphs = _split_into_paragraphs(markdown)

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = len(enc.encode(para))

        if para_tokens > chunk_size:
            # Paragraph itself is too big; flush current chunk and split para
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_tokens = 0

            sub_chunks = _split_large_paragraph(para, chunk_size, chunk_overlap, enc)
            chunks.extend(sub_chunks)
            continue

        if current_tokens + para_tokens > chunk_size and current:
            chunks.append("\n\n".join(current))
            # Keep overlap: include last paragraph(s) that fit within overlap budget
            overlap_budget = chunk_overlap
            overlap_paras: list[str] = []
            for p in reversed(current):
                pt = len(enc.encode(p))
                if pt <= overlap_budget:
                    overlap_paras.insert(0, p)
                    overlap_budget -= pt
                else:
                    break
            current = overlap_paras
            current_tokens = sum(len(enc.encode(p)) for p in current)

        current.append(para)
        current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs, keeping tables as atomic units."""
    lines = text.split("\n")
    paragraphs: list[str] = []
    buf: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("|"):
            in_table = True
            buf.append(line)
            continue

        if in_table:
            if stripped.startswith("|"):
                buf.append(line)
            else:
                paragraphs.append("\n".join(buf))
                buf = []
                in_table = False
                if stripped:
                    buf.append(line)
            continue

        if not stripped:
            if buf:
                paragraphs.append("\n".join(buf))
                buf = []
            continue

        buf.append(line)

    if buf:
        paragraphs.append("\n".join(buf))

    return [p for p in paragraphs if p.strip()]


def _split_large_paragraph(
    paragraph: str,
    chunk_size: int,
    chunk_overlap: int,
    enc: tiktoken.Encoding,
) -> list[str]:
    """Split an oversized paragraph by sentences."""
    import re

    # Don't split tables — return as-is even if oversized
    if "\n|" in paragraph or paragraph.strip().startswith("|"):
        return [paragraph]

    # Simple sentence split
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = len(enc.encode(sent))
        if sent_tokens > chunk_size:
            # Even a single sentence is too long; split by characters
            if current:
                chunks.append(" ".join(current))
                current = []
                current_tokens = 0
            chunks.extend(_split_by_chars(sent, chunk_size, enc))
            continue

        if current_tokens + sent_tokens > chunk_size and current:
            chunks.append(" ".join(current))
            # overlap
            overlap_budget = chunk_overlap
            overlap_sents: list[str] = []
            for s in reversed(current):
                st = len(enc.encode(s))
                if st <= overlap_budget:
                    overlap_sents.insert(0, s)
                    overlap_budget -= st
                else:
                    break
            current = overlap_sents
            current_tokens = sum(len(enc.encode(s)) for s in current)

        current.append(sent)
        current_tokens += sent_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks


def _split_by_chars(text: str, chunk_size: int, enc: tiktoken.Encoding) -> list[str]:
    """Last resort: split by approximate character count."""
    chars_per_token = max(1, len(text) // max(1, len(enc.encode(text))))
    max_chars = chunk_size * chars_per_token
    parts: list[str] = []
    for i in range(0, len(text), max_chars):
        parts.append(text[i : i + max_chars])
    return parts
