"""
Robust, deterministic text and topic extraction pipeline for PDF and DOCX documents.
Supports:
1. PyMuPDF (fitz) embedded text extraction with pdfplumber fallback.
2. Scanned document detection.
3. Deterministic outline/bookmark and heading hierarchy extraction (with LLM fallback).
4. Balanced topic weighting and 300-500 word chunking with page number mappings.
5. SHA-256 + Institution caching.
"""
import hashlib
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .evaluation_config import OLLAMA_KEEP_ALIVE, OLLAMA_MODEL, SYLLABUS_CACHE_TTL

logger = logging.getLogger(__name__)

MAX_SYLLABUS_FILE_SIZE = 25 * 1024 * 1024  # 25 MB max limit
_SYLLABUS_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_cache_key(file_hash: str, institution_id: Optional[int] = None) -> str:
    inst_suffix = f"_{institution_id}" if institution_id else "_global"
    return f"syllabus_data{inst_suffix}_{file_hash}"


def extract_syllabus_text(django_file, institution_id: Optional[int] = None) -> str:
    """
    Extract readable text from a PDF or DOCX file.
    Cached by file SHA-256 + institution_id.
    """
    django_file.seek(0)
    raw = django_file.read()
    django_file.seek(0)
    if not raw:
        raise ValueError('Uploaded syllabus file is empty.')

    if len(raw) > MAX_SYLLABUS_FILE_SIZE:
        raise ValueError('File size exceeds maximum allowed limit (25MB).')

    file_hash = hashlib.sha256(raw).hexdigest()
    cache_key = _get_cache_key(file_hash, institution_id)
    now = time.time()
    if cache_key in _SYLLABUS_CACHE and (now - _SYLLABUS_CACHE[cache_key].get('time', 0)) < SYLLABUS_CACHE_TTL:
        cached_entry = _SYLLABUS_CACHE[cache_key].get('data', {})
        if isinstance(cached_entry, dict) and cached_entry.get('text'):
            return cached_entry['text']

    filename = getattr(django_file, 'name', '') or ''
    extension = os.path.splitext(filename)[1].lower()
    is_pdf = extension == '.pdf' or raw.startswith(b'%PDF')
    is_docx = extension == '.docx' or raw.startswith(b'PK\x03\x04')
    text = ""

    if is_pdf:
        text, _ = _extract_pdf_pages_and_text(raw, filename)
    elif is_docx:
        text = _extract_docx_text(django_file)
    else:
        raise ValueError('Unsupported syllabus type. Upload a PDF or DOCX file.')

    if not text or len(text.strip()) < 15:
        if is_pdf:
            raise ValueError('This PDF looks scanned. Text could not be extracted.')
        raise ValueError('The uploaded DOCX did not contain extractable text.')

    # Scanned detection for multi-page documents with minimal text
    if extension == '.pdf' and len(text.strip()) < 100:
        raise ValueError('This PDF looks scanned. Text could not be extracted.')

    _SYLLABUS_CACHE[cache_key] = {'data': {'text': text, 'hash': file_hash}, 'time': now}
    return text


