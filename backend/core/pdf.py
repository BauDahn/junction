from pathlib import Path

import pymupdf as fitz


def read_pdf(path, max_pages=15, width=1024):
    doc = fitz.open(path)
    pages = []
    for number, page in enumerate(doc[:max_pages], start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(width / page.rect.width, width / page.rect.width), alpha=False)
        pages.append({"page": number, "text": page.get_text().strip(), "image": pix.tobytes("png")})
    return pages
