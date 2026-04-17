"""Utility functions for ifpdf."""

from __future__ import annotations

import sys
from pathlib import Path

import pyperclip
from rich.console import Console

console = Console(stderr=True)


def copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard."""
    try:
        pyperclip.copy(text)
    except Exception as exc:
        console.print(f"[yellow]Warning: could not copy to clipboard: {exc}[/yellow]")


def parse_page_range(pages_str: str | None) -> tuple[int, int] | None:
    """Parse a page range string like '1-10' or '5' into (start, end)."""
    if not pages_str:
        return None
    pages_str = pages_str.strip()
    if "-" in pages_str:
        parts = pages_str.split("-", 1)
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        return (start, end)
    else:
        page = int(pages_str.strip())
        return (page, page)


def write_output(text: str, output_path: str | None) -> None:
    """Write text to file or stdout."""
    if output_path:
        path = Path(output_path)
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
