"""
PDF Exporter for Generated Examination Papers.
Uses ReportLab to generate clean, professional examination question papers
and synchronized answer keys.
"""
import io
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def export_paper_to_pdf(
    paper_data: Dict[str, Any],
    include_answers: bool = False
) -> bytes:
    """
    Renders paper_data into a PDF binary stream.
    paper_data expects:
    - title: str
    - subject: str
    - duration: int (minutes)
    - total_marks: int
    - questions: List[Dict]
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'ExamTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1,  # Center
        textColor=colors.HexColor('#1E293B')
    )

    meta_style = ParagraphStyle(
        'ExamMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor('#64748B')
    )

    q_num_style = ParagraphStyle(
        'QuestionNum',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0F172A')
    )

    q_text_style = ParagraphStyle(
        'QuestionText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E293B')
    )

    opt_style = ParagraphStyle(
        'OptionText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#334155')
    )

    ans_style = ParagraphStyle(
        'AnswerText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#166534')
    )

    story = []

    # Header
    title = paper_data.get('title', 'Examination Paper')
    subject = paper_data.get('subject', 'General Subject')
    duration = paper_data.get('duration', 60)
    total_marks = paper_data.get('total_marks', 100)

    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Subject: {subject} &nbsp;|&nbsp; Duration: {duration} mins &nbsp;|&nbsp; Total Marks: {total_marks}", meta_style))
    story.append(Spacer(1, 15))

    # Divider Table
    divider = Table([['']], colWidths=[532], rowHeights=[1.5])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 15))

    # Questions
    questions = paper_data.get('questions', [])
    for q in questions:
        q_num = q.get('question_number', q.get('slot_index', 1))
        q_type = q.get('type', 'MCQ')
        marks = q.get('marks', 1)
        q_text = q.get('question', '')
        options = q.get('options', [])
        answer = q.get('answer', '')

        # Question header table
        q_table = Table(
            [[
                Paragraph(f"<b>Q{q_num}.</b>", q_num_style),
                Paragraph(f"{q_text}", q_text_style),
                Paragraph(f"<b>[{marks} M]</b>", ParagraphStyle('Marks', parent=meta_style, alignment=2, textColor=colors.HexColor('#2563EB')))
            ]],
            colWidths=[30, 442, 60]
        )
        q_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(q_table)

        # Options for MCQ
        if q_type == 'MCQ' and options:
            opt_labels = ['(A)', '(B)', '(C)', '(D)']
            opt_rows = []
            for i, opt in enumerate(options[:4]):
                lbl = opt_labels[i] if i < len(opt_labels) else f"({i+1})"
                opt_rows.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{lbl} {opt}", opt_style))
                story.append(Spacer(1, 2))
                story.append(opt_rows[-1])

        # Inline Answer key if requested
        if include_answers and answer:
            story.append(Spacer(1, 3))
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Key:</b> {answer}", ans_style))

        story.append(Spacer(1, 10))

    # Separate Answer Key appendix if not inline
    if include_answers and not paper_data.get('inline_answers', False):
        story.append(PageBreak())
        story.append(Paragraph("Answer Key & Marking Scheme", title_style))
        story.append(Spacer(1, 10))

        key_data = [['Q#', 'Type', 'Marks', 'Correct Answer / Rubric']]
        for q in questions:
            q_num = q.get('question_number', q.get('slot_index', 1))
            q_type = q.get('type', 'MCQ')
            marks = q.get('marks', 1)
            ans = q.get('answer', '')
            key_data.append([
                str(q_num),
                q_type,
                str(marks),
                Paragraph(str(ans)[:300], ans_style)
            ])

        key_table = Table(key_data, colWidths=[35, 80, 50, 367])
        key_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(key_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