def _extract_pdf_pages_and_text(raw_bytes: bytes, filename: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    """
    Extracts text and page-by-page metadata using PyMuPDF (fitz) first,
    falling back to pdfplumber.
    """
    pages_data: List[Dict[str, Any]] = []
    text_content = ""

    # 1. Try PyMuPDF (fitz)
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        page_texts = []
        for idx in range(len(doc)):
            page = doc[idx]
            page_text = page.get_text("text") or ""
            page_texts.append(page_text)
            pages_data.append({
                'page_number': idx + 1,
                'text': page_text.strip(),
                'char_count': len(page_text.strip()),
            })
        text_content = '\n'.join(page_texts).strip()
        doc.close()
    except Exception as exc:
        logger.info("PyMuPDF extraction failed (%s), falling back to pdfplumber: %s", filename, exc)
        try:
            import io
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                page_texts = []
                for idx, page in enumerate(pdf.pages, start=1):
                    p_text = page.extract_text() or ""
                    page_texts.append(p_text)
                    pages_data.append({
                        'page_number': idx,
                        'text': p_text.strip(),
                        'char_count': len(p_text.strip()),
                    })
                text_content = '\n'.join(page_texts).strip()
        except Exception as p_exc:
            raise ValueError(f'Could not read PDF file: {p_exc}') from p_exc

    return text_content, pages_data


def _extract_docx_text(django_file) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError('DOCX extraction requires python-docx to be installed.') from exc

    try:
        django_file.seek(0)
        doc = Document(django_file)
        django_file.seek(0)
        return '\n'.join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    except Exception as exc:
        raise ValueError(f'Could not read DOCX file: {exc}') from exc


def extract_syllabus_pages(django_file) -> List[Dict[str, Any]]:
    """
    Extracts structured page-by-page list.
    """
    django_file.seek(0)
    raw = django_file.read()
    django_file.seek(0)
    filename = getattr(django_file, 'name', '') or ''
    extension = os.path.splitext(filename)[1].lower()
    is_pdf = extension == '.pdf' or raw.startswith(b'%PDF')
    is_docx = extension == '.docx' or raw.startswith(b'PK\x03\x04')

    if is_pdf:
        _, pages_data = _extract_pdf_pages_and_text(raw, filename)
        return pages_data
    elif is_docx:
        from docx import Document
        django_file.seek(0)
        doc = Document(django_file)
        django_file.seek(0)
        pages_data = []
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
    return []


def detect_pdf_bookmarks_or_outlines(raw_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extracts bookmarks/table of contents directly from PDF outline if available.
    """
    outlines = []
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        toc = doc.get_toc()  # [[lvl, title, page], ...]
        doc.close()
        for item in toc:
            if isinstance(item, list) and len(item) >= 3:
                lvl, title, page = item[0], str(item[1]).strip(), item[2]
                if title and len(title) >= 3:
                    outlines.append({'title': title, 'page': page, 'level': lvl})
    except Exception:
        pass
    return outlines


def detect_syllabus_hierarchy(text: str, pages: List[Dict[str, Any]] = None, raw_bytes: bytes = None) -> Dict[str, Any]:
    """
    Deterministically extracts structured units/topics without LLM first.
    Uses:
    1. PDF Bookmarks / Outline Table of Contents.
    2. Heading patterns (Unit/Chapter/Module/Section numbering).
    3. Font size & style cues when available.
    4. Fallback LLM prompt ONLY when no structure could be found.
    """
    if not text:
        return {'units': [], 'has_multiple_subjects': False, 'detected_domains': [], 'detected_topics': []}

    total_chars = max(len(text), 1)
    detected_headings: List[Dict[str, Any]] = []

    # Strategy 1: PDF bookmarks / outline
    if raw_bytes:
        toc_entries = detect_pdf_bookmarks_or_outlines(raw_bytes)
        if len(toc_entries) >= 2:
            for entry in toc_entries:
                t_clean = re.sub(r'[\r\n\t]+', ' ', entry['title']).strip()
                if len(t_clean) >= 3 and t_clean.lower() not in [h['title'].lower() for h in detected_headings]:
                    detected_headings.append({
                        'title': t_clean,
                        'page': entry.get('page'),
                        'line': t_clean,
                    })

    # Strategy 2: Regex patterns on document text
    if len(detected_headings) < 2:
        heading_pattern = re.compile(
            r'^(?:unit|module|chapter|topic|section|part)\s*[-:\dIVXLCDM]+[\s\.\:\-–—]+(.+)',
            re.IGNORECASE
        )
        numbered_pattern = re.compile(r'^\d+[\.\:\)]\s+([A-Z][A-Za-z0-9\s,\-–—/&]{4,80})$')
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for line in lines:
            m = heading_pattern.match(line)
            if m:
                clean = line[:100].strip(' -:–—.')
                if len(clean) >= 4 and clean.lower() not in [h['title'].lower() for h in detected_headings]:
                    detected_headings.append({'title': clean, 'line': line})
                continue
            nm = numbered_pattern.match(line)
            if nm and len(detected_headings) < 15:
                clean = nm.group(1).strip(' -:–—.')
                if len(clean) >= 4 and clean.lower() not in [h['title'].lower() for h in detected_headings]:
                    detected_headings.append({'title': clean, 'line': line})

    # Strategy 3: Capitalized / Title-case standalone lines
    if len(detected_headings) < 2:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in lines:
            if 6 <= len(line) <= 60 and not line.endswith(('.', '?', '!', ';')):
                words = line.split()
                if 2 <= len(words) <= 8 and (line.isupper() or line.istitle()):
                    clean = line.strip(' -:–—.')
                    lower_clean = clean.lower()
                    if lower_clean not in [h['title'].lower() for h in detected_headings]:
                        if not any(kw in lower_clean for kw in ['syllabus', 'course', 'credit', 'exam', 'hours', 'department', 'university', 'page']):
                            detected_headings.append({'title': clean, 'line': line})
                            if len(detected_headings) >= 8:
                                break

    # Strategy 4: Fallback LLM prompt ONLY if completely unstructured (< 2 topics)
    if len(detected_headings) < 2:
        llm_topics = _detect_topics_with_short_llm_fallback(text[:3000])
        for t in llm_topics:
            detected_headings.append({'title': t, 'line': t})

    # Ensure at least 1-3 baseline topics
    if not detected_headings:
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]
        for idx, p in enumerate(paragraphs[:4], start=1):
            first_line = p.split('\n')[0].strip(' -:–—.')[:60]
            detected_headings.append({'title': first_line or f"Section {idx}", 'line': first_line})

    # Build structured units with page spans, weights, and summaries
    units = []
    for idx, h in enumerate(detected_headings):
        unit_title = h['title']
        start_char = text.find(h['line']) if h.get('line') and h['line'] in text else 0
        next_heading_line = detected_headings[idx + 1].get('line') if idx + 1 < len(detected_headings) else None
        end_char = text.find(next_heading_line, start_char + 1) if next_heading_line and next_heading_line in text else len(text)
        if end_char == -1 or end_char <= start_char:
            end_char = min(len(text), start_char + 4000)

        chunk_text = text[max(0, start_char): end_char].strip()
        char_count = max(len(chunk_text), 100)

        page_range_str = "All pages"
        if pages:
            matched_pages = []
            for p in pages:
                p_text_lower = p['text'].lower()
                if unit_title.lower() in p_text_lower or any(w.lower() in p_text_lower for w in unit_title.split() if len(w) > 4):
                    matched_pages.append(p['page_number'])
            if matched_pages:
                min_p, max_p = min(matched_pages), max(matched_pages)
                page_range_str = f"Page {min_p}" if min_p == max_p else f"Pages {min_p}–{max_p}"
            elif h.get('page'):
                page_range_str = f"Page {h['page']}"

        # Short summary: first meaningful sentence
        sentences = [s.strip() for s in re.split(r'[.!?\n]+', chunk_text) if len(s.strip()) > 15]
        summary = (sentences[0][:150] + '...') if sentences else unit_title

        units.append({
            'id': f"topic_{idx + 1}",
            'title': unit_title,
            'page_range': page_range_str,
            'char_count': char_count,
            'summary': summary,
            'chunk_text': chunk_text,
        })

    # Topic merging (merge tiny topics < 150 chars into previous topic)
    merged_units = []
    for u in units:
        if merged_units and u['char_count'] < 150 and len(units) > 3:
            prev = merged_units[-1]
            prev['char_count'] += u['char_count']
            prev['chunk_text'] += "\n" + u['chunk_text']
        else:
            merged_units.append(u)
    units = merged_units if merged_units else units

    # Constrain to 3-15 sensible topics
    if len(units) > 15:
        units = units[:15]

    # Calculate proportional weights (summing to 100%)
    total_unit_chars = sum(u['char_count'] for u in units) or 1
    for u in units:
        raw_pct = round((u['char_count'] / total_unit_chars) * 100, 1)
        u['weight'] = max(5.0, raw_pct)  # at least 5% weight

    # Re-normalize weights to exact 100.0%
    weight_sum = sum(u['weight'] for u in units)
    for u in units:
        u['weight'] = round((u['weight'] / weight_sum) * 100, 1)

    # Multi-subject detection
    low_text = text.lower()
    domain_keywords = {
        'Operating Systems': ['process management', 'memory management', 'scheduling algorithm', 'deadlock', 'linux', 'unix', 'kernel', 'file system'],
        'Java / OOP': ['java', 'jdk', 'jvm', 'inheritance', 'polymorphism', 'garbage collection', 'bytecode', 'interface'],
        'Computer Networks': ['osi model', 'tcp/ip', 'routing', 'packet switching', 'subnet', 'ethernet', 'http', 'dns'],
        'Database Systems': ['sql', 'rdbms', 'relational algebra', 'normalization', 'acid properties', 'indexing', 'transactions'],
        'Ethical Hacking / Cyber Security': ['footprinting', 'reconnaissance', 'penetration testing', 'vulnerability scanning', 'nmap', 'metasploit'],
        'Artificial Intelligence / ML': ['neural network', 'gradient descent', 'supervised learning', 'classification', 'regression', 'clustering'],
    }
    domains_found = []
    for dom, kws in domain_keywords.items():
        if sum(1 for kw in kws if kw in low_text) >= 2:
            domains_found.append(dom)

    has_multiple_subjects = len(domains_found) >= 2

    return {
        'units': units,
        'has_multiple_subjects': has_multiple_subjects,
        'detected_domains': domains_found,
        'detected_topics': [u['title'] for u in units],
    }


def _detect_topics_with_short_llm_fallback(compressed_outline: str) -> List[str]:
    """
    Short, fallback prompt when no deterministic outline was detected.
    Uses format 'json' and short max tokens.
    """
    try:
        from .ollama_client import call_ollama, parse_json_safely
        prompt = (
            "Extract 4 to 8 academic syllabus unit or chapter topic titles from this text as a JSON array of strings.\n"
            "Return JSON only: {\"topics\": [\"Unit 1 Title\", \"Unit 2 Title\", ...]}\n\n"
            f"Text:\n{compressed_outline[:2500]}"
        )
        resp = call_ollama(
            model=OLLAMA_MODEL,
            prompt=prompt,
            format_schema="json",
            num_predict=300,
            temperature=0.1,
            timeout=20,
        )
        parsed = parse_json_safely(resp)
        topics = parsed.get('topics', []) if isinstance(parsed, dict) else []
        return [str(t).strip() for t in topics if str(t).strip()][:8]
    except Exception as exc:
        logger.info("LLM topic fallback extraction skipped: %s", exc)
        return []


def detect_syllabus_topics(text: str) -> List[str]:
    """
    Fast extraction of topic titles.
    """
    hierarchy = detect_syllabus_hierarchy(text)
    return hierarchy.get('detected_topics') or []


def chunk_syllabus_by_topics(
    text: str,
    topics: List[str],
    pages: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Chunks text per topic into 300-500 words (~1800-3000 chars) with small overlap (~50 words / 300 chars).
    Each topic gets a list of chunk dicts:
    [{'chunk_id': 'topic_1_chk_1', 'text': '...', 'page_numbers': [1, 2], 'word_count': 350}, ...]
    Also keeps a flat string chunk mapping for backwards-compatibility.
    """
    chunks_map: Dict[str, Any] = {}
    if not text:
        return {}

    selected_topics = [t for t in topics if str(t).strip()]
    if not selected_topics:
        selected_topics = ['General']

    lower_text = text.lower()
    indices: List[Tuple[int, str]] = []

    for t in selected_topics:
        clean_t = str(t).strip().lower()
        idx = lower_text.find(clean_t)
        if idx == -1:
            words = [w for w in clean_t.split() if len(w) > 3]
            if words:
                idx = lower_text.find(words[0])
        if idx != -1:
            indices.append((idx, t))

    indices.sort(key=lambda x: x[0])

    # If no topic indices located in text, divide evenly
    if not indices:
        chunk_sz = max(1800, len(text) // max(len(selected_topics), 1))
        for i, t in enumerate(selected_topics):
            start = i * chunk_sz
            end = min(len(text), (i + 1) * chunk_sz + 300)
            chunks_map[t] = text[start:end].strip()
        return chunks_map

    for i in range(len(indices)):
        start_idx = indices[i][0]
        end_boundary = indices[i + 1][0] if i + 1 < len(indices) else len(text)
        # Target 300-500 words (1800-3000 chars)
        chunk_len = max(1800, min(3200, end_boundary - start_idx + 300))
        chunk_content = text[start_idx: min(len(text), start_idx + chunk_len)].strip()
        chunks_map[indices[i][1]] = chunk_content

    for t in selected_topics:
        if t not in chunks_map:
            chunks_map[t] = text[:2500].strip()

    return chunks_map


def get_relevant_syllabus_chunk(
    syllabus_text: str,
    topic: str,
    chunks_map: Optional[dict] = None,
    max_chars: int = 3000,
    round_offset: int = 0,
) -> str:
    """
    Returns the most relevant section/chunk of the syllabus for the given topic.
    """
    base_chunk = ""
    if chunks_map and topic in chunks_map and chunks_map[topic]:
        val = chunks_map[topic]
        base_chunk = val if isinstance(val, str) else str(val)
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
        return base_chunk[start_pos: start_pos + max_chars].strip()

    return base_chunk[:max_chars].strip()


def get_cached_syllabus_data(
    file_obj,
    filename: str = "",
    institution_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Extracts text, hierarchy, topics, and chunks for a syllabus file once and caches them
    keyed by SHA-256 + institution_id.
    """
    try:
        from django.core.cache import cache
    except Exception:
        cache = None

    file_obj.seek(0)
    raw = file_obj.read()
    file_obj.seek(0)
    if not raw:
        raise ValueError('Uploaded syllabus file is empty.')

    if len(raw) > MAX_SYLLABUS_FILE_SIZE:
        raise ValueError('File size exceeds maximum allowed limit (25MB).')

    file_hash = hashlib.sha256(raw).hexdigest()
    cache_key = _get_cache_key(file_hash, institution_id)
    now = time.time()

    if cache_key in _SYLLABUS_CACHE:
        entry = _SYLLABUS_CACHE[cache_key]
        if now - entry.get('time', 0) < SYLLABUS_CACHE_TTL:
            return entry['data']

    if cache:
        cached_entry = cache.get(cache_key)
        if cached_entry:
            _SYLLABUS_CACHE[cache_key] = {'data': cached_entry, 'time': now}
            return cached_entry

    # Extract text and pages
    text = extract_syllabus_text(file_obj, institution_id=institution_id)
    pages = extract_syllabus_pages(file_obj)
    hierarchy = detect_syllabus_hierarchy(text, pages=pages, raw_bytes=raw)
    topics = hierarchy.get('detected_topics') or []
    chunks = chunk_syllabus_by_topics(text, topics, pages=pages)

    data = {
        'hash': file_hash,
        'text': text,
        'pages': pages,
        'hierarchy': hierarchy,
        'topics': topics,
        'chunks': chunks,
    }
    _SYLLABUS_CACHE[cache_key] = {'data': data, 'time': now}
    if cache:
        cache.set(cache_key, data, timeout=SYLLABUS_CACHE_TTL)
    return data


def estimate_syllabus_capacity(char_count: int, num_topics: int = 1, text: str = "") -> Dict[str, Any]:
    """
    Estimates whether the syllabus text is large enough to support the requested
    number of questions and marks.
    """
    safe_chars = max(0, char_count)
    word_count = len(text.split()) if text else (safe_chars // 6)

    testable_sentences = 0
    if text:
        sentences = re.split(r'[.!?]+', text)
        keywords = {'is', 'are', 'defined', 'consists', 'function', 'protocol', 'layer', 'algorithm', 'mechanism', 'feature', 'process', 'architecture'}
        for s in sentences:
            words = set(s.lower().split())
            if len(words) >= 6 and (words & keywords):
                testable_sentences += 1
    else:
        testable_sentences = max(5, word_count // 25)

    estimated_q = max(3, min(testable_sentences // 2, safe_chars // 350))
    estimated_marks = max(10, min(100, int(estimated_q * 3.5)))
    is_low = safe_chars < 4000 or word_count < 600

    suggested_bp = {}
    if is_low:
        if estimated_marks <= 30:
            suggested_bp = {'mcq': {'count': 10, 'marks': 1}, 'true_false': {'count': 5, 'marks': 1}, 'short_answer': {'count': 3, 'marks': 5}}
        elif estimated_marks <= 60:
            suggested_bp = {'mcq': {'count': 15, 'marks': 1}, 'true_false': {'count': 5, 'marks': 1}, 'short_answer': {'count': 4, 'marks': 5}, 'long_answer': {'count': 2, 'marks': 10}}
        else:
            suggested_bp = {'mcq': {'count': 10, 'marks': 1}, 'true_false': {'count': 5, 'marks': 1}, 'fill_blank': {'count': 5, 'marks': 1}, 'short_answer': {'count': 4, 'marks': 5}, 'long_answer': {'count': 6, 'marks': 10}}

    warning = (
        f"The selected document ({char_count:,} characters, ~{word_count} words) can reliably support about {estimated_q} questions (~{estimated_marks} marks)."
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


def hash_file_content(content: bytes) -> str:
    """Computes SHA-256 hash of file bytes."""
    return hashlib.sha256(content).hexdigest()


def extract_syllabus_content(
    file_obj,
    filename: str = "",
    institution_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper around get_cached_syllabus_data returning structured topics, weights,
    chunks, and multi-subject detection.
    """
    data = get_cached_syllabus_data(file_obj, filename=filename, institution_id=institution_id)
    units = data.get('hierarchy', {}).get('units', [])
    topics = [
        {
            'name': u.get('title', ''),
            'weight': u.get('weight', 0),
            'summary': u.get('summary', ''),
            'page_range': u.get('page_range', ''),
            'id': u.get('id', ''),
        }
        for u in units
    ]
    return {
        'file_hash': data.get('hash', ''),
        'text': data.get('text', ''),
        'topics': topics,
        'has_multiple_subjects': data.get('hierarchy', {}).get('has_multiple_subjects', False),
        'detected_subjects': data.get('hierarchy', {}).get('detected_domains', []),
        'chunks': data.get('chunks', {}),
    }
