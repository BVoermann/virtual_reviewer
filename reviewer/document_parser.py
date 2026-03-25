"""
document_parser.py

Extracts plain text from uploaded student documents.
Supported file types: PDF, DOCX, ODT, TXT, MD.
"""

from pathlib import Path


def extract_text(file_obj, filename: str) -> str:
    """
    Given an uploaded file object and its original filename, return the
    extracted plain text content.

    Raises ValueError for unsupported file types.
    Raises RuntimeError if extraction fails (corrupt file, missing library, …).
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_obj)
    elif suffix == ".docx":
        return _extract_docx(file_obj)
    elif suffix == ".odt":
        return _extract_odt(file_obj)
    elif suffix in (".txt", ".md"):
        raw = file_obj.read()
        return raw.decode("utf-8", errors="replace")
    else:
        raise ValueError(
            f"Nicht unterstuetztes Dateiformat: '{suffix}'. "
            "Bitte PDF, DOCX, ODT oder TXT hochladen."
        )


# ---------------------------------------------------------------------------
# Private helpers — one per file format
# ---------------------------------------------------------------------------

def _extract_pdf(file_obj) -> str:
    """Extract text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf ist nicht installiert. Bitte `pip install pypdf` ausführen.")

    reader = PdfReader(file_obj)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_docx(file_obj) -> str:
    """Extract text from a Word document using python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError(
            "python-docx ist nicht installiert. Bitte `pip install python-docx` ausführen."
        )

    doc = Document(file_obj)
    # Each paragraph is one logical block of text.
    paragraphs = [para.text for para in doc.paragraphs]
    return "\n".join(paragraphs)


def _extract_odt(file_obj) -> str:
    """Extract text from an OpenDocument text file using odfpy."""
    try:
        from odf.opendocument import load
        from odf.text import P
    except ImportError:
        raise RuntimeError(
            "odfpy ist nicht installiert. Bitte `pip install odfpy` ausführen."
        )

    doc = load(file_obj)
    paragraphs = doc.getElementsByType(P)

    texts = []
    for para in paragraphs:
        # A paragraph can contain multiple text nodes; concatenate them.
        text = "".join(
            node.data for node in para.childNodes if hasattr(node, "data")
        )
        texts.append(text)

    return "\n".join(texts)
