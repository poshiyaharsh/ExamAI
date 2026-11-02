"""
PDF Exporter for Generated Examination Papers.
Uses ReportLab to generate clean, professional examination question papers
and synchronized answer keys.
Supports Unicode TrueType fonts (e.g. Nirmala UI for Indic scripts, Arial for European/Arabic)
while strictly preserving Helvetica for English papers.
"""
import io
import os
import re
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONTS_REGISTERED = False


def _ensure_unicode_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
    nirmala_ttc = os.path.join(win_fonts, 'Nirmala.ttc')
    if os.path.exists(nirmala_ttc):
        try:
            pdfmetrics.registerFont(TTFont('Nirmala', nirmala_ttc, subfontIndex=0))
            pdfmetrics.registerFont(TTFont('Nirmala-Bold', nirmala_ttc, subfontIndex=1))
        except Exception:
            pass

    arial_ttf = os.path.join(win_fonts, 'arial.ttf')
    arialbd_ttf = os.path.join(win_fonts, 'arialbd.ttf')
    if os.path.exists(arial_ttf):
        try:
            pdfmetrics.registerFont(TTFont('Arial', arial_ttf))
            if os.path.exists(arialbd_ttf):
                pdfmetrics.registerFont(TTFont('Arial-Bold', arialbd_ttf))
            else:
                pdfmetrics.registerFont(TTFont('Arial-Bold', arial_ttf))
        except Exception:
            pass

    _FONTS_REGISTERED = True


def _select_font_family(paper_data: Dict[str, Any]) -> tuple:
    """
    Selects font family:
    - Purely English / ASCII: ('Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique')
    - Indic scripts: ('Nirmala', 'Nirmala-Bold', 'Nirmala')
    - Other Unicode: ('Arial', 'Arial-Bold', 'Arial')
    """
    lang = paper_data.get('language') or ''
    # Inspect text for non-Latin characters
    all_text = paper_data.get('title', '') + paper_data.get('subject', '')
    for q in paper_data.get('questions', []):
        all_text += q.get('question', '')
        for opt in q.get('options', []):
            all_text += opt

    has_indic = bool(re.search(r'[\u0900-\u0d7f]', all_text))
    has_non_ascii = bool(re.search(r'[^\x00-\x7F]', all_text))

    if not has_non_ascii and (not lang or lang == 'en'):
        return 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'

    _ensure_unicode_fonts()

    if has_indic and 'Nirmala' in pdfmetrics.getRegisteredFontNames():
        bold_name = 'Nirmala-Bold' if 'Nirmala-Bold' in pdfmetrics.getRegisteredFontNames() else 'Nirmala'
        return 'Nirmala', bold_name, 'Nirmala'

    if 'Arial' in pdfmetrics.getRegisteredFontNames():
        bold_name = 'Arial-Bold' if 'Arial-Bold' in pdfmetrics.getRegisteredFontNames() else 'Arial'
        return 'Arial', bold_name, 'Arial'

    return 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'


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
    - language: Optional[str]
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
    font_reg, font_bold, font_italic = _select_font_family(paper_data)

    # Custom styles
    title_style = ParagraphStyle(
        'ExamTitle',
        parent=styles['Heading1'],
        fontName=font_bold,
        fontSize=18,
        leading=22,
        alignment=1,  # Center
        textColor=colors.HexColor('#1E293B')
    )

    meta_style = ParagraphStyle(
        'ExamMeta',
        parent=styles['Normal'],
        fontName=font_reg,
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor('#64748B')
    )

    q_num_style = ParagraphStyle(
        'QuestionNum',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0F172A')
    )

    q_text_style = ParagraphStyle(
        'QuestionText',
        parent=styles['Normal'],
        fontName=font_reg,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E293B')
    )

    opt_style = ParagraphStyle(
        'OptionText',
        parent=styles['Normal'],
        fontName=font_reg,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#334155')
    )

    ans_style = ParagraphStyle(
        'AnswerText',
        parent=styles['Normal'],
        fontName=font_italic,
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
                Paragraph(f"<b>[{marks} M]</b>", ParagraphStyle('Marks', parent=meta_style, fontName=font_bold, alignment=2, textColor=colors.HexColor('#2563EB')))
            ]],
            colWidths=[30, 442, 60]
        )
        q_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        story.append(q_table)

        # Options for MCQ
        if q_type == 'MCQ' and options:
            story.append(Spacer(1, 3))
            opt_labels = ['(A)', '(B)', '(C)', '(D)']
            opt_rows = []
            for i in range(0, min(4, len(options)), 2):
                row = []
                # First col
                lbl1 = opt_labels[i] if i < len(opt_labels) else f"({i+1})"
                txt1 = options[i]
                row.append(Paragraph(f"<b>{lbl1}</b> {txt1}", opt_style))
                # Second col
                if i + 1 < len(options):
                    lbl2 = opt_labels[i+1] if i + 1 < len(opt_labels) else f"({i+2})"
                    txt2 = options[i+1]
                    row.append(Paragraph(f"<b>{lbl2}</b> {txt2}", opt_style))
                else:
                    row.append(Paragraph("", opt_style))
                opt_rows.append(row)

            opt_table = Table(opt_rows, colWidths=[266, 266])
            opt_table.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 30),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 1.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ]))
            story.append(opt_table)

        # Inline Answer Key if requested
        if include_answers and answer:
            story.append(Spacer(1, 3))
            ans_p = Paragraph(f"<b>Answer Key:</b> {answer}", ans_style)
            ans_table = Table([[ans_p]], colWidths=[502])
            ans_table.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 30),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(ans_table)

        story.append(Spacer(1, 10))

    # Separate Answer Key Appendix if requested
    if include_answers:
        story.append(PageBreak())
        app_title = Paragraph("Official Answer Key & Marking Scheme", title_style)
        story.append(app_title)
        story.append(Spacer(1, 12))

        app_rows = [[
            Paragraph("<b>Q#</b>", q_num_style),
            Paragraph("<b>Type</b>", q_num_style),
            Paragraph("<b>Marks</b>", q_num_style),
            Paragraph("<b>Model Answer / Evaluation Criteria</b>", q_num_style),
        ]]

        for q in questions:
            q_num = q.get('question_number', q.get('slot_index', 1))
            q_type = q.get('type', '')
            marks = q.get('marks', '')
            ans_text = q.get('answer', '')

            # Format rubric if available
            rub = q.get('rubric')
            if isinstance(rub, list) and rub and isinstance(rub[0], dict) and rub[0].get('key_points'):
                pts = rub[0]['key_points']
                formatted_pts = "<br/>".join(f"• {p}" for p in pts)
                display_ans = f"{ans_text}<br/><br/><b>Key Points:</b><br/>{formatted_pts}"
            else:
                display_ans = str(ans_text).replace('\n', '<br/>')

            app_rows.append([
                Paragraph(str(q_num), meta_style),
                Paragraph(str(q_type), meta_style),
                Paragraph(str(marks), meta_style),
                Paragraph(display_ans, q_text_style),
            ])

        app_table = Table(app_rows, colWidths=[35, 80, 45, 372])
        app_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(app_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
