import os
import re
import tempfile


class DocumentExtractionError(ValueError):
    pass


class ScannedDocumentError(DocumentExtractionError):
    pass


def _clean_text(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_pdf(path):
    pages = []
    image_count = 0
    try:
        import fitz
        document = fitz.open(path)
        for page in document:
            page_text = page.get_text('text')
            if page_text.strip():
                pages.append(page_text)
            image_count += len(page.get_images(full=True))
    except ImportError:
        try:
            import pdfplumber
            with pdfplumber.open(path) as document:
                for page in document.pages:
                    pages.append(page.extract_text() or '')
        except ImportError as exc:
            raise DocumentExtractionError('PDF extraction requires PyMuPDF or pdfplumber to be installed.') from exc

    text = _clean_text('\n\n'.join(pages))
    if not text:
        if image_count:
            raise ScannedDocumentError(
                'This PDF appears to be scanned/image-based and does not contain selectable text. '
                'Please upload a text-based PDF or DOCX.'
            )
        raise DocumentExtractionError('Unable to extract readable text from this PDF.')
    return text


def _extract_docx(path):
    try:
        from docx import Document
    except ImportError as exc:
        raise DocumentExtractionError('DOCX extraction requires python-docx to be installed.') from exc
    document = Document(path)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    text = _clean_text('\n\n'.join(paragraphs))
    if not text:
        raise DocumentExtractionError('Unable to extract readable text from this DOCX.')
    return text


def extract_document_text(uploaded_file):
    extension = os.path.splitext(uploaded_file.name or '')[1].lower()
    if extension not in {'.pdf', '.docx'}:
        raise DocumentExtractionError('Only PDF and DOCX files are supported.')

    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temporary_file:
        for chunk in uploaded_file.chunks():
            temporary_file.write(chunk)
        temporary_path = temporary_file.name

    try:
        return _extract_pdf(temporary_path) if extension == '.pdf' else _extract_docx(temporary_path)
    finally:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
