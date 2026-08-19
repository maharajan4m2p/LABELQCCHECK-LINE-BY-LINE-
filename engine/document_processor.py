"""Document input handling: images and PDF -> page images."""
from pathlib import Path

import cv2
import fitz

from config import PDF_DPI

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS


def is_supported(path_or_name):
    return Path(str(path_or_name)).suffix.lower() in SUPPORTED_EXTENSIONS


def render_document(path, output_dir, dpi=None):
    """Return page records with one image per page."""
    path = Path(path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise ValueError(f"Unable to read image: {path.name}")
        return [{"page": 1, "image_path": path, "source_page": 1}]

    if ext == ".pdf":
        pages = []
        scale = float(dpi or PDF_DPI) / 72.0
        matrix = fitz.Matrix(scale, scale)
        with fitz.open(str(path)) as doc:
            if doc.page_count == 0:
                raise ValueError(f"PDF has no pages: {path.name}")
            for page_number, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                out = output_dir / f"{path.stem}_page_{page_number:03d}.png"
                pix.save(str(out))
                pages.append({
                    "page": page_number,
                    "image_path": out,
                    "source_page": page_number,
                })
        return pages

    raise ValueError(f"Unsupported file type: {path.suffix}")
