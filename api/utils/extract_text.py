import os


def extract_syllabus_text(django_file):
    """Extract readable text from a PDF or DOCX Django uploaded file."""
    filename = getattr(django_file, 'name', '') or ''
    extension = os.path.splitext(filename)[1].lower()

    try:
        django_file.seek(0)
    except (AttributeError, OSError):
        pass

    if extension == '.pdf':
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValueError('PDF extraction requires pdfplumber to be installed.') from exc

        with pdfplumber.open(django_file) as pdf:
            text = '\n'.join(page.extract_text() or '' for page in pdf.pages).strip()
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
        raise ValueError('The syllabus file did not contain extractable text.')

    return text
