"""Seiten eines Plans (PDF oder Bild) als Bild laden - rein lokal."""

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass
class RenderedPage:
    image: Image.Image
    page_index: int
    page_count: int
    dpi: int


def render_page(path: str, page_index: int = 0, dpi: int = 150) -> RenderedPage:
    suffix = Path(path).suffix.lower()

    if suffix == ".pdf":
        pdf = pdfium.PdfDocument(path)
        try:
            page_count = len(pdf)
            page = pdf[page_index]
            scale = dpi / 72.0
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            return RenderedPage(image=image, page_index=page_index, page_count=page_count, dpi=dpi)
        finally:
            pdf.close()

    if suffix in IMAGE_SUFFIXES:
        image = Image.open(path).convert("RGB")
        return RenderedPage(image=image, page_index=0, page_count=1, dpi=dpi)

    raise ValueError(f"Nicht unterstuetztes Dateiformat: {suffix}")
