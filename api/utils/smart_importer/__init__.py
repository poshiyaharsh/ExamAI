"""
Smart Question Bank Importer Package.
"""

from typing import Any, Dict, List, Optional

from .ai_extractor import extract_questions_with_ai
from .documents import analyze_document
from .normalizer import (
    STATUS_INVALID,
    STATUS_NEEDS_REVIEW,
    STATUS_READY,
    normalize_smart_question_row,
)
from .spreadsheet import analyze_spreadsheet
from .synonyms import COLUMN_TARGETS


def analyze_file_for_smart_import(
    file_bytes: bytes,
    filename: str,
    custom_mapping: Optional[Dict[str, str]] = None,
    sheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Step 1 & 2: Analyzes file container, detects structure, detects headers and mapping.
    Works for CSV, XLSX, DOCX, PDF, and TXT without needing a template.
    """
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    if ext not in ('csv', 'xlsx', 'docx', 'pdf', 'txt', 'json'):
        raise ValueError(f"Unsupported file extension '.{ext}'. Supported: CSV, XLSX, DOCX, PDF, TXT, JSON.")

    if ext in ('csv', 'xlsx'):
        analysis = analyze_spreadsheet(
            file_bytes=file_bytes,
            file_format=ext,
            custom_mapping=custom_mapping,
            sheet_name=sheet_name,
        )
    elif ext in ('docx', 'pdf', 'txt'):
        analysis = analyze_document(
            file_bytes=file_bytes,
            file_format=ext,
        )
    elif ext == 'json':
        import json
        from .spreadsheet import sanitize_cell_value
        data = json.loads(file_bytes.decode('utf-8'))
        items = data if isinstance(data, list) else (data.get('questions') or data.get('data') or [])
        records = []
        for idx, item in enumerate(items, start=1):
            if isinstance(item, dict):
                records.append({
                    '_row_number': idx,
                    'question_text': item.get('question_text') or item.get('text') or '',
                    'question_type': item.get('question_type') or item.get('type') or '',
                    'marks': item.get('marks') or 1.0,
                    'difficulty': item.get('difficulty') or 'medium',
                    'topic': item.get('topic') or '',
                    'options': item.get('options') or [],
                    'correct_answer': item.get('correct_answer') or item.get('answer') or '',
                    'explanation': item.get('explanation') or '',
                })
        analysis = {
            'format': 'json',
            'total_data_rows': len(records),
            'records': records,
        }
    else:
        raise ValueError(f"Unsupported format '{ext}'.")

    return analysis


def parse_and_normalize_smart_import(
    file_bytes: bytes,
    filename: str,
    custom_mapping: Optional[Dict[str, str]] = None,
    default_marks: float = 1.0,
    default_difficulty: str = 'medium',
    default_type: Optional[str] = None,
    sheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Step 3: Converts raw records into normalized questions with validation status
    (READY, NEEDS_REVIEW, INVALID) and comprehensive statistics.
    """
    analysis = analyze_file_for_smart_import(
        file_bytes=file_bytes,
        filename=filename,
        custom_mapping=custom_mapping,
        sheet_name=sheet_name,
    )

    raw_records = analysis.get('records') or []
    normalized_rows = []
    ready_count = 0
    needs_review_count = 0
    invalid_count = 0
    duplicate_count = 0
    all_errors = []
    all_warnings = []
    seen_hashes = set()

    for idx, raw in enumerate(raw_records, start=1):
        norm = normalize_smart_question_row(
            raw_row=raw,
            row_idx=idx,
            default_marks=default_marks,
            default_difficulty=default_difficulty,
            default_type=default_type,
            seen_hashes=seen_hashes,
        )
        norm['warnings'] = norm.get('review_notes', [])

        if norm.get('is_duplicate'):
            duplicate_count += 1

        if norm['status'] == STATUS_READY:
            ready_count += 1
        elif norm['status'] == STATUS_NEEDS_REVIEW:
            needs_review_count += 1
        else:
            invalid_count += 1

        all_errors.extend(norm.get('errors', []))
        all_warnings.extend(norm.get('warnings', []))

        normalized_rows.append(norm)

    return {
        'filename': filename,
        'format': analysis.get('format'),
        'metadata': analysis.get('metadata', {}),
        'columns': analysis.get('columns', []),
        'header_row_index': analysis.get('header_row_index'),
        'sheet_names': analysis.get('sheet_names', []),
        'selected_sheet': analysis.get('selected_sheet'),
        'total_rows': len(normalized_rows),
        'ready_count': ready_count,
        'needs_review_count': needs_review_count,
        'invalid_count': invalid_count,
        'valid_count': ready_count + needs_review_count,
        'duplicate_count': duplicate_count,
        'has_errors': invalid_count > 0,
        'errors': all_errors,
        'warnings': all_warnings,
        'preview_rows': normalized_rows[:15],
        'all_rows': normalized_rows,
    }
