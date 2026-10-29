"""
Downloadable Sample Question Bank Templates Generator.
Generates valid sample files in CSV, XLSX, DOCX, and JSON formats.
"""

import io
import json
from typing import Dict, List, Tuple

SAMPLE_QUESTIONS: List[Dict[str, str]] = [
    {
        "question_text": "What is the average case time complexity of QuickSort?",
        "question_type": "mcq",
        "marks": "2",
        "options": "O(n)|O(n log n)|O(n^2)|O(log n)",
        "correct_answer": "B",
        "difficulty": "medium",
        "topic": "Divide and Conquer",
        "explanation": "QuickSort achieves O(n log n) expected time on average through balanced partitioning.",
    },
    {
        "question_text": "In a max-heap, the root node always contains the largest key in the tree.",
        "question_type": "true_false",
        "marks": "1",
        "options": "True|False",
        "correct_answer": "True",
        "difficulty": "easy",
        "topic": "Heaps and Priority Queues",
        "explanation": "The max-heap property dictates that every parent is greater than or equal to its children.",
    },
    {
        "question_text": "The data structure used to implement Breadth-First Search (BFS) is a ________.",
        "question_type": "fill_blank",
        "marks": "2",
        "options": "",
        "correct_answer": "queue",
        "difficulty": "easy",
        "topic": "Graph Algorithms",
        "explanation": "BFS uses a FIFO queue to visit vertices level by level.",
    },
    {
        "question_text": "Explain the difference between a process and a thread in modern operating systems.",
        "question_type": "short_answer",
        "marks": "5",
        "options": "",
        "correct_answer": "A process has an independent memory address space and OS resources. A thread is an execution unit within a process that shares memory and file descriptors with sibling threads.",
        "difficulty": "medium",
        "topic": "Operating Systems",
        "explanation": "Context switching between threads is faster than between processes due to shared address space.",
    },
    {
        "question_text": "Explain Dijkstra's shortest path algorithm. Detail the greedy choice property, data structure used, and worst-case time complexity with a min-priority queue.",
        "question_type": "long_answer",
        "marks": "10",
        "options": "",
        "correct_answer": "1. Initialization of distance array and priority queue. 2. Greedy extraction of minimum distance vertex. 3. Edge relaxation. 4. Complexity O((V + E) log V).",
        "difficulty": "hard",
        "topic": "Shortest Paths",
        "explanation": "Dijkstra requires non-negative edge weights to guarantee optimal substructure correctness.",
    },
]

HEADERS = [
    "question_text",
    "question_type",
    "marks",
    "options",
    "correct_answer",
    "difficulty",
    "topic",
    "explanation",
]


def generate_template_csv() -> Tuple[bytes, str, str]:
    import csv
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(HEADERS)
    for q in SAMPLE_QUESTIONS:
        writer.writerow([q.get(h, '') for h in HEADERS])
    content = out.getvalue().encode('utf-8-sig')
    return content, 'text/csv; charset=utf-8', 'question_bank_template.csv'


def generate_template_xlsx() -> Tuple[bytes, str, str]:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Question Bank Template"

    # Header styling
    ws.append(HEADERS)
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    for col_idx in range(1, len(HEADERS) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for q in SAMPLE_QUESTIONS:
        ws.append([q.get(h, '') for h in HEADERS])

    # Auto-fit column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(40, max(14, max_len + 3))

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return (
        out.getvalue(),
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'question_bank_template.xlsx',
    )


def generate_template_docx() -> Tuple[bytes, str, str]:
    import docx
    from docx.shared import Inches, Pt, RGBColor

    doc = docx.Document()
    title = doc.add_heading("Question Bank Import Template", level=1)
    p = doc.add_paragraph("Instructions: Fill out each row in the table below. Do not modify or remove the header row.")
    p.runs[0].font.size = Pt(10)
    p.runs[0].font.italic = True

    table = doc.add_table(rows=1, cols=len(HEADERS))
    table.style = 'Light Grid Accent 1'

    hdr_cells = table.rows[0].cells
    for idx, h in enumerate(HEADERS):
        hdr_cells[idx].text = h
        hdr_cells[idx].paragraphs[0].runs[0].font.bold = True
        hdr_cells[idx].paragraphs[0].runs[0].font.size = Pt(9)

    for q in SAMPLE_QUESTIONS:
        row_cells = table.add_row().cells
        for idx, h in enumerate(HEADERS):
            row_cells[idx].text = str(q.get(h, ''))
            row_cells[idx].paragraphs[0].runs[0].font.size = Pt(9)

    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return (
        out.getvalue(),
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'question_bank_template.docx',
    )


def generate_template_json() -> Tuple[bytes, str, str]:
    data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "description": "Question Bank Import File for Exam Platform",
        "questions": SAMPLE_QUESTIONS,
    }
    content = json.dumps(data, indent=2).encode('utf-8')
    return content, 'application/json; charset=utf-8', 'question_bank_template.json'


def get_template(fmt: str) -> Tuple[bytes, str, str]:
    f = str(fmt).strip().lower()
    if f == 'xlsx':
        return generate_template_xlsx()
    if f == 'docx':
        return generate_template_docx()
    if f == 'json':
        return generate_template_json()
    return generate_template_csv()
