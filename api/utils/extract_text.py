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


def detect_syllabus_topics(text: str) -> list[str]:
    """
    Extracts distinct units/modules/chapters/topics from syllabus text.
    Returns a deduplicated list of clean topic strings.
    """
    import re
    if not text:
        return []

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    detected = []

    # Regex patterns for syllabus headings: Unit 1, Module A, Chapter 2, etc.
    heading_pattern = re.compile(
        r'^(?:unit|module|chapter|topic|section|part)\s*[-:\dIVXLCDM]+[\s\.\:\-–—]+(.+)',
        re.IGNORECASE
    )
    numbered_pattern = re.compile(r'^\d+[\.\:\)]\s+([A-Z][A-Za-z0-9\s,\-–—/&]{4,80})$')

    for line in lines:
        # Match explicit Unit/Module/Chapter prefixes
        m = heading_pattern.match(line)
        if m:
            clean = m.group(1).strip(' -:–—.')
            if len(clean) >= 4 and clean.lower() not in [t.lower() for t in detected]:
                # Keep prefix if informative, e.g. "Unit 1: Data Structures"
                detected.append(line[:100].strip())
            continue

        # Match numbered syllabus items e.g. "1. Computer Networks and Architecture"
        nm = numbered_pattern.match(line)
        if nm:
            clean = nm.group(1).strip(' -:–—.')
            if len(clean) >= 4 and clean.lower() not in [t.lower() for t in detected]:
                detected.append(clean[:100].strip())

    # If heuristic found fewer than 2 units/topics, search for short uppercase or title-case lines
    if len(detected) < 2:
        for line in lines:
            if 6 <= len(line) <= 60 and not line.endswith(('.', '?', '!', ';')):
                words = line.split()
                if 2 <= len(words) <= 8 and (line.isupper() or line.istitle()):
                    if line.lower() not in [t.lower() for t in detected] and not any(kw in line.lower() for kw in ['syllabus', 'course', 'credit', 'exam', 'hours', 'department']):
                        detected.append(line)
                        if len(detected) >= 8:
                            break

    # If still none found, create 3-5 semantic sections by chunking
    if not detected:
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]
        for p in paragraphs[:5]:
            first_line = p.split('\n')[0].strip(' -:–—.')
            if 5 <= len(first_line) <= 80:
                detected.append(first_line)

    return detected[:10]


import hashlib
import time

_SYLLABUS_CACHE = {}


def get_cached_syllabus_data(file_obj, filename=""):
    """
    Extracts text, topics, and chunks for a syllabus file once and caches them by SHA-256 hash.
    """
    from .evaluation_config import SYLLABUS_CACHE_TTL
    file_obj.seek(0)
    content = file_obj.read()
    file_obj.seek(0)
    
    file_hash = hashlib.sha256(content).hexdigest()
    now = time.time()
    
    if file_hash in _SYLLABUS_CACHE:
        entry = _SYLLABUS_CACHE[file_hash]
        if now - entry.get('time', 0) < SYLLABUS_CACHE_TTL:
            return entry['data']

    text = extract_syllabus_text(file_obj)
    topics = detect_syllabus_topics(text)
    chunks = chunk_syllabus_by_topics(text, topics)
    data = {
        'hash': file_hash,
        'text': text,
        'topics': topics,
        'chunks': chunks,
    }
    _SYLLABUS_CACHE[file_hash] = {'data': data, 'time': now}
    return data


def chunk_syllabus_by_topics(text: str, topics: list) -> dict:
    """
    Splits the syllabus text into topic-based chunks.
    Guarantees each chunk has at least 1500 chars (if available) and at most 3500 chars.
    """
    chunks = {}
    if not text:
        return {}
    if not topics:
        return {"General": text[:3500].strip()}

    lower_text = text.lower()
    indices = []
    for t in topics:
        clean_t = str(t).strip().lower()
        idx = lower_text.find(clean_t)
        if idx == -1:
            words = [w for w in clean_t.split() if len(w) > 3]
            if words:
                idx = lower_text.find(words[0])
        if idx != -1:
            indices.append((idx, t))

    indices.sort(key=lambda x: x[0])

    if not indices:
        chunk_sz = max(1500, len(text) // max(len(topics), 1))
        for i, t in enumerate(topics):
            chunks[t] = text[i * chunk_sz : min(len(text), (i + 1) * chunk_sz + 500)].strip()
        return chunks

    for i in range(len(indices)):
        start_idx = indices[i][0]
        # Allow overlap and ensure minimum readable chunk size
        end_boundary = indices[i + 1][0] if i + 1 < len(indices) else len(text)
        chunk_len = max(1500, min(3500, end_boundary - start_idx + 300))
        chunk_content = text[start_idx : min(len(text), start_idx + chunk_len)].strip()
        chunks[indices[i][1]] = chunk_content

    for t in topics:
        if t not in chunks:
            chunks[t] = text[:2500].strip()

    return chunks


def get_relevant_syllabus_chunk(syllabus_text: str, topic: str, chunks_map: dict = None, max_chars: int = 3000) -> str:
    """
    Returns the most relevant section/chunk of the syllabus for the given topic.
    """
    if chunks_map and topic in chunks_map and chunks_map[topic]:
        return chunks_map[topic][:max_chars]
    if not syllabus_text:
        return ""
    if topic:
        lower_text = syllabus_text.lower()
        idx = lower_text.find(topic.lower())
        if idx != -1:
            start = max(0, idx - 200)
            return syllabus_text[start : min(len(syllabus_text), start + max_chars)].strip()
    return syllabus_text[:max_chars].strip()


