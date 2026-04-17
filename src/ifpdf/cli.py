"""CLI entry point for ifpdf."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ifpdf.chunker import chunk_markdown, count_tokens
from ifpdf.extractor import extract_pdf
from ifpdf.formatter import format_document
from ifpdf.layout import analyze_layout
from ifpdf.metadata import BookMetadata, interactive_complete, parse_filename
from ifpdf.ocr_engine import is_scanned_pdf, ocr_pdf, validate_engine
from ifpdf.pagemap import format_chunk_comment
from ifpdf.utils import copy_to_clipboard, parse_page_range, write_output

app = typer.Typer(
    name="ifpdf",
    help="Convert PDFs into AI-friendly Markdown",
    no_args_is_help=True,
)

console = Console(stderr=True)


def version_callback(value: bool) -> None:
    if value:
        from ifpdf import __version__
        console.print(f"ifpdf {__version__}")
        raise typer.Exit()


@app.command()
def ocr(
    filepath: str = typer.Argument(..., help="Path to the PDF file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy output to clipboard"),
    pages: Optional[str] = typer.Option(None, "--pages", "-p", help="Page range, e.g. '1-10' or '5'"),
    content_starts_at: int = typer.Option(1, "--content-starts-at", help="PDF page number where main content starts (正文起始页)"),
    chunk_size: Optional[int] = typer.Option(None, "--chunk-size", "-k", help="Max tokens per chunk (e.g. 4000)"),
    no_metadata: bool = typer.Option(False, "--no-metadata", help="Omit metadata header"),
    no_tables: bool = typer.Option(False, "--no-tables", help="Skip table extraction"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactively confirm/complement metadata"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of parallel OCR processes (scan-only)"),
    engine: str = typer.Option("tesseract", "--engine", "-e", help="OCR engine: tesseract or paddleocr"),
    lang: str = typer.Option("chi_sim+eng", "--lang", "-l", help="Tesseract language pack"),
    version: Optional[bool] = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True),
) -> None:
    """Convert a PDF (text-layer or scanned) to AI-friendly Markdown."""
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red]Error: file not found: {filepath}[/red]")
        raise typer.Exit(1)

    # Parse metadata from filename
    meta = parse_filename(path.name)
    if interactive:
        meta = interactive_complete(meta)

    # Allow CLI flags to override parsed metadata
    if content_starts_at == 1 and meta.content_starts_at > 1:
        content_starts_at = meta.content_starts_at

    page_range = parse_page_range(pages)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=quiet,
    ) as progress:
        # Detect scanned vs text-layer
        scanned = is_scanned_pdf(path)

        if scanned:
            progress.update(progress.add_task("Detecting scanned PDF...", total=None), description="Scan detected, running OCR...")
            _engine = validate_engine(engine)

            def _progress_cb(done: int, total: int) -> None:
                if not quiet:
                    progress.update(task, description=f"OCR 第 {done}/{total} 页...")

            task = progress.add_task("OCR...", total=None)
            ocr_results = ocr_pdf(
                path,
                engine=_engine,
                lang=lang,
                workers=workers,
                page_range=page_range,
                progress_callback=_progress_cb,
            )

            # Build a fake ExtractedDocument from OCR results
            from ifpdf.extractor import ExtractedDocument, ExtractedPage, TextBlock

            doc = ExtractedDocument(
                filepath=str(path),
                title=meta.title or path.stem,
                author=meta.author,
                page_count=len(ocr_results),
            )
            for page_num, text in ocr_results:
                ep = ExtractedPage(page_num=page_num, width=0, height=0)
                if text:
                    ep.blocks.append(TextBlock(
                        text=text,
                        page_num=page_num,
                        x0=0, y0=0, x1=0, y1=0,
                        font_size=11.0,
                        is_bold=False,
                        is_italic=False,
                        block_type="body",
                    ))
                doc.pages.append(ep)

            progress.update(task, description="Analyzing layout...")
            doc = analyze_layout(doc)
        else:
            task = progress.add_task("Extracting PDF...", total=None)
            doc = extract_pdf(path, page_range=page_range)

            progress.update(task, description="Analyzing layout...")
            doc = analyze_layout(doc)

            # Override metadata from filename if PDF metadata is empty
            if not doc.title and meta.title:
                doc.title = meta.title
            if not doc.author and meta.author:
                doc.author = meta.author

        progress.update(task, description="Formatting Markdown...")
        markdown = format_document(
            doc,
            include_metadata=not no_metadata,
            include_tables=not no_tables,
            content_starts_at=content_starts_at,
            publisher=meta.publisher,
            year=meta.year,
            isbn=meta.isbn,
        )

    # Chunking
    if chunk_size and chunk_size > 0:
        chunks = chunk_markdown(markdown, chunk_size=chunk_size)
        if not quiet:
            total_tokens = count_tokens(markdown)
            console.print(
                f"[green]Converted {doc.page_count} pages -> {len(chunks)} chunks"
                f" ({total_tokens} tokens total)[/green]"
            )
        if output and len(chunks) > 1:
            base = Path(output).stem
            suffix = Path(output).suffix or ".md"
            parent = Path(output).parent
            for i, chunk in enumerate(chunks, 1):
                chunk_path = parent / f"{base}_chunk{i}{suffix}"
                chunk_path.write_text(chunk, encoding="utf-8")
                if not quiet:
                    console.print(f"  Wrote {chunk_path}")
        elif output:
            write_output(chunks[0], output)
        else:
            for i, chunk in enumerate(chunks, 1):
                sep = f"\n<!-- === CHUNK {i}/{len(chunks)} === -->\n"
                sys.stdout.write(sep)
                sys.stdout.write(chunk)
                sys.stdout.write("\n")
    else:
        if not quiet:
            total_tokens = count_tokens(markdown)
            console.print(
                f"[green]Converted {doc.page_count} pages -> Markdown"
                f" ({total_tokens} tokens)[/green]"
            )
        write_output(markdown, output)

    if copy:
        if chunk_size and len(chunks) > 1:  # type: ignore[has-type]
            copy_to_clipboard(chunks[0])
            if not quiet:
                console.print("[blue]Copied first chunk to clipboard[/blue]")
        else:
            copy_to_clipboard(markdown)
            if not quiet:
                console.print("[blue]Copied to clipboard[/blue]")


# Keep 'convert' as an alias for backward compatibility
@app.command(hidden=True)
def convert(
    ctx: typer.Context,
    filepath: str = typer.Argument(..., help="Path to the PDF file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy output to clipboard"),
    pages: Optional[str] = typer.Option(None, "--pages", "-p", help="Page range, e.g. '1-10' or '5'"),
    chunk_size: Optional[int] = typer.Option(None, "--chunk-size", "-k", help="Max tokens per chunk (e.g. 4000)"),
    no_metadata: bool = typer.Option(False, "--no-metadata", help="Omit metadata header"),
    no_tables: bool = typer.Option(False, "--no-tables", help="Skip table extraction"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
) -> None:
    """Alias for 'ocr'. Convert a PDF to AI-friendly Markdown."""
    ctx.invoke(
        ocr,
        filepath=filepath,
        output=output,
        copy=copy,
        pages=pages,
        chunk_size=chunk_size,
        no_metadata=no_metadata,
        no_tables=no_tables,
        quiet=quiet,
    )


@app.command()
def batch(
    directory: str = typer.Argument(..., help="Directory containing PDF files"),
    output: str = typer.Option("./output", "--output", "-o", help="Output directory"),
    workers: int = typer.Option(1, "--workers", "-w", help="Parallel OCR workers per file"),
    engine: str = typer.Option("tesseract", "--engine", "-e", help="OCR engine"),
    lang: str = typer.Option("chi_sim+eng", "--lang", "-l", help="Tesseract language"),
    chunk_size: Optional[int] = typer.Option(None, "--chunk-size", "-k", help="Max tokens per chunk"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
) -> None:
    """Batch convert all PDFs in a directory."""
    src = Path(directory)
    dst = Path(output)
    if not src.exists() or not src.is_dir():
        console.print(f"[red]Error: directory not found: {directory}[/red]")
        raise typer.Exit(1)

    dst.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(src.glob("*.pdf"))
    if not pdfs:
        console.print("[yellow]No PDF files found.[/yellow]")
        raise typer.Exit(0)

    error_log = dst / "ifpdf_errors.log"
    errors: list[str] = []

    for pdf in pdfs:
        if not quiet:
            console.print(f"Processing [cyan]{pdf.name}[/cyan]...")
        try:
            meta = parse_filename(pdf.name)
            scanned = is_scanned_pdf(pdf)

            if scanned:
                _engine = validate_engine(engine)
                ocr_results = ocr_pdf(pdf, engine=_engine, lang=lang, workers=workers)
                from ifpdf.extractor import ExtractedDocument, ExtractedPage, TextBlock
                doc = ExtractedDocument(
                    filepath=str(pdf),
                    title=meta.title or pdf.stem,
                    author=meta.author,
                    page_count=len(ocr_results),
                )
                for page_num, text in ocr_results:
                    ep = ExtractedPage(page_num=page_num, width=0, height=0)
                    if text:
                        ep.blocks.append(TextBlock(
                            text=text, page_num=page_num,
                            x0=0, y0=0, x1=0, y1=0,
                            font_size=11.0, block_type="body",
                        ))
                    doc.pages.append(ep)
                doc = analyze_layout(doc)
            else:
                doc = extract_pdf(pdf)
                doc = analyze_layout(doc)
                if not doc.title and meta.title:
                    doc.title = meta.title
                if not doc.author and meta.author:
                    doc.author = meta.author

            markdown = format_document(
                doc,
                include_metadata=True,
                include_tables=True,
                publisher=meta.publisher,
                year=meta.year,
                isbn=meta.isbn,
            )

            out_path = dst / f"{pdf.stem}.md"
            if chunk_size and chunk_size > 0:
                chunks = chunk_markdown(markdown, chunk_size=chunk_size)
                if len(chunks) > 1:
                    for i, chunk in enumerate(chunks, 1):
                        chunk_path = dst / f"{pdf.stem}_chunk{i}.md"
                        chunk_path.write_text(chunk, encoding="utf-8")
                    if not quiet:
                        console.print(f"  -> {len(chunks)} chunks")
                else:
                    out_path.write_text(chunks[0], encoding="utf-8")
            else:
                out_path.write_text(markdown, encoding="utf-8")

            if not quiet:
                console.print(f"  [green]OK[/green]")
        except Exception as exc:
            console.print(f"  [red]Failed: {exc}[/red]")
            errors.append(f"{pdf.name}: {exc}")

    if errors:
        error_log.write_text("\n".join(errors), encoding="utf-8")
        console.print(f"[red]{len(errors)} file(s) failed. See {error_log}[/red]")
        raise typer.Exit(1)

    if not quiet:
        console.print(f"[green]Done: {len(pdfs)} file(s) -> {dst}[/green]")


@app.command()
def chunk(
    filepath: str = typer.Argument(..., help="Path to the Markdown file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory or file prefix"),
    chunk_size: int = typer.Option(4000, "--chunk-size", "-k", help="Max tokens per chunk"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
) -> None:
    """Split an existing Markdown file into token-sized chunks."""
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red]Error: file not found: {filepath}[/red]")
        raise typer.Exit(1)

    text = path.read_text(encoding="utf-8")
    chunks = chunk_markdown(text, chunk_size=chunk_size)

    if not quiet:
        total = count_tokens(text)
        console.print(f"[green]Split into {len(chunks)} chunks ({total} tokens total)[/green]")

    if output:
        out_dir = Path(output)
        if out_dir.suffix:
            # Treat as file prefix
            base = out_dir.stem
            suffix = out_dir.suffix or ".md"
            parent = out_dir.parent
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            base = path.stem
            suffix = ".md"
            parent = out_dir

        for i, chunk in enumerate(chunks, 1):
            chunk_path = parent / f"{base}_chunk{i}{suffix}"
            chunk_path.write_text(chunk, encoding="utf-8")
            if not quiet:
                console.print(f"  Wrote {chunk_path}")
    else:
        for i, chunk in enumerate(chunks, 1):
            sep = format_chunk_comment(i, len(chunks), None, None)
            sys.stdout.write(sep)
            sys.stdout.write(chunk)
            sys.stdout.write("\n")


@app.command()
def info(
    filepath: str = typer.Argument(..., help="Path to the PDF file"),
) -> None:
    """Show PDF metadata and structure overview."""
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red]Error: file not found: {filepath}[/red]")
        raise typer.Exit(1)

    doc = extract_pdf(path)
    scanned = is_scanned_pdf(path)
    meta = parse_filename(path.name)

    table = Table(title=f"PDF Info: {path.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Pages", str(doc.page_count))
    table.add_row("Scanned", "Yes" if scanned else "No")
    table.add_row("Title", doc.title or meta.title or "—")
    table.add_row("Author", doc.author or meta.author or "—")
    table.add_row("Publisher", meta.publisher or "—")
    table.add_row("Year", meta.year or "—")
    table.add_row("ISBN", meta.isbn or "—")

    # Count headings
    heading_counts: dict[str, int] = {}
    for page in doc.pages:
        for block in page.blocks:
            if block.block_type.startswith("heading_"):
                heading_counts[block.block_type] = heading_counts.get(block.block_type, 0) + 1

    for level in sorted(heading_counts.keys()):
        table.add_row(f"Headings ({level})", str(heading_counts[level]))

    console.print(table)


if __name__ == "__main__":
    app()
