"""OCR engine wrapper for scanned PDFs."""

from __future__ import annotations

import shutil
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from PIL import Image


def is_scanned_pdf(filepath: str | Path) -> bool:
    """Check whether a PDF has no selectable text layer.

    Heuristic: sample a few pages and check if extractable text is very sparse.
    """
    import fitz

    path = Path(filepath)
    doc = fitz.open(str(path))
    try:
        sample_pages = min(3, len(doc))
        total_chars = 0
        for i in range(sample_pages):
            text = doc[i].get_text().strip()
            total_chars += len(text)
        # If fewer than ~50 chars per sampled page, treat as scanned
        avg_chars = total_chars / max(sample_pages, 1)
        return avg_chars < 50
    finally:
        doc.close()


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _run_tesseract(image_path: str, lang: str = "chi_sim+eng") -> str:
    """Run Tesseract OCR on an image file and return the text."""
    import pytesseract

    try:
        return pytesseract.image_to_string(image_path, lang=lang).strip()
    except Exception as exc:
        return f"[OCR Error: {exc}]"


def _run_paddleocr(image_path: str) -> str:
    """Run PaddleOCR on an image file and return the text."""
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        result = ocr.ocr(image_path, cls=True)
        lines: list[str] = []
        if result and result[0]:
            for line in result[0]:
                if line:
                    lines.append(line[1][0])
        return "\n".join(lines)
    except Exception as exc:
        return f"[PaddleOCR Error: {exc}]"


def ocr_page(
    image: Image.Image,
    engine: str = "tesseract",
    lang: str = "chi_sim+eng",
) -> str:
    """Run OCR on a single PIL Image.

    Args:
        image: PIL Image to OCR.
        engine: "tesseract" or "paddleocr".
        lang: Tesseract language pack (ignored for paddleocr).

    Returns:
        Extracted text string.
    """
    from ifpdf.preprocessor import preprocess_for_ocr

    processed = preprocess_for_ocr(image, grayscale=True, contrast=1.5, denoise=True)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    processed.save(tmp_path, "PNG")

    try:
        if engine == "paddleocr":
            return _run_paddleocr(tmp_path)
        return _run_tesseract(tmp_path, lang=lang)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def ocr_pdf(
    filepath: str | Path,
    engine: str = "tesseract",
    lang: str = "chi_sim+eng",
    dpi: int = 300,
    workers: int = 1,
    page_range: tuple[int, int] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[tuple[int, str]]:
    """OCR an entire PDF and return text per page.

    Args:
        filepath: Path to the scanned PDF.
        engine: OCR engine name.
        lang: Tesseract language.
        dpi: Rendering DPI.
        workers: Number of parallel processes (Tesseract only; PaddleOCR may not be multiprocess-safe).
        page_range: Optional (start, end) 1-based page numbers.
        progress_callback: Optional callable(page_index, total_pages) for progress updates.

    Returns:
        List of (page_num, text) tuples, sorted by page number.
    """
    import fitz
    from PIL import Image

    path = Path(filepath)
    doc = fitz.open(str(path))

    start_page = page_range[0] - 1 if page_range else 0
    end_page = page_range[1] if page_range else len(doc)
    total = end_page - start_page

    # Render selected pages to images first
    images: list[tuple[int, Image.Image]] = []
    for i in range(start_page, min(end_page, len(doc))):
        page = doc[i]
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append((i + 1, img))
    doc.close()

    results: list[tuple[int, str]] = []

    if workers > 1 and engine == "tesseract" and _tesseract_available():
        # Parallel processing with process pool
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(ocr_page, img, engine, lang): page_num
                for page_num, img in images
            }
            for future in as_completed(futures):
                page_num = futures[future]
                text = future.result()
                results.append((page_num, text))
                if progress_callback:
                    progress_callback(len(results), total)
    else:
        for page_num, img in images:
            text = ocr_page(img, engine=engine, lang=lang)
            results.append((page_num, text))
            if progress_callback:
                progress_callback(page_num, total)

    results.sort(key=lambda x: x[0])
    return results


def validate_engine(engine: str) -> str:
    """Validate and normalize OCR engine selection."""
    engine = engine.lower()
    if engine not in ("tesseract", "paddleocr"):
        raise ValueError(f"Unsupported OCR engine: {engine}. Choose 'tesseract' or 'paddleocr'.")

    if engine == "tesseract" and not _tesseract_available():
        raise RuntimeError(
            "Tesseract is not installed or not found in PATH. "
            "Install it via: brew install tesseract tesseract-lang (macOS) or apt install tesseract-ocr-chi-sim (Linux)"
        )

    if engine == "paddleocr":
        try:
            import paddleocr  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "PaddleOCR is not installed. Install it via: pip install paddleocr"
            )

    return engine
