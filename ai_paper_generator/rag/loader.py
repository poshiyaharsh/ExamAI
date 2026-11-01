"""
Document Loader for RAG.
Extracts clean, structured text from:
- PDF (via pymupdf / fitz or pdfplumber)
- DOCX (via python-docx)
- TXT
- PPTX (via XML text extraction from slides)
Returns list of pages/sections with metadata (source file, page/slide number).
"""
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any


def load_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Loads PDF pages with page numbers using PyMuPDF / pdfplumber."""
    pages = []
    try:
        import pymupdf as fitz
        doc = fitz.open(file_path)
        for page_idx, page in enumerate(doc, start=1):
            text = page.get_text() or ''
            if text.strip():
                pages.append({
                    'page_number': page_idx,
                    'text': text.strip(),
                    'source': Path(file_path).name,
                })
        doc.close()
        return pages
    except Exception:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ''
                if text.strip():
                    pages.append({
                        'page_number': page_idx,
                        'text': text.strip(),
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
        paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]

        # Also extract table cells
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)

        full_text = "\n\n".join(paragraphs)
        if not full_text.strip():
            return []

        # Split into ~1000 character logical sections
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
    """Loads plain text files."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        if not content.strip():
            return []
        chunks = [content[i:i + 1500] for i in range(0, len(content), 1500)]
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
                text_parts = [elem.text for elem in tree.iter() if elem.text and elem.text.strip()]
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
    """
    ext = Path(file_path).suffix.lower()
    if ext == '.pdf':
        return load_pdf(file_path)
    elif ext in ('.docx', '.doc'):
        return load_docx(file_path)
    elif ext == '.txt':
        return load_txt(file_path)
    elif ext in ('.pptx', '.ppt'):
        return load_pptx(file_path)
    else:
        # Fallback to plain text read
        return load_txt(file_path)
