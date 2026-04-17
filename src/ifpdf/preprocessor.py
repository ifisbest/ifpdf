"""Image preprocessing for OCR pipelines."""

from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter


def preprocess_for_ocr(
    image: Image.Image,
    *,
    grayscale: bool = True,
    contrast: float = 1.5,
    sharpness: float = 1.2,
    denoise: bool = True,
    binarize: bool = False,
    threshold: int = 128,
) -> Image.Image:
    """Preprocess an image to improve OCR accuracy.

    Args:
        image: Input PIL Image.
        grayscale: Convert to grayscale.
        contrast: Contrast enhancement factor (1.0 = no change).
        sharpness: Sharpness enhancement factor (1.0 = no change).
        denoise: Apply mild median filter denoising.
        binarize: Convert to pure black/white.
        threshold: Binarization threshold (0-255).

    Returns:
        Preprocessed PIL Image.
    """
    img = image.copy()

    if grayscale and img.mode != "L":
        img = img.convert("L")

    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast)

    if sharpness != 1.0:
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(sharpness)

    if denoise:
        # Mild median filter to reduce speckles without blurring text
        img = img.filter(ImageFilter.MedianFilter(size=3))

    if binarize and img.mode == "L":
        img = img.point(lambda x: 0 if x < threshold else 255, "1")

    return img
