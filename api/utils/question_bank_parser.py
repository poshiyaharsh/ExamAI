"""
Secure Multi-Format Question Bank Parser Engine.
Supports: CSV, XLSX, DOCX, JSON.

Security & Validation:
- Max file size: 10 MB.
- Max row count: 500 rows.
- Magic bytes & container verification (rejects fake extensions, EXE, ELF, macros/VBA).
- Formula injection protection (strips leading '=', '+', '-', '@', '\\t', '\\r').
- Row-by-row transactional validation with comprehensive error reporting.
"""

import csv
import io
import json
import os
import re
import unicodedata
import zipfile
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

logger = __import__('logging').getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ROWS = 2000

DANGEROUS_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')
DANGEROUS_BIN_HEADERS = (b'MZ', b'\x7fELF')


def sanitize_cell_value(val: Any) -> Any:
    """Neutralize Excel/CSV formula injection and strip trailing/leading whitespace."""
    if val is None:
        return ''
    if isinstance(val, (int, float, Decimal)):
        return val
    s = str(val).strip()
    # Strip dangerous formula injection prefixes
    while s and s[0] in DANGEROUS_FORMULA_PREFIXES:
        s = s[1:].strip()
    return s


def canonicalize_type(raw_type: Optional[str]) -> str:
    """Normalize question type variants into canonical system types."""
    if not raw_type:
        return 'mcq'
    t = str(raw_type).strip().lower().replace('-', '_').replace(' ', '_')
    if t in ('mcq', 'mcq_single', 'multiple_choice', 'single_choice', 'mcqs'):
        return 'mcq'
    if t in ('true_false', 'truefalse', 't_f', 'tf', 'boolean', 'true_or_false'):
        return 'true_false'
    if t in ('fill_blank', 'fillblank', 'fill_in_the_blank', 'fib', 'blank'):
        return 'fill_blank'
    if t in ('short_answer', 'shortanswer', 'short', 'sa', 'brief'):
        return 'short_answer'
    if t in ('long_answer', 'longanswer', 'long', 'la', 'descriptive', 'subjective', 'essay'):
        return 'long_answer'
    return 'mcq'


def canonicalize_difficulty(raw_diff: Optional[str]) -> str:
    if not raw_diff:
        return 'medium'
    d = str(raw_diff).strip().lower()
    if d in ('easy', 'beginner', 'basic', 'low', '1'):
        return 'easy'
    if d in ('hard', 'difficult', 'advanced', 'expert', 'high', '3'):
        return 'hard'
    return 'medium'


def validate_file_signature(file_bytes: bytes, filename: str) -> str:
    """
    Validates file size, extension, and real binary container signatures.
    Returns normalized format: 'csv', 'xlsx', 'docx', 'json'.
    Raises ValueError with a user-friendly error message on violation.
    """
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds 10MB limit ({len(file_bytes) / (1024 * 1024):.1f}MB).")

    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    if ext not in ('csv', 'xlsx', 'docx', 'json', 'pdf', 'txt'):
        raise ValueError("Unsupported file extension. Only .csv, .xlsx, .docx, .json, .pdf, and .txt files are accepted.")

    # Reject binary executable headers disguised with another extension
    for bad_header in DANGEROUS_BIN_HEADERS:
        if file_bytes.startswith(bad_header):
            raise ValueError(f"File contents do not match the .{ext} extension (detected unsupported binary header).")

    if ext != 'pdf' and file_bytes.startswith(b'%PDF'):
        raise ValueError(f"File contents do not match the .{ext} extension (detected PDF header in non-PDF file).")

    if ext in ('xlsx', 'docx'):
        # Must be a valid zip archive
        if not file_bytes.startswith(b'PK\x03\x04'):
            raise ValueError(f"Invalid .{ext} file: missing valid OpenXML package signature.")
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
                namelist = zf.namelist()
                # Check for malicious VBA macros
                if any('vbaproject.bin' in name.lower() for name in namelist):
                    raise ValueError("Macro-enabled documents (.xlsm, .docm or VBA macros) are strictly forbidden.")
                if ext == 'xlsx':
                    if not any('xl/workbook.xml' in name for name in namelist):
                        raise ValueError("Invalid .xlsx file: missing workbook spreadsheet structure.")
                elif ext == 'docx':
                    if not any('word/document.xml' in name for name in namelist):
                        raise ValueError("Invalid .docx file: missing Word document structure.")
        except zipfile.BadZipFile:
            raise ValueError(f"Corrupted or invalid .{ext} archive.")

    elif ext == 'json':
        try:
            text = file_bytes.decode('utf-8')
            json.loads(text)
        except UnicodeDecodeError:
            raise ValueError("JSON file must be UTF-8 encoded text.")
        except json.JSONDecodeError as err:
            raise ValueError(f"Malformed JSON: {err}")

    elif ext == 'csv':
        # Must decode cleanly as text
        decoded = None
        for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                decoded = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise ValueError("CSV file must be valid UTF-8 or Latin-1 text.")

    elif ext == 'pdf':
        if not file_bytes.startswith(b'%PDF'):
            raise ValueError("Invalid .pdf file: missing standard PDF header (%PDF).")

    elif ext == 'txt':
        decoded = None
        for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
            try:
                decoded = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise ValueError("Text file must be valid UTF-8, CP1252, or Latin-1 text.")

    return ext


