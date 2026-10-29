"""
Smart Document Parser for Question Bank Import (DOCX, PDF, TXT).
Handles unstructured word documents, PDFs, trailing answer keys,
unlettered options, marks in brackets, and topic headings.
"""

import io
import re
from typing import Any, Dict, List, Optional, Tuple

import docx
import pymupdf


def extract_docx_text_and_tables(file_bytes: bytes) -> Tuple[List[str], List[List[List[str]]]]:
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    tables_data = []
    for t in doc.tables:
        grid = []
        for r in t.rows:
            row_cells = [c.text.strip() for c in r.cells]
            if any(row_cells):
                grid.append(row_cells)
        if grid:
            tables_data.append(grid)

    return paragraphs, tables_data


def extract_pdf_text_lines(file_bytes: bytes) -> Tuple[List[str], bool, int]:
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    page_count = len(doc)
    total_chars = 0
    pages_lines = []

    line_page_occurrences: Dict[str, int] = {}

    for page in doc:
        txt = page.get_text()
        total_chars += len(txt.strip())
        cur_page_lines = []
        seen_on_page = set()
        for l in txt.splitlines():
            s = l.strip()
            # Strip page number footers
            if re.match(r'^(?:page\s+\d+(?:\s+of\s+\d+)?|\d+\s*/\s*\d+)$', s, re.IGNORECASE):
                continue
            if s:
                cur_page_lines.append(s)
                if s not in seen_on_page:
                    line_page_occurrences[s] = line_page_occurrences.get(s, 0) + 1
                    seen_on_page.add(s)
        pages_lines.append(cur_page_lines)

    # Scanned PDF check
    is_scanned = (total_chars < 50) or (page_count > 0 and (total_chars / page_count) < 20)

    # Strip running headers (lines appearing on more than half the pages)
    all_lines = []
    for page_l in pages_lines:
        for line in page_l:
            if page_count > 2 and line_page_occurrences.get(line, 0) >= (page_count // 2):
                continue
            all_lines.append(line)

    return all_lines, is_scanned, page_count


def extract_txt_lines(file_bytes: bytes) -> List[str]:
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            text = file_bytes.decode(enc)
            return [l.strip() for l in text.splitlines() if l.strip()]
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode text file. Must be valid UTF-8, Windows-1252, or Latin-1 text.")


RE_QUESTION_START = re.compile(
    r'^(?:(?:q(?:ue(?:stion)?)?|problem|[a-zA-Z]?)\s*[\.\:\-\)]?\s*(\d+)|(\d+)[\.\)\:\-]|\[(\d+)\])\s*(.*)$',
    re.IGNORECASE
)

RE_OPTION_PREFIX = re.compile(
    r'^(?:[\(\[]?([A-Fa-f0-9])[\)\]\.\:\-]\s*|\(([A-Fa-f0-9])\)\s*)(.+)$'
)

RE_ANSWER_LINE = re.compile(
    r'^(?:correct\s*answers?|answers?|key|solutions?|right\s*answers?)\s*[:\-]\s*(.+)$',
    re.IGNORECASE
)

RE_EXPLANATION_LINE = re.compile(
    r'^(?:explanations?|rationales?|solution\s*descriptions?|reasons?|notes?)\s*[:\-]\s*(.+)$',
    re.IGNORECASE
)

RE_MARKS_TAG = re.compile(
    r'(?:\[|\()(\d+(?:\.\d+)?)\s*(?:m|marks?|pts?|points?)(?:\]|\))',
    re.IGNORECASE
)

RE_TOPIC_HEADING = re.compile(
    r'^(?:topics?\s*covered|unit\s*\d*|chapter\s*\d*|module\s*\d*)\s*[:\-]?\s*(.*)$',
    re.IGNORECASE
)

RE_PREAMBLE_PATTERNS = re.compile(
    r'^(?:instructions?|topics?\s*covered|choose\s*one\s*best\s*answer|full\s*question\s*paper|time\s*:\s*\d+|\d*\s*multiple[\s\-]*choice.*|\d*\s*mcqs?\b|attempt\s*all\s*questions|examination\s*\d*|department\s*of\s*|questions?\s*with\s*answers?|data\s*structures\s*&).*$',
    re.IGNORECASE
)


def parse_trailing_answer_keys(lines: List[str]) -> Tuple[Dict[int, str], int]:
    key_start_idx = -1
    for idx, l in enumerate(lines):
        if re.match(r'^(?:answers?\s*key|answer\s*keys?|solutions?\s*key|key\s*answers?)\s*[:\-]?$', l, re.IGNORECASE):
            key_start_idx = idx
            break

    if key_start_idx == -1:
        return {}, -1

    answer_map: Dict[int, str] = {}
    key_lines = lines[key_start_idx + 1:]

    for l in key_lines:
        pairs = re.findall(r'(\d+)[\.\)\:\-]\s*([A-Za-z0-9]+(?:\.[^\s]+)?)', l)
        for q_num_str, ans_str in pairs:
            try:
                answer_map[int(q_num_str)] = ans_str.strip()
            except ValueError:
                pass

    return answer_map, key_start_idx


def parse_document_blocks(lines: List[str]) -> List[Dict[str, Any]]:
    if not lines:
        return []

    trailing_keys, key_split_idx = parse_trailing_answer_keys(lines)
    content_lines = lines[:key_split_idx] if key_split_idx != -1 else lines

    questions: List[Dict[str, Any]] = []
    current_q: Optional[Dict[str, Any]] = None
    current_topic = ""
    raw_buffer_lines: List[str] = []

    def flush_current_q():
        nonlocal current_q, raw_buffer_lines
        if not current_q:
            return

        # Sift unlettered options from buffer if options are empty
        if not current_q.get('options') and raw_buffer_lines:
            # If buffer has more than 4 lines, options are the last 4 lines before the answer
            if len(raw_buffer_lines) > 4:
                opts = raw_buffer_lines[-4:]
                preceding = [current_q.get('question_text', '')] + raw_buffer_lines[:-4]
                # Find true question stem
                best_stem = None
                for candidate in reversed(preceding):
                    if candidate.endswith('?') or any(candidate.lower().startswith(w) for w in ('which', 'what', 'how', 'why', 'in ', 'where', 'when', 'is ')):
                        best_stem = candidate
                        break
                if best_stem:
                    current_q['question_text'] = best_stem
                current_q['options'] = opts
            else:
                current_q['options'] = list(raw_buffer_lines)
            raw_buffer_lines = []

        # Reject document preamble before question 1 if it has no options and no answer
        if len(questions) == 0 and not current_q.get('correct_answer') and not current_q.get('options'):
            current_q = None
            raw_buffer_lines = []
            return

        q_text = current_q.get('question_text', '').strip()
        # Clean leading numbers
        q_text = re.sub(r'^(?:[A-Za-z]?\d+[\.\)\:\-]\s*|\([A-Za-z]?\d+\)\s*)', '', q_text).strip()
        current_q['question_text'] = q_text

        # Validate minimum text length and reject obvious non-question titles
        if q_text and len(q_text) >= 5 and not RE_PREAMBLE_PATTERNS.match(q_text):
            q_num = current_q.get('_q_num')
            if not current_q.get('correct_answer') and q_num and q_num in trailing_keys:
                current_q['correct_answer'] = trailing_keys[q_num]

            if current_topic and not current_q.get('topic'):
                current_q['topic'] = current_topic

            questions.append(current_q)

        current_q = None
        raw_buffer_lines = []

    for idx, raw_line in enumerate(content_lines):
        line = raw_line.strip()
        if not line:
            continue

        # Topic Heading check
        topic_m = RE_TOPIC_HEADING.match(line)
        if topic_m:
            captured = topic_m.group(1).strip()
            if captured:
                current_topic = captured
            continue

        # Skip preamble lines
        if RE_PREAMBLE_PATTERNS.match(line):
            continue

        # Check Answer Line
        ans_m = RE_ANSWER_LINE.match(line)
        if ans_m:
            if current_q:
                current_q['correct_answer'] = ans_m.group(1).strip()
                if raw_buffer_lines and not current_q.get('options'):
                    if len(raw_buffer_lines) > 4:
                        current_q['options'] = raw_buffer_lines[-4:]
                        preceding = [current_q.get('question_text', '')] + raw_buffer_lines[:-4]
                        for cand in reversed(preceding):
                            if cand.endswith('?') or any(cand.lower().startswith(w) for w in ('which', 'what', 'how', 'why', 'in ', 'where', 'when', 'is ')):
                                current_q['question_text'] = cand
                                break
                    else:
                        current_q['options'] = list(raw_buffer_lines)
                    raw_buffer_lines = []
            continue

        # Check Explanation Line
        exp_m = RE_EXPLANATION_LINE.match(line)
        if exp_m:
            if current_q:
                current_q['explanation'] = exp_m.group(1).strip()
            continue

        # Check Lettered Option line (A. Apple, (b) Banana)
        opt_m = RE_OPTION_PREFIX.match(line)
        if opt_m and current_q and not current_q.get('correct_answer'):
            letter = (opt_m.group(1) or opt_m.group(2)).upper()
            opt_text = opt_m.group(3).strip()
            if 'options_dict' not in current_q:
                current_q['options_dict'] = {}
            current_q['options_dict'][letter] = opt_text
            current_q['options'] = [current_q['options_dict'][k] for k in sorted(current_q['options_dict'].keys())]
            continue

        # If current question has already captured its answer, this line belongs to the NEXT question
        if current_q and current_q.get('correct_answer'):
            flush_current_q()

        # Check Question Start
        q_start_m = RE_QUESTION_START.match(line)
        is_real_q_start = False
        if q_start_m:
            stem_candidate = q_start_m.group(4).strip()
            if stem_candidate and ('?' in stem_candidate or len(stem_candidate) > 10 or any(stem_candidate.lower().startswith(w) for w in ('which', 'what', 'how', 'why', 'in ', 'where', 'when', 'is ', 'the ', 'a '))):
                is_real_q_start = True

        if is_real_q_start and q_start_m:
            flush_current_q()
            q_num_str = q_start_m.group(1) or q_start_m.group(2) or q_start_m.group(3)
            q_num = int(q_num_str) if q_num_str else len(questions) + 1
            stem_text = q_start_m.group(4).strip()

            marks_val = 1
            marks_m = RE_MARKS_TAG.search(stem_text)
            if marks_m:
                try:
                    marks_val = float(marks_m.group(1))
                    stem_text = RE_MARKS_TAG.sub('', stem_text).strip()
                except ValueError:
                    pass

            current_q = {
                '_row_number': idx + 1,
                '_q_num': q_num,
                'question_text': stem_text,
                'marks': marks_val,
                'options': [],
                'correct_answer': '',
                'explanation': '',
                'topic': current_topic,
            }
            continue

        # Non-Numbered Question Stems or question continuation
        if not current_q:
            current_q = {
                '_row_number': idx + 1,
                '_q_num': len(questions) + 1,
                'question_text': line,
                'marks': 1,
                'options': [],
                'correct_answer': '',
                'explanation': '',
                'topic': current_topic,
            }
            continue

        # If inside a question and before answer line, accumulate in buffer
        if current_q and not current_q.get('correct_answer'):
            raw_buffer_lines.append(line)

    flush_current_q()
    return questions


def analyze_document(file_bytes: bytes, file_format: str) -> Dict[str, Any]:
    if file_format == 'docx':
        paragraphs, tables = extract_docx_text_and_tables(file_bytes)
        if tables and len(tables[0]) >= 2 and len(tables[0][0]) >= 2:
            grid = tables[0]
            from .spreadsheet import detect_header_row, match_column_name, TARGET_IGNORE
            header_idx = detect_header_row(grid)
            raw_headers = [str(c).strip() for c in grid[header_idx]]
            data_rows = grid[header_idx + 1:]
            records = []
            for r_idx, r in enumerate(data_rows, start=header_idx + 2):
                rec = {'_row_number': r_idx, 'options': []}
                for c_idx, val in enumerate(r):
                    t, _ = match_column_name(raw_headers[c_idx] if c_idx < len(raw_headers) else f"col_{c_idx}")
                    if t != TARGET_IGNORE:
                        rec[t] = str(val).strip()
                if rec.get('question_text'):
                    records.append(rec)
            if records:
                return {
                    'format': 'docx_table',
                    'total_data_rows': len(records),
                    'records': records,
                }

        records = parse_document_blocks(paragraphs)
        return {
            'format': 'docx',
            'total_data_rows': len(records),
            'records': records,
        }

    elif file_format == 'pdf':
        lines, is_scanned, page_count = extract_pdf_text_lines(file_bytes)
        if is_scanned:
            raise ValueError(
                "This PDF appears to be a scanned image or contains no selectable text. "
                "Smart Import requires a text-based PDF or document."
            )
        records = parse_document_blocks(lines)
        return {
            'format': 'pdf',
            'page_count': page_count,
            'total_data_rows': len(records),
            'records': records,
        }

    elif file_format == 'txt':
        lines = extract_txt_lines(file_bytes)
        records = parse_document_blocks(lines)
        return {
            'format': 'txt',
            'total_data_rows': len(records),
            'records': records,
        }

    else:
        raise ValueError(f"Unsupported document format '{file_format}'.")
