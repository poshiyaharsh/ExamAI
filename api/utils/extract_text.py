import hashlib
import logging
import os
import time

from .evaluation_config import SYLLABUS_CACHE_TTL

logger = logging.getLogger(__name__)

_SYLLABUS_CACHE = {}


def extract_syllabus_text(django_file):
    """Extract readable text from a PDF or DOCX Django uploaded file (with in-memory & Django caching)."""
    django_file.seek(0)
    raw = django_file.read()
    django_file.seek(0)
    if not raw:
        raise ValueError('Uploaded syllabus file is empty.')

    file_hash = hashlib.sha256(raw).hexdigest()
    now = time.time()
    if file_hash in _SYLLABUS_CACHE and (now - _SYLLABUS_CACHE[file_hash].get('time', 0)) < SYLLABUS_CACHE_TTL:
        cached_entry = _SYLLABUS_CACHE[file_hash].get('data', {})
        if isinstance(cached_entry, dict) and cached_entry.get('text'):
            return cached_entry['text']

    filename = getattr(django_file, 'name', '') or ''
    extension = os.path.splitext(filename)[1].lower()

    if extension == '.pdf':
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValueError('PDF extraction requires pdfplumber to be installed.') from exc

        try:
            with pdfplumber.open(django_file) as pdf:
                page_lengths = []
                page_texts = []
                for page in pdf.pages:
                    page_text = page.extract_text() or ''
                    page_lengths.append(len(page_text))
                    page_texts.append(page_text)
                logger.debug('PDF text lengths name=%s pages=%s', filename, page_lengths)
                text = '\n'.join(page_texts).strip()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f'Could not read PDF file: {exc}') from exc
    elif extension == '.docx':
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError('DOCX extraction requires python-docx to be installed.') from exc

        try:
            document = Document(django_file)
            text = '\n'.join(paragraph.text for paragraph in document.paragraphs).strip()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f'Could not read DOCX file: {exc}') from exc
    else:
        raise ValueError('Unsupported syllabus type. Upload a PDF or DOCX file.')

    if not text:
        if extension == '.pdf':
            raise ValueError(
                'The uploaded PDF has no extractable text layer; it may be a scanned document. '
                'Try a text-based PDF or generate using only the Topics list without a syllabus upload.'
            )
        raise ValueError('The uploaded DOCX did not contain extractable text.')

    # Cache extracted text
    _SYLLABUS_CACHE[file_hash] = {'data': {'text': text, 'hash': file_hash}, 'time': now}
    return text


def extract_syllabus_pages(django_file) -> list[dict]:
    """
    Extracts text page by page (for PDF) or section by section (for DOCX).
    Returns list of dicts: [{'page_number': 1, 'text': '...', 'char_count': 123}, ...]
    """
    django_file.seek(0)
    filename = getattr(django_file, 'name', '') or ''
    extension = os.path.splitext(filename)[1].lower()
    pages_data = []

    if extension == '.pdf':
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValueError('PDF extraction requires pdfplumber to be installed.') from exc

        with pdfplumber.open(django_file) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                p_text = (page.extract_text() or '').strip()
                if p_text:
                    pages_data.append({
                        'page_number': idx,
                        'text': p_text,
                        'char_count': len(p_text),
                    })
    elif extension == '.docx':
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError('DOCX extraction requires python-docx to be installed.') from exc

        doc = Document(django_file)
        # Group paragraphs into ~2000 char virtual pages
        curr_text = []
        curr_len = 0
        page_num = 1
        for p in doc.paragraphs:
            txt = p.text.strip()
            if not txt:
                continue
            curr_text.append(txt)
            curr_len += len(txt)
            if curr_len >= 2000:
                pages_data.append({
                    'page_number': page_num,
                    'text': '\n'.join(curr_text),
                    'char_count': curr_len,
                })
                curr_text = []
                curr_len = 0
                page_num += 1
        if curr_text:
            pages_data.append({
                'page_number': page_num,
                'text': '\n'.join(curr_text),
                'char_count': curr_len,
            })
    return pages_data