def parse_csv(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse CSV text with encoding fallback and header normalization."""
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    reader = csv.reader(io.StringIO(text))
    rows = []
    headers = None
    for row in reader:
        if not row or not any(cell.strip() for cell in row):
            continue
        cleaned_cells = [sanitize_cell_value(c) for c in row]
        if headers is None:
            headers = [str(c).strip().lower().replace(' ', '_') for c in cleaned_cells]
            continue
        row_dict = {}
        for idx, val in enumerate(cleaned_cells):
            key = headers[idx] if idx < len(headers) else f"col_{idx}"
            row_dict[key] = val
        rows.append(row_dict)
    return rows


def parse_xlsx(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse Excel workbook data cells without formula execution."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    rows = []
    headers = None
    for row in ws.iter_rows(values_only=True):
        if not row or not any(row):
            continue
        cleaned_cells = [sanitize_cell_value(c) for c in row]
        if headers is None:
            headers = [str(c).strip().lower().replace(' ', '_') for c in cleaned_cells]
            continue
        row_dict = {}
        for idx, val in enumerate(cleaned_cells):
            key = headers[idx] if idx < len(headers) else f"col_{idx}"
            row_dict[key] = val
        rows.append(row_dict)
    return rows


def parse_docx(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parse DOCX document.
    Prioritizes structured tables; falls back to structured numbered paragraphs.
    """
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    rows = []

    # 1. Attempt table extraction first
    if doc.tables:
        table = doc.tables[0]
        headers = None
        for row in table.rows:
            cell_texts = [sanitize_cell_value(cell.text) for cell in row.cells]
            if not any(cell_texts):
                continue
            if headers is None:
                headers = [str(c).strip().lower().replace(' ', '_') for c in cell_texts]
                continue
            row_dict = {}
            for idx, val in enumerate(cell_texts):
                key = headers[idx] if idx < len(headers) else f"col_{idx}"
                row_dict[key] = val
            rows.append(row_dict)
        if rows:
            return rows

    # 2. Structured paragraph extraction fallback
    # Example format:
    # 1. [MCQ] [2 marks] Question text here?
    # Options: A|B|C|D
    # Answer: B
    current_q: Dict[str, Any] = {}
    for p in doc.paragraphs:
        txt = sanitize_cell_value(p.text)
        if not txt:
            continue
        m = re.match(r'^(?:\d+[\.\)]\s*)?(?:\[([A-Za-z_\s]+)\])?\s*(?:\[(\d+(?:\.\d+)?)\s*(?:m|marks)?\])?\s*(.+)$', txt, re.IGNORECASE)
        if m and ('?' in txt or len(txt) > 20):
            if current_q and current_q.get('question_text'):
                rows.append(current_q)
            current_q = {
                'question_type': m.group(1) or 'mcq',
                'marks': m.group(2) or '1',
                'question_text': m.group(3) or '',
            }
        elif current_q:
            if txt.lower().startswith('options:'):
                current_q['options'] = txt.split(':', 1)[1].strip()
            elif txt.lower().startswith('answer:'):
                current_q['correct_answer'] = txt.split(':', 1)[1].strip()
            elif txt.lower().startswith('explanation:'):
                current_q['explanation'] = txt.split(':', 1)[1].strip()
            elif txt.lower().startswith('topic:'):
                current_q['topic'] = txt.split(':', 1)[1].strip()
            elif txt.lower().startswith('difficulty:'):
                current_q['difficulty'] = txt.split(':', 1)[1].strip()

    if current_q and current_q.get('question_text'):
        rows.append(current_q)

    return rows


def parse_json_content(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse JSON structure supporting list of dicts or {'questions': [...]}."""
    data = json.loads(file_bytes.decode('utf-8'))
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get('questions') or data.get('data') or data.get('items') or []
    else:
        items = []

    rows = []
    for item in items:
        if isinstance(item, dict):
            cleaned = {k.strip().lower(): sanitize_cell_value(v) if not isinstance(v, (list, dict)) else v for k, v in item.items()}
            rows.append(cleaned)
    return rows


def normalize_row_data(raw: Dict[str, Any], row_idx: int) -> Tuple[bool, Dict[str, Any], List[str], List[str]]:
    """
    Validates and normalizes one row into standard question payload.
    Returns: (is_valid, normalized_data, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Question Text
    text = (
        raw.get('question_text')
        or raw.get('text')
        or raw.get('question')
        or raw.get('q_text')
        or raw.get('prompt')
        or ''
    )
    if isinstance(text, str):
        text = text.strip()
    else:
        text = str(text)

    if not text or len(text) < 5:
        errors.append(f"Row {row_idx}: 'question_text' is required and must be at least 5 characters.")

    # 2. Question Type
    raw_type = raw.get('question_type') or raw.get('type') or raw.get('q_type') or 'mcq'
    q_type = canonicalize_type(str(raw_type))

    # 3. Marks
    raw_marks = raw.get('marks') or raw.get('mark') or raw.get('points') or raw.get('score')
    marks_val = 1.0
    if raw_marks is not None and str(raw_marks).strip():
        try:
            parsed_m = float(str(raw_marks).strip())
            if parsed_m <= 0:
                warnings.append(f"Row {row_idx}: marks was {parsed_m} (<= 0); defaulted to 1.0 mark.")
                marks_val = 1.0
            else:
                marks_val = parsed_m
        except ValueError:
            warnings.append(f"Row {row_idx}: invalid marks value '{raw_marks}'; defaulted to 1.0 mark.")
            marks_val = 1.0
    else:
        warnings.append(f"Row {row_idx}: marks not specified; defaulted to 1.0 mark.")
        marks_val = 1.0

    # Ensure integer marks when applicable
    if marks_val == int(marks_val):
        marks_val = int(marks_val)

    # 4. Difficulty
    raw_diff = raw.get('difficulty') or raw.get('diff') or 'medium'
    difficulty = canonicalize_difficulty(str(raw_diff))

    # 5. Topic & Subject
    topic = str(raw.get('topic') or raw.get('topic_text') or '').strip()
    subject = str(raw.get('subject') or raw.get('subject_name') or '').strip()
    department = str(raw.get('department') or '').strip()

    # 6. Options & Correct Answer Handling
    options_list: List[Dict[str, Any]] = []
    correct_answer = raw.get('correct_answer') or raw.get('answer') or raw.get('correct_option') or raw.get('correct')

    if q_type == 'mcq':
        raw_options = raw.get('options') or raw.get('choices')
        candidates: List[str] = []

        if isinstance(raw_options, list):
            candidates = [str(o).strip() for o in raw_options if str(o).strip()]
        elif isinstance(raw_options, str) and raw_options.strip():
            # Check for JSON array string
            if raw_options.strip().startswith('[') and raw_options.strip().endswith(']'):
                try:
                    parsed_opts = json.loads(raw_options)
                    if isinstance(parsed_opts, list):
                        candidates = [str(o).strip() for o in parsed_opts if str(o).strip()]
                except Exception:
                    candidates = [c.strip() for c in raw_options.split('|') if c.strip()]
            else:
                # Pipe-separated options (e.g. A|B|C|D)
                candidates = [c.strip() for c in raw_options.split('|') if c.strip()]
        else:
            # Check option_1, option_2, option_3, option_4 columns
            for o_idx in range(1, 7):
                opt_key = f"option_{o_idx}"
                if opt_key in raw and str(raw[opt_key]).strip():
                    candidates.append(str(raw[opt_key]).strip())

        if len(candidates) < 2:
            errors.append(f"Row {row_idx}: MCQ requires at least 2 distinct options (found {len(candidates)}).")

        # Determine correct option
        corr_str = str(correct_answer or '').strip()
        if not corr_str:
            errors.append(f"Row {row_idx}: MCQ requires a 'correct_answer' (option letter, index, or text).")

        matched_correct = False
        for c_idx, opt_text in enumerate(candidates):
            # Letter matching ('A', 'B', ...)
            letter = chr(65 + c_idx)
            is_corr = False
            if corr_str.upper() == letter:
                is_corr = True
            elif corr_str == str(c_idx + 1) or corr_str == str(c_idx):
                is_corr = True
            elif corr_str.lower() == opt_text.lower():
                is_corr = True

            if is_corr:
                matched_correct = True

            options_list.append({
                'text': opt_text,
                'is_correct': is_corr,
                'order': c_idx + 1,
            })

        if not matched_correct and candidates:
            # Default to first option with warning if unspecified
            warnings.append(f"Row {row_idx}: correct_answer '{corr_str}' did not match options; marked first option as correct.")
            if options_list:
                options_list[0]['is_correct'] = True

    elif q_type == 'true_false':
        corr_str = str(correct_answer or '').strip().lower()
        if not corr_str:
            errors.append(f"Row {row_idx}: True/False question requires a 'correct_answer' ('True' or 'False').")
        is_true = corr_str in ('true', 't', 'yes', '1')
        options_list = [
            {'text': 'True', 'is_correct': is_true, 'order': 1},
            {'text': 'False', 'is_correct': not is_true, 'order': 2},
        ]
        correct_answer = 'True' if is_true else 'False'

    elif q_type == 'fill_blank':
        if not correct_answer:
            errors.append(f"Row {row_idx}: Fill in the blank requires 'correct_answer' with the accepted answer string.")

    # 7. Explanation & Rubric
    explanation = str(raw.get('explanation') or raw.get('rationale') or '').strip()
    raw_rubric = raw.get('rubric') or raw.get('grading_rubric')
    rubric_list = []
    if isinstance(raw_rubric, list):
        rubric_list = raw_rubric
    elif isinstance(raw_rubric, str) and raw_rubric.strip().startswith('['):
        try:
            parsed_rub = json.loads(raw_rubric)
            if isinstance(parsed_rub, list):
                rubric_list = parsed_rub
        except Exception:
            pass

    normalized = {
        'row_number': row_idx,
        'question_text': text,
        'question_type': q_type,
        'marks': marks_val,
        'difficulty': difficulty,
        'topic': topic,
        'subject': subject,
        'department': department,
        'options': options_list,
        'correct_answer': correct_answer,
        'model_answer': str(correct_answer or explanation) if q_type in ('short_answer', 'long_answer') else '',
        'rubric': rubric_list,
        'explanation': explanation,
    }

    is_valid = len(errors) == 0
    return is_valid, normalized, errors, warnings


def parse_and_validate_question_bank_file(
    uploaded_file,
    use_smart_import: bool = False,
    custom_mapping: Optional[Dict[str, str]] = None,
    default_marks: float = 1.0,
    default_difficulty: str = 'medium',
    default_type: Optional[str] = None,
    sheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry point: safely validates file container, parses rows up to MAX_ROWS,
    normalizes all fields, and returns a detailed dry-run/preview report.
    Supports both legacy template parsing and intelligent non-template Smart Import.
    """
    filename = getattr(uploaded_file, 'name', 'question_file.csv') or 'question_file.csv'
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    file_bytes = uploaded_file.read() if hasattr(uploaded_file, 'read') else bytes(uploaded_file)

    fmt = validate_file_signature(file_bytes, filename)

    if use_smart_import or fmt in ('pdf', 'txt'):
        from api.utils.smart_importer import parse_and_normalize_smart_import
        return parse_and_normalize_smart_import(
            file_bytes=file_bytes,
            filename=filename,
            custom_mapping=custom_mapping,
            default_marks=default_marks,
            default_difficulty=default_difficulty,
            default_type=default_type,
            sheet_name=sheet_name,
        )

    if fmt == 'csv':
        raw_rows = parse_csv(file_bytes)
    elif fmt == 'xlsx':
        raw_rows = parse_xlsx(file_bytes)
    elif fmt == 'docx':
        raw_rows = parse_docx(file_bytes)
    elif fmt == 'json':
        raw_rows = parse_json_content(file_bytes)
    else:
        raise ValueError(f"Unsupported format '{fmt}'.")

    if not raw_rows:
        # Fallback to smart import if docx or xlsx has text outside standard tables/paragraphs
        try:
            from api.utils.smart_importer import parse_and_normalize_smart_import
            return parse_and_normalize_smart_import(
                file_bytes=file_bytes,
                filename=filename,
                custom_mapping=custom_mapping,
                default_marks=default_marks,
                default_difficulty=default_difficulty,
                default_type=default_type,
                sheet_name=sheet_name,
            )
        except Exception:
            raise ValueError("Uploaded file contains no question records.")

    if len(raw_rows) > MAX_ROWS:
        raise ValueError(f"File contains {len(raw_rows)} rows. Maximum allowed per import is {MAX_ROWS} rows.")

    parsed_rows = []
    valid_count = 0
    invalid_count = 0
    all_errors = []
    all_warnings = []
    seen_hashes = set()
    duplicate_count = 0

    for idx, raw in enumerate(raw_rows, start=1):
        is_valid, norm_data, errs, warns = normalize_row_data(raw, idx)
        q_hash = norm_data.get('question_text', '').strip().lower()
        is_dup = False
        if q_hash and q_hash in seen_hashes:
            is_dup = True
            duplicate_count += 1
            warns.append(f"Row {idx}: Duplicate question text detected in this file batch.")
        elif q_hash:
            seen_hashes.add(q_hash)

        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1

        all_errors.extend(errs)
        all_warnings.extend(warns)

        parsed_rows.append({
            'row_number': idx,
            'is_valid': is_valid,
            'is_duplicate': is_dup,
            'data': norm_data,
            'errors': errs,
            'warnings': warns,
        })

    # If standard template parser had 0 valid rows (e.g. non-template real faculty doc/sheet),
    # automatically attempt smart import fallback before giving up
    if valid_count == 0 and len(raw_rows) > 0:
        try:
            from api.utils.smart_importer import parse_and_normalize_smart_import
            smart_report = parse_and_normalize_smart_import(
                file_bytes=file_bytes,
                filename=filename,
                custom_mapping=custom_mapping,
                default_marks=default_marks,
                default_difficulty=default_difficulty,
                default_type=default_type,
                sheet_name=sheet_name,
            )
            if smart_report.get('valid_count', 0) > 0:
                return smart_report
        except Exception as exc:
            logger.warning("Smart import fallback attempt produced: %s", exc)

    return {
        'filename': filename,
        'format': fmt,
        'total_rows': len(raw_rows),
        'valid_count': valid_count,
        'invalid_count': invalid_count,
        'ready_count': valid_count,
        'needs_review_count': 0,
        'duplicate_count': duplicate_count,
        'has_errors': invalid_count > 0,
        'errors': all_errors,
        'warnings': all_warnings,
        'preview_rows': [r for r in parsed_rows[:15]],
        'all_rows': parsed_rows,
    }
