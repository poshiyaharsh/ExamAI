"""
DOCX Exporter for Generated Examination Papers.
Uses python-docx to generate editable Microsoft Word documents for
examination question papers and answer keys.
Supports multilingual text rendering and RTL direction when appropriate.
"""
import io
from typing import Dict, Any, List
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


def export_paper_to_docx(
    paper_data: Dict[str, Any],
    include_answers: bool = False
) -> bytes:
    """
    Renders paper_data into a DOCX binary stream.
    """
    doc = Document()

    # Set standard 0.75-inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    lang = paper_data.get('language', 'en')
    is_rtl = lang in ('ar', 'ur', 'fa', 'he')

    title = paper_data.get('title', 'Examination Paper')
    subject = paper_data.get('subject', 'General Subject')
    duration = paper_data.get('duration', 60)
    total_marks = paper_data.get('total_marks', 100)

    # Document Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run(title)
    run_title.font.name = 'Calibri'
    run_title.font.size = Pt(18)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)

    # Metadata subtitle
    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_meta = p_meta.add_run(f"Subject: {subject}  |  Duration: {duration} mins  |  Total Marks: {total_marks}")
    run_meta.font.name = 'Calibri'
    run_meta.font.size = Pt(10.5)
    run_meta.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # Questions
    questions = paper_data.get('questions', [])
    for q in questions:
        q_num = q.get('question_number', q.get('slot_index', 1))
        q_type = q.get('type', 'MCQ')
        marks = q.get('marks', 1)
        q_text = q.get('question', '')
        options = q.get('options', [])
        answer = q.get('answer', '')

        # Question header line
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_after = Pt(4)
        if is_rtl:
            p_q.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        run_num = p_q.add_run(f"Q{q_num}. ")
        run_num.font.bold = True
        run_num.font.size = Pt(11)

        run_text = p_q.add_run(f"{q_text} ")
        run_text.font.size = Pt(11)

        run_marks = p_q.add_run(f"[{marks} Marks]")
        run_marks.font.bold = True
        run_marks.font.size = Pt(10)
        run_marks.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)

        # Options for MCQ
        if q_type == 'MCQ' and options:
            opt_labels = ['(A)', '(B)', '(C)', '(D)']
            for i, opt in enumerate(options[:4]):
                lbl = opt_labels[i] if i < len(opt_labels) else f"({i+1})"
                p_opt = doc.add_paragraph()
                p_opt.paragraph_format.left_indent = Inches(0.4)
                p_opt.paragraph_format.space_after = Pt(2)
                if is_rtl:
                    p_opt.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                r_opt = p_opt.add_run(f"{lbl}  {opt}")
                r_opt.font.size = Pt(10.5)
                r_opt.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

        # Inline Answer key if requested
        if include_answers and answer:
            p_ans = doc.add_paragraph()
            p_ans.paragraph_format.left_indent = Inches(0.4)
            p_ans.paragraph_format.space_after = Pt(6)
            if is_rtl:
                p_ans.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r_ans_lbl = p_ans.add_run("Answer Key: ")
            r_ans_lbl.font.bold = True
            r_ans_lbl.font.size = Pt(10)
            r_ans_lbl.font.color.rgb = RGBColor(0x16, 0x65, 0x34)

            r_ans = p_ans.add_run(str(answer))
            r_ans.font.size = Pt(10)
            r_ans.font.color.rgb = RGBColor(0x16, 0x65, 0x34)

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Separate Answer Key Appendix if requested
    if include_answers:
        doc.add_page_break()
        p_app = doc.add_paragraph()
        p_app.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_app = p_app.add_run("Official Answer Key & Marking Scheme")
        r_app.font.size = Pt(16)
        r_app.font.bold = True

        table = doc.add_table(rows=1, cols=4)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Q#"
        hdr_cells[1].text = "Type"
        hdr_cells[2].text = "Marks"
        hdr_cells[3].text = "Model Answer / Key"

        for q in questions:
            q_num = q.get('question_number', q.get('slot_index', 1))
            row_cells = table.add_row().cells
            row_cells[0].text = str(q_num)
            row_cells[1].text = str(q.get('type', ''))
            row_cells[2].text = str(q.get('marks', ''))
            row_cells[3].text = str(q.get('answer', ''))

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