def detect_syllabus_hierarchy(text: str, pages: list[dict] = None) -> dict:
    """
    Groups syllabus content into structured chapters/units with page ranges,
    character counts, subtopics, and detects multi-subject or multi-unit coverage.
    """
    import re
    if not text:
        return {'units': [], 'has_multiple_subjects': False, 'detected_topics': []}

    raw_topics = detect_syllabus_topics(text)
    units = []

    # Regex patterns for unit/chapter headings
    heading_pattern = re.compile(
        r'^(?:unit|module|chapter|topic|section|part)\s*[-:\dIVXLCDM]+[\s\.\:\-–—]+(.+)',
        re.IGNORECASE
    )

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    detected_headings = []
    for line in lines:
        m = heading_pattern.match(line)
        if m:
            clean = line[:100].strip(' -:–—.')
            if len(clean) >= 4 and clean.lower() not in [h['title'].lower() for h in detected_headings]:
                detected_headings.append({'title': clean, 'line': line})

    # If no explicit headings, use raw_topics
    if not detected_headings:
        for t in raw_topics[:8]:
            detected_headings.append({'title': t, 'line': t})

    # Find character / page spans for each unit
    for idx, h in enumerate(detected_headings):
        unit_title = h['title']
        start_char = text.find(h['line']) if h['line'] in text else 0
        next_heading_line = detected_headings[idx + 1]['line'] if idx + 1 < len(detected_headings) else None
        end_char = text.find(next_heading_line, start_char + 1) if next_heading_line and next_heading_line in text else len(text)
        if end_char == -1 or end_char <= start_char:
            end_char = min(len(text), start_char + 4000)

        chunk_text = text[max(0, start_char) : end_char].strip()

        # Find page range if page data available
        page_range_str = "Document section"
        if pages:
            matched_pages = []
            for p in pages:
                if unit_title.lower() in p['text'].lower() or any(w.lower() in p['text'].lower() for w in unit_title.split() if len(w) > 4):
                    matched_pages.append(p['page_number'])
            if matched_pages:
                min_p, max_p = min(matched_pages), max(matched_pages)
                page_range_str = f"Page {min_p}" if min_p == max_p else f"Pages {min_p}–{max_p}"

        # Extract subtopics inside this unit
        unit_lines = [l.strip() for l in chunk_text.split('\n') if len(l.strip()) > 5]
        subtopics = []
        sub_pattern = re.compile(r'^(?:\d+[\.\)]|[•\-\*])\s*([A-Za-z0-9\s,\-–—/&]{4,60})')
        for l in unit_lines:
            sm = sub_pattern.match(l)
            if sm:
                sub = sm.group(1).strip()
                if sub.lower() not in [s.lower() for s in subtopics] and sub.lower() != unit_title.lower():
                    subtopics.append(sub)
                    if len(subtopics) >= 6:
                        break

        units.append({
            'id': f"unit_{idx + 1}",
            'title': unit_title,
            'page_range': page_range_str,
            'char_count': len(chunk_text),
            'subtopics': subtopics,
            'chunk_text': chunk_text[:5000],
        })

    # Domain keyword heuristics to detect cross-subject bleed (e.g. OS vs Java vs Network)
    domains_found = set()
    low_text = text.lower()
    domain_keywords = {
        'Operating Systems': ['process management', 'memory management', 'scheduling algorithm', 'deadlock', 'linux', 'unix', 'kernel', 'file system'],
        'Java / OOP': ['java', 'jdk', 'jvm', 'inheritance', 'polymorphism', 'garbage collection', 'bytecode', 'interface'],
        'Computer Networks': ['osi model', 'tcp/ip', 'routing', 'packet switching', 'subnet', 'ethernet', 'http', 'dns'],
        'Database Systems': ['sql', 'rdbms', 'relational algebra', 'normalization', 'acid properties', 'indexing', 'transactions'],
        'Ethical Hacking': ['footprinting', 'reconnaissance', 'penetration testing', 'vulnerability scanning', 'nmap', 'metasploit'],
    }
    for dom, kws in domain_keywords.items():
        if sum(1 for kw in kws if kw in low_text) >= 2:
            domains_found.add(dom)

    has_multiple_subjects = len(domains_found) >= 2 or len(units) >= 2

    return {
        'units': units,
        'has_multiple_subjects': has_multiple_subjects,
        'detected_domains': list(domains_found),
        'detected_topics': [u['title'] for u in units] if units else raw_topics,
    }


