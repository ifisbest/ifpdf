"""Tests for image preprocessing."""

from PIL import Image

from ifpdf.preprocessor import preprocess_for_ocr


class TestPreprocess:
    def test_grayscale(self):
        img = Image.new("RGB", (100, 100), color="red")
        out = preprocess_for_ocr(img, grayscale=True)
        assert out.mode == "L"

    def test_no_grayscale(self):
        img = Image.new("RGB", (100, 100), color="red")
        out = preprocess_for_ocr(img, grayscale=False)
        assert out.mode == "RGB"

    def test_binarize(self):
        img = Image.new("L", (100, 100), color=128)
        out = preprocess_for_ocr(img, grayscale=False, binarize=True)
        assert out.mode == "1"
