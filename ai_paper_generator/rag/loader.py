"""
Document Loader for RAG.
Extracts clean, structured text from:
- PDF (via pymupdf / fitz or pdfplumber)
- DOCX (via python-docx)
- TXT (with automatic encoding detection)
- PPTX (via XML text extraction from slides)
Returns list of pages/sections with metadata (source file, page/slide number).
Ensures Unicode NFC normalization and legacy 8-bit font detection across all formats.
"""
import os
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any

try:
    import charset_normalizer
except ImportError:
    charset_normalizer = None

from ai_paper_generator.language import is_garbled_legacy_text


def _normalize_text(text: str) -> str:
    """Normalizes text to Unicode NFC and cleans abnormal control chars."""
    if not text:
        return ""
    # NFC canonical composition
    normalized = unicodedata.normalize("NFC", text)
    # Remove control characters except standard whitespace (keep \n, \r, \t)
    return "".join(ch for ch in normalized if ch in "\n\r\t" or not unicodedata.category(ch).startswith("C"))


def load_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Loads PDF pages with page numbers using PyMuPDF / pdfplumber."""
    pages = []
    try:
        import pymupdf as fitz
        doc = fitz.open(file_path)
        for page_idx, page in enumerate(doc, start=1):
            text = page.get_text() or ''
            clean_text = _normalize_text(text).strip()
            if clean_text:
                pages.append({
                    'page_number': page_idx,
                    'text': clean_text,
                    'source': Path(file_path).name,
                })
        doc.close()
        if pages:
            return pages
    except Exception:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ''
                clean_text = _normalize_text(text).strip()
                if clean_text:
                    pages.append({
                        'page_number': page_idx,
                        'text': clean_text,
                        'source': Path(file_path).name,
                    })
        return pages
    except Exception as exc:
        raise ValueError(f"Could not parse PDF file '{file_path}': {str(exc)}") from exc


def load_docx(file_path: str) -> List[Dict[str, Any]]:
    """Loads paragraphs and tables from DOCX with pseudo-page numbering."""
    try:
        import docx
        doc = docx.Document(file_path)
        paragraphs = [_normalize_text(p.text) for p in doc.paragraphs if p.text and p.text.strip()]

        # Also extract table cells
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(_normalize_text(cell.text).strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)

        full_text = "\n\n".join(paragraphs)
        if not full_text.strip():
            return []

        # Split into ~1500 character logical sections
        chunks = [full_text[i:i + 1500] for i in range(0, len(full_text), 1500)]
        return [
            {
                'page_number': idx,
                'text': chunk.strip(),
                'source': Path(file_path).name,
            }
            for idx, chunk in enumerate(chunks, start=1)
        ]
    except Exception as exc:
        raise ValueError(f"Could not parse DOCX file '{file_path}': {str(exc)}") from exc


def load_txt(file_path: str) -> List[Dict[str, Any]]:
    """Loads plain text files with automatic encoding detection."""
    try:
        with open(file_path, 'rb') as f:
            raw_bytes = f.read()

        if not raw_bytes:
            return []

        content = ""
        # 1. Try charset_normalizer
        if charset_normalizer:
            try:
                result = charset_normalizer.from_bytes(raw_bytes).best()
                if result and result.encoding:
                    content = str(result)
            except Exception:
                content = ""

        # 2. Fallbacks
        if not content:
            for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
                try:
                    content = raw_bytes.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue

        clean_text = _normalize_text(content)
        if not clean_text.strip():
            return []

        chunks = [clean_text[i:i + 1500] for i in range(0, len(clean_text), 1500)]
        return [
            {
                'page_number': idx,
                'text': chunk.strip(),
                'source': Path(file_path).name,
            }
            for idx, chunk in enumerate(chunks, start=1)
        ]
    except Exception as exc:
        raise ValueError(f"Could not read TXT file '{file_path}': {str(exc)}") from exc


def load_pptx(file_path: str) -> List[Dict[str, Any]]:
    """Loads slides from PPTX by parsing XML slide archives."""
    slides = []
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            slide_names = [name for name in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml', name)]
            # Sort numerically
            slide_names.sort(key=lambda s: int(re.search(r'\d+', s).group()) if re.search(r'\d+', s) else 0)

            for idx, slide_name in enumerate(slide_names, start=1):
                xml_content = z.read(slide_name)
                tree = ET.fromstring(xml_content)
                text_parts = [_normalize_text(elem.text) for elem in tree.iter() if elem.text and elem.text.strip()]
                slide_text = " ".join(text_parts).strip()
                if slide_text:
                    slides.append({
                        'page_number': idx,
                        'text': slide_text,
                        'source': Path(file_path).name,
                    })
        return slides
    except Exception as exc:
        raise ValueError(f"Could not parse PPTX presentation '{file_path}': {str(exc)}") from exc


def load_document(file_path: str) -> List[Dict[str, Any]]:
    """
    Auto-detects document format from file extension and extracts sections.
    Supported: .pdf, .docx, .txt, .pptx
    Checks for scanned image-only PDFs and garbled legacy 8-bit text.
    """
    ext = Path(file_path).suffix.lower()
    if ext == '.pdf':
        sections = load_pdf(file_path)
    elif ext in ('.docx', '.doc'):
        sections = load_docx(file_path)
    elif ext == '.txt':
        sections = load_txt(file_path)
    elif ext in ('.pptx', '.ppt'):
        sections = load_pptx(file_path)
    else:
        # Fallback to plain text read
        sections = load_txt(file_path)

    if not sections:
        if ext == '.pdf':
            raise ValueError(
                "No extractable text found in PDF. Scanned or image-only PDFs without an "
                "embedded text layer are not supported."
            )
        return []

    combined_text = "\n".join(s.get('text', '') for s in sections)
    if is_garbled_legacy_text(combined_text):
        raise ValueError(
            "The uploaded document appears to use legacy 8-bit encoded text (such as Kruti Dev or Shree-Lipi) "
            "rather than standard Unicode. Please convert it to standard Unicode font or UTF-8 text before uploading."
        )

    return sections
