import os
import logging


logger = logging.getLogger(__name__)


def extract_syllabus_text(django_file):
    """Extract readable text from a PDF or DOCX Django uploaded file."""
    django_file.seek(0)
    filename = getattr(django_file, 'name', '') or ''
    extension = os.path.splitext(filename)[1].lower()

    if extension == '.pdf':
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValueError('PDF extraction requires pdfplumber to be installed.') from exc

        with pdfplumber.open(django_file) as pdf:
            page_lengths = []
            page_texts = []
            for page in pdf.pages:
                page_text = page.extract_text() or ''
                page_lengths.append(len(page_text))
                page_texts.append(page_text)
            logger.debug('PDF text lengths name=%s pages=%s', filename, page_lengths)
            text = '\n'.join(page_texts).strip()
    elif extension == '.docx':
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError('DOCX extraction requires python-docx to be installed.') from exc

        document = Document(django_file)
        text = '\n'.join(paragraph.text for paragraph in document.paragraphs).strip()
    else:
        raise ValueError('Unsupported syllabus type. Upload a PDF or DOCX file.')

    if not text:
        if extension == '.pdf':
            raise ValueError(
                'The uploaded PDF has no extractable text layer; it may be a scanned document. '
                'Try a text-based PDF or generate using only the Topics list without a syllabus upload.'
            )
        raise ValueError('The uploaded DOCX did not contain extractable text.')

    return text
