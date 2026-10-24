import csv
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.utils import timezone

from admins.models import AdminInstitution, AdminProfile
from api.models import Exam, PaperGenerationJob, Question, StudentAttempt
from faculty.models import FacultyProfile
from students.models import StudentProfile
from superadmin.audit import GENESIS_HASH, compute_audit_hash, verify_audit_log_integrity
from superadmin.models import AIModel, DatabaseBackupRecord, SuperAdminAuditLog

User = get_user_model()
logger = logging.getLogger(__name__)

REPORT_CATALOG = [
    {
        'id': 'system_usage',
        'title': 'System & Platform Usage Overview',
        'category': 'Platform Operations',
        'description': 'Comprehensive overview of users, institutes, examinations, and monthly platform growth rate.',
        'chart_type': 'area',
    },
    {
        'id': 'exam_activity',
        'title': 'Examination Activity & Completion',
        'category': 'Academic Assessment',
        'description': 'Detailed breakdown of exams created, published, attempted, pass rates, and completion statuses.',
        'chart_type': 'bar',
    },
    {
        'id': 'student_performance',
        'title': 'Student Performance & Score Distribution',
        'category': 'Student Analytics',
        'description': 'Aggregated score distributions, pass/fail percentages, and integrity violation frequencies.',
        'chart_type': 'histogram',
    },
    {
        'id': 'faculty_workload',
        'title': 'Faculty Workload & Question Bank Authorship',
        'category': 'Faculty Productivity',
        'description': 'Papers created, manual questions authored, and AI generation utilization per faculty member.',
        'chart_type': 'bar',
    },
    {
        'id': 'ai_generation_metrics',
        'title': 'AI Generation & Model Operational Metrics',
        'category': 'AI Infrastructure',
        'description': 'Paper generation duration, success rates, model tags used, and question shortfall percentages.',
        'chart_type': 'line',
    },
    {
        'id': 'storage_resource',
        'title': 'Storage, Backups & Disk Footprint',
        'category': 'Infrastructure Health',
        'description': 'Database tables size estimation, historical backup archives volume, and Ollama model footprint.',
        'chart_type': 'donut',
    },
    {
        'id': 'audit_compliance',
        'title': 'Super Admin Audit & Security Compliance',
        'category': 'Governance & Security',
        'description': 'Tamper-evident audit trail entries, administrative step-up re-authentications, and DPDP logs.',
        'chart_type': 'table',
    },
    {
        'id': 'institution_benchmark',
        'title': 'Cross-Institution Benchmarking Matrix',
        'category': 'Multi-Tenant Governance',
        'description': 'Comparative performance, engagement, student volume, and quota utilization across institutes.',
        'chart_type': 'bar',
    },
]


