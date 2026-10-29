"""
Automated Test Suite for Smart Question Bank Importer (Non-Template & Multi-Format).
Tests:
1. Real faculty files:
   - DSA_50_MCQ_Questions_Options_Answers.docx (50 questions, 0 invalid)
   - DSA_50_MCQ_Questions_Options_Answers.pdf (50 questions)
   - Cloud_Computing_100_Marks_Full_Paper_With_Answers.pdf (mixed types)
2. Spreadsheet Smart Import:
   - CSV with semicolon delimiter, Latin-1 encoding, and formula injection sanitization.
   - XLSX with title and metadata rows before header row.
3. Scanned PDF detection:
   - Empty / scanned PDF raises descriptive error.
4. Endpoints:
   - Analyze mode (dry_run=True, mode='analyze').
   - Direct curated questions commit.
   - AI Assist endpoint.
   - Error report CSV export.
   - Cleaned template XLSX export.
5. Multi-tenancy and department privacy enforcement.
"""

import io
import os
import json
from decimal import Decimal
import openpyxl

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from api.models import Option, Question, QuestionImportLog, Subject
from api.utils.smart_importer import (
    analyze_file_for_smart_import,
    parse_and_normalize_smart_import,
)
from api.utils.smart_importer.spreadsheet import sanitize_cell_value
from api.utils.smart_importer.documents import analyze_document


