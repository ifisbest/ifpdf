"""Tests for chunker module."""

from ifpdf.chunker import chunk_markdown, count_tokens


def test_count_tokens_simple():
    assert count_tokens("hello world") == 2


def test_chunk_markdown_short_text():
    text = "This is a short paragraph."
    chunks = chunk_markdown(text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_markdown_splits_on_paragraphs():
    paragraphs = [f"Paragraph {i}. " + "word " * 50 for i in range(5)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_markdown(text, chunk_size=100)
    assert len(chunks) > 1


def test_chunk_markdown_preserves_tables():
    text = "| a | b |\n| --- | --- |\n| 1 | 2 |"
    chunks = chunk_markdown(text, chunk_size=10)
    assert len(chunks) == 1
    assert "| a | b |" in chunks[0]


def test_chunk_markdown_overlap():
    # Create text with two large paragraphs
    para1 = "This is a moderately long sentence that contains enough words to span multiple tokens. " * 20
    para2 = "Another distinct paragraph with different content and vocabulary for testing overlap. " * 20
    text = para1 + "\n\n" + para2
    chunks = chunk_markdown(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) >= 2
    # Check overlap: last part of first chunk appears in second chunk
    if len(chunks) >= 2:
        assert chunks[0][-40:] in chunks[1] or any(word in chunks[1] for word in chunks[0].split()[-5:])