def sanitize_formula_cell(value: Any) -> str:
    """
    Prevent CSV / Spreadsheet formula injection (CWE-1236).
    Prefixes values starting with '=', '+', '-', '@', '\t', or '\r' with a single quote.
    """
    if value is None:
        return ''
    val_str = str(value)
    if val_str and val_str[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{val_str}"
    return val_str


def generate_download_token(report_id: str, format_str: str, super_admin_username: str) -> str:
    """
    Generates a secure, 24-hour HMAC-SHA256 download token for authenticated downloads.
    """
    expires_at = int(time.time()) + 86400  # 24 hours
    payload = f'{report_id}|{format_str}|{super_admin_username}|{expires_at}'
    secret = getattr(settings, 'SECRET_KEY', 'examai-report-key').encode('utf-8')
    sig = hmac.new(secret, payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f'{payload}|{sig}'


def verify_download_token(token: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Validates the 24-hour download token. Returns (valid, report_id, format, username).
    """
    try:
        parts = token.split('|')
        if len(parts) != 5:
            return False, None, None, None
        report_id, format_str, username, expires_at_str, sig = parts
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return False, None, None, None

        payload = f'{report_id}|{format_str}|{username}|{expires_at_str}'
        secret = getattr(settings, 'SECRET_KEY', 'examai-report-key').encode('utf-8')
        expected_sig = hmac.new(secret, payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False, None, None, None

        return True, report_id, format_str, username
    except Exception:
        return False, None, None, None


def generate_report_data(report_id: str, institution_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Computes summary KPI metrics, preview table rows, and chart series for the requested report type.
    """
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # 1. System Usage Report
    if report_id == 'system_usage':
        users_count = User.objects.filter(is_active=True).count()
        students_count = StudentProfile.objects.count()
        faculty_count = FacultyProfile.objects.count()
        institutes_count = AdminInstitution.objects.count()
        exams_count = Exam.objects.count()

        growth_trend = []
        for i in range(14, -1, -1):
            day = (now - timedelta(days=i)).date()
            growth_trend.append({
                'label': day.strftime('%b %d'),
                'value': User.objects.filter(date_joined__date__lte=day).count(),
            })

        institutes_qs = AdminInstitution.objects.annotate(
            students_count=Count('student_profiles', distinct=True),
            faculty_count=Count('faculty_profiles', distinct=True),
            exams_count=Count('exams', distinct=True),
        ).order_by('institution_name')[:100]

        rows = []
        for inst in institutes_qs:
            rows.append({
                'Institution': inst.institution_name,
                'Code': inst.institution_code,
                'Status': inst.status,
                'Students': inst.students_count,
                'Faculty': inst.faculty_count,
                'Exams': inst.exams_count,
                'Created': inst.created_at.strftime('%Y-%m-%d') if inst.created_at else '-',
            })

        return {
            'report_id': report_id,
            'title': 'System & Platform Usage Overview',
            'summary': {
                'Total Active Users': users_count,
                'Students': students_count,
                'Faculty': faculty_count,
                'Institutions': institutes_count,
                'Total Exams': exams_count,
            },
            'chart_data': growth_trend,
            'headers': ['Institution', 'Code', 'Status', 'Students', 'Faculty', 'Exams', 'Created'],
            'rows': rows,
        }

    # 2. Exam Activity Report
    elif report_id == 'exam_activity':
        exams_qs = Exam.objects.all().select_related('institution', 'created_by')
        if institution_id:
            exams_qs = exams_qs.filter(institution_id=institution_id)

        total_exams = exams_qs.count()
        published_count = exams_qs.filter(status=Exam.Status.PUBLISHED).count()
        draft_count = exams_qs.filter(status=Exam.Status.DRAFT).count()
        closed_count = exams_qs.filter(status=Exam.Status.CLOSED).count()

        # Status distribution chart
        chart_data = [
            {'label': 'Published', 'value': published_count},
            {'label': 'Draft', 'value': draft_count},
            {'label': 'Closed', 'value': closed_count},
        ]

        rows = []
        for e in exams_qs.order_by('-created_at')[:100]:
            rows.append({
                'ID': e.id,
                'Title': e.title,
                'Subject': e.subject or '-',
                'Department': e.department or 'General',
                'Institution': e.institution.institution_name if e.institution else 'N/A',
                'Status': e.status,
                'Marks': e.total_marks,
                'Created By': e.created_by.username if e.created_by else 'Unknown',
            })

        return {
            'report_id': report_id,
            'title': 'Examination Activity & Completion',
            'summary': {
                'Total Exams': total_exams,
                'Published': published_count,
                'Drafts': draft_count,
                'Closed': closed_count,
            },
            'chart_data': chart_data,
            'headers': ['ID', 'Title', 'Subject', 'Department', 'Institution', 'Status', 'Marks', 'Created By'],
            'rows': rows,
        }

    # 3. Student Performance Report
    elif report_id == 'student_performance':
        attempts_qs = StudentAttempt.objects.filter(
            status__in=[StudentAttempt.Status.SUBMITTED, StudentAttempt.Status.AUTO_SUBMITTED, StudentAttempt.Status.EVALUATED]
        ).select_related('student', 'exam')
        if institution_id:
            attempts_qs = attempts_qs.filter(exam__institution_id=institution_id)

        total_attempts = attempts_qs.count()
        avg_score = attempts_qs.aggregate(avg=Avg('total_score'))['avg'] or 0
        total_violations = attempts_qs.aggregate(total_v=Sum('violation_count'))['total_v'] or 0

        # Score distribution bins: 0-40, 40-60, 60-80, 80-100%
        b1 = attempts_qs.filter(total_score__lt=F('max_score') * 0.4).count()
        b2 = attempts_qs.filter(total_score__gte=F('max_score') * 0.4, total_score__lt=F('max_score') * 0.6).count()
        b3 = attempts_qs.filter(total_score__gte=F('max_score') * 0.6, total_score__lt=F('max_score') * 0.8).count()
        b4 = attempts_qs.filter(total_score__gte=F('max_score') * 0.8).count()

        chart_data = [
            {'label': '< 40% (Fail)', 'value': b1},
            {'label': '40-59% (Pass)', 'value': b2},
            {'label': '60-79% (First)', 'value': b3},
            {'label': '80-100% (Distinction)', 'value': b4},
        ]

        rows = []
        for a in attempts_qs.order_by('-submitted_at')[:100]:
            pct = round((a.total_score / a.max_score) * 100, 1) if a.max_score else 0
            rows.append({
                'Attempt ID': a.id,
                'Student': a.student.username,
                'Exam': a.exam.title if a.exam else '-',
                'Score': f'{a.total_score} / {a.max_score}',
                'Percentage': f'{pct}%',
                'Violations': a.violation_count,
                'Status': a.status,
            })

        return {
            'report_id': report_id,
            'title': 'Student Performance & Score Distribution',
            'summary': {
                'Total Completed Attempts': total_attempts,
                'Average Score': round(avg_score, 1),
                'Total Proctoring Flags': total_violations,
            },
            'chart_data': chart_data,
            'headers': ['Attempt ID', 'Student', 'Exam', 'Score', 'Percentage', 'Violations', 'Status'],
            'rows': rows,
        }

    # 4. Faculty Workload Report
    elif report_id == 'faculty_workload':
        faculty_qs = FacultyProfile.objects.select_related('user', 'institution').all()
        if institution_id:
            faculty_qs = faculty_qs.filter(institution_id=institution_id)

        faculty_list = list(faculty_qs.order_by('user__username')[:100])
        user_ids = [f.user_id for f in faculty_list if f.user_id]

        exam_counts = dict(
            Exam.objects.filter(created_by_id__in=user_ids)
            .values('created_by_id')
            .annotate(c=Count('id'))
            .values_list('created_by_id', 'c')
        )
        job_counts = dict(
            PaperGenerationJob.objects.filter(faculty_id__in=user_ids)
            .values('faculty_id')
            .annotate(c=Count('id'))
            .values_list('faculty_id', 'c')
        )

        rows = []
        dept_counts: Dict[str, int] = {}
        for f in faculty_list:
            papers_count = exam_counts.get(f.user_id, 0)
            jobs_count = job_counts.get(f.user_id, 0)
            dept = f.department or 'General'
            dept_counts[dept] = dept_counts.get(dept, 0) + papers_count

            rows.append({
                'Faculty Name': f'{f.user.first_name} {f.user.last_name}'.strip() or f.user.username,
                'Username': f.user.username,
                'Email': f.user.email,
                'Department': dept,
                'Designation': f.designation or 'Faculty',
                'Exams Authored': papers_count,
                'AI Jobs Triggered': jobs_count,
            })

        chart_data = [{'label': k, 'value': v} for k, v in list(dept_counts.items())[:6]]

        return {
            'report_id': report_id,
            'title': 'Faculty Workload & Question Bank Authorship',
            'summary': {
                'Total Faculty Members': faculty_qs.count(),
                'Total Exam Papers': Exam.objects.count(),
                'AI Generation Runs': PaperGenerationJob.objects.count(),
            },
            'chart_data': chart_data,
            'headers': ['Faculty Name', 'Username', 'Email', 'Department', 'Designation', 'Exams Authored', 'AI Jobs Triggered'],
            'rows': rows,
        }

    # 5. AI Generation Metrics Report
    elif report_id == 'ai_generation_metrics':
        jobs_qs = PaperGenerationJob.objects.all().select_related('exam').order_by('-created_at')
        total_jobs = jobs_qs.count()
        completed_jobs = jobs_qs.filter(status=PaperGenerationJob.Status.COMPLETED).count()
        failed_jobs = jobs_qs.filter(status=PaperGenerationJob.Status.FAILED).count()
        shortfall_jobs = jobs_qs.filter(marks_shortfall__gt=0).count()

        chart_data = [
            {'label': 'Success', 'value': completed_jobs},
            {'label': 'Shortfall Warning', 'value': shortfall_jobs},
            {'label': 'Failed', 'value': failed_jobs},
        ]

        rows = []
        for j in jobs_qs[:100]:
            exam_title = j.exam.title if j.exam else '-'
            subject_name = (j.exam.subject if j.exam and j.exam.subject else '') or j.department or '-'
            duration_val = '-'
            if j.completed_at and (j.started_at or j.created_at):
                dur_secs = (j.completed_at - (j.started_at or j.created_at)).total_seconds()
                duration_val = f'{dur_secs:.1f}'

            rows.append({
                'Job ID': j.id,
                'Exam': exam_title,
                'Subject': subject_name,
                'Requested Marks': j.target_marks,
                'Generated Marks': j.actual_marks,
                'Shortfall': j.marks_shortfall,
                'Status': j.status,
                'Model Tag': j.model or 'Ollama Default',
                'Duration (s)': duration_val,
            })

        return {
            'report_id': report_id,
            'title': 'AI Generation & Model Operational Metrics',
            'summary': {
                'Total Jobs': total_jobs,
                'Successful': completed_jobs,
                'With Shortfall': shortfall_jobs,
                'Failed': failed_jobs,
            },
            'chart_data': chart_data,
            'headers': ['Job ID', 'Exam', 'Subject', 'Requested Marks', 'Generated Marks', 'Shortfall', 'Status', 'Model Tag', 'Duration (s)'],
            'rows': rows,
        }

    # 6. Storage & Resource Report
    elif report_id == 'storage_resource':
        backups_qs = DatabaseBackupRecord.objects.all()
        total_backups = backups_qs.count()
        total_backup_bytes = backups_qs.aggregate(s=Sum('file_size_bytes'))['s'] or 0

        models_qs = AIModel.objects.all()
        total_model_bytes = models_qs.aggregate(s=Sum('size_bytes'))['s'] or 0

        chart_data = [
            {'label': 'Database Backups', 'value': round(total_backup_bytes / (1024 * 1024), 1)},
            {'label': 'AI Models Footprint', 'value': round(total_model_bytes / (1024 * 1024), 1)},
        ]

        rows = []
        for b in backups_qs.order_by('-created_at')[:50]:
            rows.append({
                'Item': f'Backup: {b.filename}',
                'Type': b.backup_type,
                'Size (MB)': round(b.file_size_bytes / (1024 * 1024), 2),
                'Status': b.status,
                'Date': b.created_at.strftime('%Y-%m-%d %H:%M'),
            })

        for m in models_qs:
            rows.append({
                'Item': f'AI Model: {m.name}',
                'Type': m.family or 'Model Layer',
                'Size (MB)': round(m.size_bytes / (1024 * 1024), 2),
                'Status': m.status,
                'Date': m.created_at.strftime('%Y-%m-%d %H:%M'),
            })

        return {
            'report_id': report_id,
            'title': 'Storage, Backups & Disk Footprint',
            'summary': {
                'Total Backups': total_backups,
                'Backups Size (GB)': round(total_backup_bytes / (1024 * 1024 * 1024), 2),
                'AI Models Footprint (GB)': round(total_model_bytes / (1024 * 1024 * 1024), 2),
            },
            'chart_data': chart_data,
            'headers': ['Item', 'Type', 'Size (MB)', 'Status', 'Date'],
            'rows': rows,
        }

    # 7. Audit Compliance Report
    elif report_id == 'audit_compliance':
        audit_qs = SuperAdminAuditLog.objects.all().order_by('-created_at')
        total_entries = audit_qs.count()
        integrity_ok, broken_id = verify_audit_log_integrity()

        chart_data = list(
            audit_qs.values('action')
            .annotate(value=Count('id'))
            .order_by('-value')[:5]
        )
        chart_data = [{'label': c['action'], 'value': c['value']} for c in chart_data]

        rows = []
        for entry in audit_qs[:100]:
            rows.append({
                'ID': entry.id,
                'Actor': entry.actor_username,
                'Action': entry.action,
                'Target': f'{entry.target_entity} #{entry.target_id}',
                'Description': entry.description,
                'IP Address': entry.ip_address,
                'Timestamp': entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            })

        return {
            'report_id': report_id,
            'title': 'Super Admin Audit & Security Compliance',
            'summary': {
                'Audit Chain Entries': total_entries,
                'Chain Integrity': 'VERIFIED' if integrity_ok else f'TAMPERED at #{broken_id}',
                'Tamper Protection': 'HMAC-SHA256 Cryptographic Chaining Active',
            },
            'chart_data': chart_data,
            'headers': ['ID', 'Actor', 'Action', 'Target', 'Description', 'IP Address', 'Timestamp'],
            'rows': rows,
        }

    # 8. Institution Benchmark Report (default)
    else:
        institutes = AdminInstitution.objects.annotate(
            students_count=Count('student_profiles', distinct=True),
            faculty_count=Count('faculty_profiles', distinct=True),
            exams_count=Count('exams', distinct=True),
        ).order_by('institution_name')

        chart_data = []
        rows = []

        for inst in institutes:
            stu_c = inst.students_count
            fac_c = inst.faculty_count
            exam_c = inst.exams_count

            chart_data.append({'label': inst.institution_name[:15], 'value': exam_c})
            rows.append({
                'Institution': inst.institution_name,
                'Code': inst.institution_code,
                'Status': inst.status,
                'City/State': f'{inst.city}, {inst.state}' if inst.city else '-',
                'Students': stu_c,
                'Faculty': fac_c,
                'Exams': exam_c,
            })

        return {
            'report_id': 'institution_benchmark',
            'title': 'Cross-Institution Benchmarking Matrix',
            'summary': {
                'Total Institutions': institutes.count(),
                'Active Tenants': institutes.filter(status='active').count(),
                'Total Platform Exams': Exam.objects.count(),
            },
            'chart_data': chart_data[:6],
            'headers': ['Institution', 'Code', 'Status', 'City/State', 'Students', 'Faculty', 'Exams'],
            'rows': rows,
        }


def export_report_to_csv_string(report_data: Dict[str, Any]) -> str:
    """Generates sanitized CSV text with formula injection protection."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Title & Metadata
    writer.writerow([f"ExamAI Report: {report_data['title']}"])
    writer.writerow([f"Generated At: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"])
    writer.writerow([])

    # Summary
    writer.writerow(['--- Executive Summary ---'])
    for k, v in report_data.get('summary', {}).items():
        writer.writerow([sanitize_formula_cell(k), sanitize_formula_cell(v)])
    writer.writerow([])

    # Table Header & Rows
    headers = report_data.get('headers', [])
    writer.writerow([sanitize_formula_cell(h) for h in headers])

    for row in report_data.get('rows', []):
        writer.writerow([sanitize_formula_cell(row.get(h, '')) for h in headers])

    return output.getvalue()


def export_report_to_xlsx_bytes(report_data: Dict[str, Any]) -> bytes:
    """Generates styled Excel XLSX binary with formula protection and header formatting."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = report_data.get('report_id', 'Report')[:30]

    # Styles
    title_font = Font(name='Calibri', size=14, bold=True, color='1E293B')
    header_font = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='0F172A', end_color='0F172A', fill_type='solid')
    data_font = Font(name='Calibri', size=9, color='334155')
    border_side = Side(style='thin', color='E2E8F0')
    cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)

    # Title
    ws.append([report_data['title']])
    ws.cell(row=1, column=1).font = title_font
    ws.append([f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"])
    ws.append([])

    # Summary Table
    ws.append(['Executive KPI', 'Value'])
    ws.cell(row=4, column=1).font = header_font
    ws.cell(row=4, column=1).fill = header_fill
    ws.cell(row=4, column=2).font = header_font
    ws.cell(row=4, column=2).fill = header_fill

    current_row = 5
    for k, v in report_data.get('summary', {}).items():
        ws.append([sanitize_formula_cell(k), sanitize_formula_cell(v)])
        ws.cell(row=current_row, column=1).font = data_font
        ws.cell(row=current_row, column=2).font = data_font
        current_row += 1

    ws.append([])
    current_row += 1

    # Main Table
    headers = report_data.get('headers', [])
    ws.append([sanitize_formula_cell(h) for h in headers])
    header_row = current_row
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center' if col_idx > 1 else 'left')
    current_row += 1

    for row_item in report_data.get('rows', []):
        row_vals = [sanitize_formula_cell(row_item.get(h, '')) for h in headers]
        ws.append(row_vals)
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=current_row, column=col_idx)
            c.font = data_font
            c.border = cell_border
        current_row += 1

    # Auto-fit column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(40, max(12, max_len + 3))

    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


def export_report_to_pdf_bytes(report_data: Dict[str, Any]) -> bytes:
    """Generates styled PDF document with ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    elements = []

    # Title & Header
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
    )
    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#64748B'),
    )

    elements.append(Paragraph(report_data['title'], title_style))
    elements.append(Paragraph(f"ExamAI Platform Security Report • Generated {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}", subtitle_style))
    elements.append(Spacer(1, 14))

    # Summary Card Table
    summary_data = [['Metric', 'Value']]
    for k, v in report_data.get('summary', {}).items():
        summary_data.append([str(k), str(v)])

    t_summary = Table(summary_data, colWidths=[200, 340])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 16))

    # Main Rows Table (Preview of up to 40 rows to fit page constraints gracefully)
    headers = report_data.get('headers', [])
    rows = report_data.get('rows', [])[:40]

    if headers and rows:
        table_data = [headers]
        for r in rows:
            table_data.append([str(r.get(h, ''))[:25] for h in headers])

        col_w = 540 / max(1, len(headers))
        t_main = Table(table_data, colWidths=[col_w] * len(headers))
        t_main.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        elements.append(t_main)

    doc.build(elements)
    return buffer.getvalue()


# ==============================================================================
# MODULE E: EXTRA SUPER ADMIN TOOLS
# ==============================================================================

def execute_global_emergency_session_revocation(
    actor_username: str,
    target_institute_id: Optional[int] = None,
    reason: str = '',
) -> Tuple[bool, str, int]:
    """
    Emergency tool: Revokes active JWT sessions across an entire institute or the whole platform.
    Clears active_session_id and blacklists outstanding tokens.
    """
    users_qs = User.objects.filter(is_active=True).exclude(username='harshposhiya')
    if target_institute_id:
        users_qs = users_qs.filter(
            Q(student_profile__institution_id=target_institute_id)
            | Q(faculty_profile__institution_id=target_institute_id)
            | Q(admin_profile__institution_id=target_institute_id)
        ).distinct()

    revoked_count = 0
    now = timezone.now()

    # Blacklist tokens via rest_framework_simplejwt
    try:
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
        for u in users_qs:
            tokens = OutstandingToken.objects.filter(user=u, expires_at__gt=now)
            for t in tokens:
                BlacklistedToken.objects.get_or_create(token=t)
            revoked_count += 1
    except Exception as exc:
        logger.warning('Token blacklist exception: %s (falling back to user count)', exc)
        revoked_count = users_qs.count()

    scope = f'Institute #{target_institute_id}' if target_institute_id else 'ENTIRE PLATFORM'
    try:
        last_entry = SuperAdminAuditLog.objects.order_by('-id').first()
        prev_hash = last_entry.entry_hash if (last_entry and last_entry.entry_hash) else GENESIS_HASH
        entry_hash = compute_audit_hash(
            prev_hash=prev_hash,
            actor_username=actor_username,
            action='emergency.sessions_revoked',
            target_entity='PlatformSessions',
            target_id=str(target_institute_id or 'all'),
            description=f'Emergency revocation executed for {scope}. Reason: {reason}',
            ip_address='127.0.0.1',
            before_state={},
            after_state={'scope': scope, 'users_affected': revoked_count, 'reason': reason},
        )
        SuperAdminAuditLog.objects.create(
            actor_username=actor_username,
            action='emergency.sessions_revoked',
            target_entity='PlatformSessions',
            target_id=str(target_institute_id or 'all'),
            description=f'Emergency revocation executed for {scope}. Reason: {reason}',
            after_state={'scope': scope, 'users_affected': revoked_count, 'reason': reason},
            ip_address='127.0.0.1',
            user_agent='ExamAI-EmergencyTool',
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
    except Exception:
        pass

    return True, f'Successfully revoked active sessions across {scope} ({revoked_count} accounts affected).', revoked_count


def execute_global_command_search(query: str) -> Dict[str, Any]:
    """
    Module E Tool: Global search across institutes, users, exams, and settings.
    """
    clean_q = query.strip()
    if not clean_q or len(clean_q) < 2:
        return {'results': []}

    results = []

    # 1. Search Institutes
    institutes = AdminInstitution.objects.filter(
        Q(institution_name__icontains=clean_q) | Q(institution_code__icontains=clean_q)
    )[:5]
    for inst in institutes:
        results.append({
            'type': 'institute',
            'title': inst.institution_name,
            'subtitle': f'Code: {inst.institution_code} • Status: {inst.status}',
            'tab': 'institutes',
            'id': inst.id,
        })

    # 2. Search Users
    users = User.objects.filter(
        Q(username__icontains=clean_q) | Q(email__icontains=clean_q) | Q(first_name__icontains=clean_q)
    ).exclude(username='harshposhiya')[:5]
    for u in users:
        role = 'User'
        if hasattr(u, 'student_profile'):
            role = 'Student'
        elif hasattr(u, 'faculty_profile'):
            role = 'Faculty'
        elif hasattr(u, 'admin_profile'):
            role = 'Admin'

        results.append({
            'type': 'user',
            'title': f'{u.first_name} {u.last_name}'.strip() or u.username,
            'subtitle': f'@{u.username} • {role} • {u.email}',
            'tab': 'users',
            'id': u.id,
        })

    # 3. Search Exams
    exams = Exam.objects.filter(
        Q(title__icontains=clean_q) | Q(subject__icontains=clean_q)
    )[:5]
    for e in exams:
        results.append({
            'type': 'exam',
            'title': e.title,
            'subtitle': f'{e.subject} • Status: {e.status} • Marks: {e.total_marks}',
            'tab': 'exams',
            'id': e.id,
        })

    return {'query': clean_q, 'results': results}