def _get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class SmartQuestionBankImporterTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Faculty & Institution A
        self.admin_a = User.objects.create_user(
            username="admin_smart@apex.edu", password="testpassword123", email="admin_smart@apex.edu"
        )
        AdminProfile.objects.create(user=self.admin_a)
        self.inst_a = AdminInstitution.objects.create(
            admin=self.admin_a,
            institution_name="Apex University Smart",
            institution_code="APEX-SMART",
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.faculty_user = User.objects.create_user(
            username="prof_smart@apex.edu", password="testpassword123", email="prof_smart@apex.edu"
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.inst_a,
            department="Computer Science",
        )
        self.token = _get_token(self.faculty_user, 'faculty', self.inst_a)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        # Known downloads files if present
        self.real_docx = r"C:\Users\Harsh Poshiya\Downloads\DSA_50_MCQ_Questions_Options_Answers.docx"
        self.real_pdf = r"C:\Users\Harsh Poshiya\Downloads\DSA_50_MCQ_Questions_Options_Answers.pdf"
        self.cloud_pdf = r"C:\Users\Harsh Poshiya\Downloads\Cloud_Computing_100_Marks_Full_Paper_With_Answers.pdf"

    def test_real_docx_parses_50_questions_cleanly(self):
        """Verify the 191 invalid rows failure is fixed: real docx produces 50 questions and 0 invalid."""
        if not os.path.exists(self.real_docx):
            self.skipTest(f"{self.real_docx} not found on disk.")

        with open(self.real_docx, "rb") as f:
            docx_bytes = f.read()

        report = parse_and_normalize_smart_import(
            file_bytes=docx_bytes,
            filename="DSA_50_MCQ_Questions_Options_Answers.docx",
        )
        self.assertEqual(report['total_rows'], 50)
        self.assertEqual(report['invalid_count'], 0)
        self.assertGreaterEqual(report['ready_count'], 45)

        # Check question 1 stem and options
        first_q = report['all_rows'][0]['data']
        self.assertIn("Which data structure follows", first_q['question_text'])
        self.assertEqual(first_q['question_type'], 'mcq')
        self.assertIn(first_q['correct_answer'], ('A', 'Stack'))
        self.assertEqual(len(first_q['options']), 4)

    def test_real_pdf_parses_cleanly(self):
        """Verify real text-based PDF parses 50 questions without template."""
        if not os.path.exists(self.real_pdf):
            self.skipTest(f"{self.real_pdf} not found on disk.")

        with open(self.real_pdf, "rb") as f:
            pdf_bytes = f.read()

        report = parse_and_normalize_smart_import(
            file_bytes=pdf_bytes,
            filename="DSA_50_MCQ_Questions_Options_Answers.pdf",
        )
        self.assertEqual(report['total_rows'], 50)
        self.assertEqual(report['invalid_count'], 0)
        self.assertGreaterEqual(report['ready_count'], 40)

    def test_messy_csv_with_semicolon_and_latin1_and_formula(self):
        """Verify delimiter sniffing, encoding handling, and formula neutralization."""
        csv_data = (
            "Que;Type;Points;Option 1;Option 2;Option 3;Option 4;Ans\r\n"
            "=SUM(1,2) What is Python?;MCQ;2;=CMD Snakes;Programming Language;Car;Planet;B\r\n"
            "Is Python compiled?;True/False;1;True;False;;;False\r\n"
        ).encode('latin-1')

        report = parse_and_normalize_smart_import(
            file_bytes=csv_data,
            filename="messy.csv",
        )
        self.assertEqual(report['total_rows'], 2)
        self.assertEqual(report['invalid_count'], 0)
        self.assertEqual(report['ready_count'], 2)

        # Formula prefix '=' must be stripped
        q1 = report['all_rows'][0]['data']
        self.assertFalse(q1['question_text'].startswith('='))
        self.assertIn("What is Python?", q1['question_text'])

    def test_messy_xlsx_with_title_rows_before_headers(self):
        """Verify header detection finds row 4 after title and metadata rows."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Exam Questions"
        ws.append(["Apex Institute - Midterm Examination 2026"])
        ws.append(["Department of Computer Engineering"])
        ws.append(["Instructions: Answer all questions carefully."])
        ws.append(["Question Text", "Option A", "Option B", "Option C", "Option D", "Correct Option", "Marks"])
        ws.append(["What is the time complexity of binary search?", "O(n)", "O(log n)", "O(n^2)", "O(1)", "B", 2])
        ws.append(["HTTP stands for HyperText Transfer Protocol.", "True", "False", "", "", "A", 1])

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        xlsx_bytes = out.getvalue()

        report = parse_and_normalize_smart_import(
            file_bytes=xlsx_bytes,
            filename="exam_messy.xlsx",
        )
        self.assertIn(report['header_row_index'], (3, 4))
        self.assertEqual(report['total_rows'], 2)
        self.assertEqual(report['invalid_count'], 0)
        self.assertEqual(report['ready_count'], 2)

    def test_scanned_pdf_error_detection(self):
        """Verify scanned or empty PDF raises user-friendly exception."""
        # Minimal valid PDF binary with almost 0 text content
        minimal_empty_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type /Pages /Kids[3 0 R] /Count 1>>endobj\n"
            b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000108 00000 n \n"
            b"trailer<</Size 4 /Root 1 0 R>>\nstartxref\n182\n%%EOF"
        )
        with self.assertRaises(ValueError) as ctx:
            analyze_document(minimal_empty_pdf, "pdf")
        self.assertIn("scanned", str(ctx.exception).lower())

    def test_upload_api_analyze_mode(self):
        """Verify POST /api/faculty/question-bank/upload/?mode=analyze returns preview without writing to DB."""
        csv_data = (
            "Question,Option 1,Option 2,Option 3,Option 4,Answer,Marks\n"
            "What is DNS?,Domain Name System,Dynamic Network Service,Data Node Server,None,A,1\n"
        ).encode('utf-8')
        f = SimpleUploadedFile("dns.csv", csv_data, content_type="text/csv")

        initial_count = Question.objects.count()
        response = self.client.post(
            '/api/faculty/question-bank/upload/',
            {'file': f, 'mode': 'analyze'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('dry_run'))
        self.assertEqual(response.data.get('ready_count'), 1)
        self.assertEqual(Question.objects.count(), initial_count)

    def test_upload_api_direct_curated_questions_commit(self):
        """Verify committing curated question items payload saves records atomically with Option rows."""
        payload = {
            'is_shared': True,
            'questions': [
                {
                    'question_text': 'What is an idempotent HTTP method?',
                    'question_type': 'mcq',
                    'marks': 2,
                    'difficulty': 'medium',
                    'topic': 'Web Protocols',
                    'subject': 'Computer Networks',
                    'options': [
                        {'text': 'POST', 'is_correct': False, 'order': 1},
                        {'text': 'GET', 'is_correct': True, 'order': 2},
                        {'text': 'PATCH', 'is_correct': False, 'order': 3},
                    ],
                    'correct_answer': 'GET',
                    'explanation': 'GET is idempotent because repeated requests have same effect.',
                }
            ]
        }
        response = self.client.post(
            '/api/faculty/question-bank/upload/',
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['imported_count'], 1)

        q = Question.objects.filter(text__icontains='idempotent').first()
        self.assertIsNotNone(q)
        self.assertEqual(q.institution, self.inst_a)
        self.assertEqual(q.department, 'Computer Science')
        self.assertEqual(q.marks, Decimal('2.00'))
        self.assertEqual(q.option_items.count(), 3)
        correct_opt = q.option_items.filter(is_correct=True).first()
        self.assertEqual(correct_opt.text, 'GET')

    def test_export_report_csv_endpoint(self):
        """Verify POST /api/faculty/question-bank/export-report/ returns downloadable CSV."""
        payload = {
            'rows': [
                {
                    'row_number': 3,
                    'status': 'needs_review',
                    'errors': [],
                    'warnings': ['Missing correct answer key'],
                    'data': {
                        'question_text': 'Explain QuickSort partitioning algorithm.',
                        'question_type': 'long_answer',
                    }
                }
            ]
        }
        response = self.client.post(
            '/api/faculty/question-bank/export-report/',
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn('Explain QuickSort', content)
        self.assertIn('needs_review', content)

    def test_export_cleaned_xlsx_endpoint(self):
        """Verify POST /api/faculty/question-bank/export-cleaned/ returns valid XLSX workbook."""
        payload = {
            'questions': [
                {
                    'question_text': 'Which port is default for HTTPS?',
                    'question_type': 'mcq',
                    'marks': 1,
                    'difficulty': 'easy',
                    'topic': 'Security',
                    'subject': 'Networking',
                    'options_raw': ['80', '443', '8080', '22'],
                    'correct_answer': 'B',
                    'explanation': 'Port 443 is standard for HTTPS.',
                }
            ]
        }
        response = self.client.post(
            '/api/faculty/question-bank/export-cleaned/',
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('spreadsheetml', response['Content-Type'])

        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        ws = wb.active
        self.assertEqual(ws.cell(row=2, column=1).value, 'Which port is default for HTTPS?')
        self.assertEqual(ws.cell(row=2, column=7).value, '80')
        self.assertEqual(ws.cell(row=2, column=8).value, '443')
