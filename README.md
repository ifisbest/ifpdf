# ifpdf

Convert PDFs into AI-friendly Markdown.

## Why

PDFs are terrible for AI. Copy-paste gives you mangled text, broken tables, and headers mixed into every paragraph. Existing tools either:

- **pdftotext** — outputs raw text with zero structure
- **Adobe Acrobat** — GUI-only, cannot be automated
- **Marker / Nougat** — 2GB+ models, minutes per page, GPU required
- **Online converters** — privacy risk for sensitive documents

**ifpdf** fills the gap: a lightweight CLI that converts PDFs to clean, structured Markdown in seconds. No models, no cloud, no GUI.

## Install

```bash
pip install ifpdf
```

Or from source:

```bash
git clone https://github.com/yourname/ifpdf.git
cd ifpdf
pip install -e ".[dev]"
```

## Usage

```bash
# Convert a PDF to Markdown (prints to stdout)
ifpdf convert paper.pdf

# Save to file
ifpdf convert paper.pdf -o paper.md

# Copy to clipboard
ifpdf convert paper.pdf --copy

# Only first 10 pages
ifpdf convert book.pdf --pages 1-10

# Split into 4000-token chunks for LLM context limits
ifpdf convert thesis.pdf --chunk-size 4000 -o thesis.md

# Skip metadata header and tables
ifpdf convert report.pdf --no-metadata --no-tables

# Show PDF structure info
ifpdf info paper.pdf
```

## What it does

1. **Extracts text** with PyMuPDF — fast, preserves layout coordinates
2. **Analyzes layout** — detects headings by font size and weight, filters headers/footers
3. **Formats as Markdown** — headings become `#`, tables become `|`, lists become `-`
4. **Chunks by tokens** — splits long documents into LLM-friendly pieces with overlap

## Pipeline

```
PDF → [extractor] → text blocks with coordinates
         ↓
    [layout analyzer] → heading / body / table classification
         ↓
    [formatter] → clean Markdown
         ↓
    [chunker] → token-sized chunks (optional)
```

## Example output

Input: a 15-page academic paper with tables and sections.

Output:

```markdown
# Attention Is All You Need

**Pages**: 15 | **Extracted**: 2026-04-17 21:30

---

## Abstract

The dominant sequence transduction models...

## 1 Introduction

Recurrent neural networks (RNN), long short-term memory (LSTM)...

| Model | BLEU | Parameters |
| --- | --- | --- |
| Transformer (base) | 27.3 | 65M |
| Transformer (big) | 28.4 | 213M |
```

## Architecture

```
ifpdf/
├── cli.py        # Typer CLI interface
├── extractor.py  # PDF text + layout extraction
├── layout.py     # Heading/body classification
├── formatter.py  # Markdown output generation
├── chunker.py    # Token-aware text splitting
└── utils.py      # Clipboard, file I/O helpers
```

## Tech stack

- **Python 3.9+**
- **PyMuPDF** — PDF parsing
- **pdfplumber** — Table extraction
- **typer** — CLI framework
- **rich** — Terminal UI
- **tiktoken** — Token counting

## OCR (optional)

For scanned documents, install with OCR support:

```bash
pip install "ifpdf[ocr]"
```

Requires [Tesseract](https://github.com/tesseract-ocr/tesseract) installed on your system.

## License

MIT