def estimate_syllabus_capacity(char_count: int, num_topics: int = 1, text: str = "") -> dict:
    """
    Estimates whether the syllabus text is large enough to support the requested
    number of questions and marks based on factual sentence count, distinct concepts,
    and words per topic.
    """
    safe_chars = max(0, char_count)
    word_count = len(text.split()) if text else (safe_chars // 6)
    
    # Analyze testable sentences if text is provided
    testable_sentences = 0
    if text:
        import re
        sentences = re.split(r'[.!?]+', text)
        keywords = {'is', 'are', 'defined', 'consists', 'function', 'protocol', 'layer', 'algorithm', 'mechanism', 'feature', 'process', 'architecture'}
        for s in sentences:
            words = set(s.lower().split())
            if len(words) >= 6 and (words & keywords):
                testable_sentences += 1
    else:
        testable_sentences = max(5, word_count // 25)

    # Question capacity: 1 question requires ~3 factual sentences or ~350 chars
    estimated_q = max(3, min(testable_sentences // 2, safe_chars // 350))
    # Marks capacity: objective (~1-2M), short (~5M), long (~10M)
    estimated_marks = max(10, min(100, int(estimated_q * 3.5)))
    is_low = safe_chars < 4000 or word_count < 600

    # Suggested blueprint when capacity is low
    suggested_bp = {}
    if is_low:
        if estimated_marks <= 30:
            suggested_bp = {'mcq': {'count': 10, 'marks': 1}, 'true_false': {'count': 5, 'marks': 1}, 'short_answer': {'count': 3, 'marks': 5}}
        elif estimated_marks <= 60:
            suggested_bp = {'mcq': {'count': 15, 'marks': 1}, 'true_false': {'count': 5, 'marks': 1}, 'short_answer': {'count': 4, 'marks': 5}, 'long_answer': {'count': 2, 'marks': 10}}
        else:
            suggested_bp = {'mcq': {'count': 10, 'marks': 1}, 'true_false': {'count': 5, 'marks': 1}, 'fill_blank': {'count': 5, 'marks': 1}, 'short_answer': {'count': 4, 'marks': 5}, 'long_answer': {'count': 6, 'marks': 10}}

    warning = (
        f"The selected document ({char_count:,} characters, ~{word_count} words) can reliably support about {estimated_q} questions (~{estimated_marks} marks). A target higher than {estimated_marks} may result in a shortfall."
        if is_low else None
    )
    return {
        'word_count': word_count,
        'testable_sentences': testable_sentences,
        'estimated_max_questions': estimated_q,
        'estimated_max_marks': estimated_marks,
        'is_low_capacity': is_low,
        'warning': warning,
        'suggested_blueprint': suggested_bp,
    }


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




def get_cached_syllabus_data(file_obj, filename=""):
    """
    Extracts text, topics, and chunks for a syllabus file once and caches them by SHA-256 hash.
    Checks in-memory process cache first, then Django cache backend.
    """
    from .evaluation_config import SYLLABUS_CACHE_TTL
    try:
        from django.core.cache import cache
    except Exception:
        cache = None

    file_obj.seek(0)
    content = file_obj.read()
    file_obj.seek(0)
    
    file_hash = hashlib.sha256(content).hexdigest()
    now = time.time()
    
    if file_hash in _SYLLABUS_CACHE:
        entry = _SYLLABUS_CACHE[file_hash]
        if now - entry.get('time', 0) < SYLLABUS_CACHE_TTL:
            return entry['data']

    if cache:
        cache_key = f'syllabus_data_{file_hash}'
        cached_entry = cache.get(cache_key)
        if cached_entry:
            _SYLLABUS_CACHE[file_hash] = {'data': cached_entry, 'time': now}
            return cached_entry

    text = extract_syllabus_text(file_obj)
    try:
        pages = extract_syllabus_pages(file_obj)
    except Exception:
        pages = []
    hierarchy = detect_syllabus_hierarchy(text, pages)
    topics = hierarchy.get('detected_topics') or detect_syllabus_topics(text)
    chunks = chunk_syllabus_by_topics(text, topics)
    data = {
        'hash': file_hash,
        'text': text,
        'pages': pages,
        'hierarchy': hierarchy,
        'topics': topics,
        'chunks': chunks,
    }
    _SYLLABUS_CACHE[file_hash] = {'data': data, 'time': now}
    if cache:
        cache.set(f'syllabus_data_{file_hash}', data, timeout=SYLLABUS_CACHE_TTL)
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


def get_relevant_syllabus_chunk(
    syllabus_text: str,
    topic: str,
    chunks_map: dict = None,
    max_chars: int = 3000,
    round_offset: int = 0,
) -> str:
    """
    Returns the most relevant section/chunk of the syllabus for the given topic.
    Supports round_offset to shift reading window across multiple top-up rounds,
    ensuring subsequent rounds explore fresh text.
    """
    base_chunk = ""
    if chunks_map and topic in chunks_map and chunks_map[topic]:
        base_chunk = chunks_map[topic]
    elif syllabus_text and topic:
        lower_text = syllabus_text.lower()
        idx = lower_text.find(topic.lower())
        if idx != -1:
            start = max(0, idx - 200)
            base_chunk = syllabus_text[start:]

    if not base_chunk:
        base_chunk = syllabus_text or ""

    if not base_chunk:
        return ""

    stride = 800 * max(0, round_offset)
    if len(base_chunk) > max_chars and stride > 0:
        start_pos = stride % max(1, len(base_chunk) - max_chars // 2)
        return base_chunk[start_pos : start_pos + max_chars].strip()

    return base_chunk[:max_chars].strip()



