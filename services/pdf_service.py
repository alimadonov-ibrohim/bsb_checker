"""
PDF Service — split multi-page PDFs into images for Gemini processing.
"""
import os
import fitz  # PyMuPDF
import logging
from pathlib import Path
from typing import List, Tuple
from PIL import Image
import io

from services.paths import temp_dir as default_temp_dir

logger = logging.getLogger(__name__)


class PDFService:
    def __init__(self, temp_dir: str | None = None):
        self.temp_dir = Path(temp_dir) if temp_dir else default_temp_dir()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_page_count(self, pdf_path: str) -> int:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count

    def render_page_to_image(
        self,
        pdf_path: str,
        page_index: int,
        output_path: str,
        dpi: int = 200,
    ) -> str:
        """Render a single PDF page to PNG image."""
        doc = fitz.open(pdf_path)
        if page_index < 0 or page_index >= len(doc):
            doc.close()
            raise IndexError(f"Page {page_index} out of range (0-{len(doc)-1})")

        page = doc[page_index]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(output_path)
        doc.close()
        return output_path

    def split_pdf_to_images(
        self,
        pdf_path: str,
        job_id: int,
        dpi: int = 180,
    ) -> List[str]:
        """
        Convert every page of PDF to PNG images.
        Returns list of image file paths.
        """
        doc = fitz.open(pdf_path)
        total = len(doc)
        image_paths = []

        job_dir = self.temp_dir / f"job_{job_id}"
        job_dir.mkdir(parents=True, exist_ok=True)

        for i in range(total):
            out_path = str(job_dir / f"page_{i:04d}.png")
            page = doc[i]
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pix.save(out_path)
            image_paths.append(out_path)

        doc.close()
        logger.info(f"Split PDF {pdf_path} into {total} images for job {job_id}")
        return image_paths

    def is_valid_pdf(self, path: str) -> bool:
        try:
            doc = fitz.open(path)
            ok = len(doc) > 0
            doc.close()
            return ok
        except Exception:
            return False

    def cleanup_job(self, job_id: int) -> None:
        job_dir = self.temp_dir / f"job_{job_id}"
        if job_dir.exists():
            for f in job_dir.iterdir():
                try:
                    f.unlink()
                except Exception:
                    pass
            try:
                job_dir.rmdir()
            except Exception:
                pass
