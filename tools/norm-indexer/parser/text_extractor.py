from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class TextExtractionError(RuntimeError):
    pass


def extract_pdf_text(pdf_path: Path, ocr_source: bool = False) -> str:
    """Extract text from a PDF using pdftotext -layout (poppler-utils).

    -layout preserves the left indentation that the clause segmenters rely on
    to tell real headings apart from body text and table-of-contents lines.

    ocr_source is informational only for now: documents produced from OCR
    (large scanned standards such as EN40000 1-2/1-3) are expected to have a
    higher segmentation error rate and should be flagged for manual review
    downstream (see provenanceClass in the IR), not silently trusted.
    """
    if shutil.which("pdftotext") is None:
        raise TextExtractionError("pdftotext (poppler-utils) not found on PATH")
    if not pdf_path.exists():
        raise TextExtractionError(f"PDF source not found: {pdf_path}")
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise TextExtractionError(f"pdftotext failed for {pdf_path}: {stderr}")
    return result.stdout.decode("utf-8", errors="replace")
