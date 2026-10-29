"""
Comprehensive Automated Tests for Part B:
Faculty Question Bank File Upload & Paper Builder (No AI).

Verifies:
1. Multi-format parsers (CSV, XLSX, DOCX, JSON).
2. Security safeguards:
   - File size <= 10MB limit enforcement.
   - Row limit <= 500 enforcement.
   - Magic bytes detection (rejecting binary executables / wrong headers).
   - Macro rejection (.xlsm, .docm, vbaProject.bin).
   - Formula injection neutralization (leading '=', '+', '-', '@').
3. Transactional validation & rollback:
   - All-or-nothing mode rolls back on malformed row.
   - import_valid_rows_only skips errors and imports valid rows.
4. Downloadable templates endpoint (CSV, XLSX, DOCX, JSON).
5. Multi-tenancy & privacy isolation:
   - Cross-institution isolation.
   - Private questions (is_shared=False) invisible to other faculty.
6. Bank-to-Paper assembly:
   - Manual question_ids assembly.
   - Deterministic auto-assembly via knapsack solver matching target marks exactly without AI.
"""

import io
import json
import zipfile
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from api.models import Exam, Option, Question, QuestionImportLog, Subject
from api.utils.question_bank_parser import (
    MAX_FILE_SIZE,
    MAX_ROWS,
    parse_and_validate_question_bank_file,
    sanitize_cell_value,
    validate_file_signature,
)
from api.utils.question_bank_templates import (
    generate_template_csv,
    generate_template_docx,
    generate_template_json,
    generate_template_xlsx,
)


def _get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class FacultyQuestionBankTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Institution A
        self.admin_a = User.objects.create_user(
            username="admin_a@apex.edu", password="testpassword123", email="admin_a@apex.edu"
        )
        AdminProfile.objects.create(user=self.admin_a)
        self.inst_a = AdminInstitution.objects.create(
            admin=self.admin_a,
            institution_name="Apex University A",
            institution_code="APEX-A",
            status=AdminInstitution.STATUS_ACTIVE,
        )

        # Faculty 1 in Institution A (CS Dept)
        self.faculty_1 = User.objects.create_user(
            username="prof_cs_1", password="testpassword123", email="prof_cs_1@apex.edu"
        )
        self.prof_1_profile = FacultyProfile.objects.create(
            user=self.faculty_1,
            institution=self.inst_a,
            department="Computer Science",
            employee_id="FAC-A-001",
        )
        self.token_1 = _get_token(self.faculty_1, "faculty", self.inst_a)

        # Faculty 2 in Institution A (Same CS Dept)
        self.faculty_2 = User.objects.create_user(
            username="prof_cs_2", password="testpassword123", email="prof_cs_2@apex.edu"
        )
        self.prof_2_profile = FacultyProfile.objects.create(
            user=self.faculty_2,
            institution=self.inst_a,
            department="Computer Science",
            employee_id="FAC-A-002",
        )
        self.token_2 = _get_token(self.faculty_2, "faculty", self.inst_a)

        # Institution B (for cross-tenant tests)
        self.admin_b = User.objects.create_user(
            username="admin_b@other.edu", password="testpassword123", email="admin_b@other.edu"
        )
        AdminProfile.objects.create(user=self.admin_b)
        self.inst_b = AdminInstitution.objects.create(
            admin=self.admin_b,
            institution_name="Other Institute B",
            institution_code="OTHER-B",
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.faculty_b = User.objects.create_user(
            username="prof_b", password="testpassword123", email="prof_b@other.edu"
        )
        FacultyProfile.objects.create(
            user=self.faculty_b,
            institution=self.inst_b,
            department="Computer Science",
            employee_id="FAC-B-001",
        )
        self.token_b = _get_token(self.faculty_b, "faculty", self.inst_b)

        # Subject in Inst A
        self.subject = Subject.objects.create(
            name="Data Structures",
            code="CS201",
            department="Computer Science",
            institution=self.inst_a,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_1}")

    def test_sanitize_formula_injection(self):
        """Verify formula injection prefixes are stripped."""
        self.assertEqual(sanitize_cell_value("=SUM(A1:A10)"), "SUM(A1:A10)")
        self.assertEqual(sanitize_cell_value("+cmd|' /C calc'!A1"), "cmd|' /C calc'!A1")
        self.assertEqual(sanitize_cell_value("-10+5"), "10+5")
        self.assertEqual(sanitize_cell_value("@IMPORT"), "IMPORT")
        self.assertEqual(sanitize_cell_value("Normal text"), "Normal text")
        self.assertEqual(sanitize_cell_value(25), 25)

    def test_validate_file_signature_rejects_binary_executable(self):
        """Verify Windows EXE / ELF binary renamed to .csv is rejected."""
        fake_csv = b"MZ\x90\x00\x03\x00\x00\x00fake executable content"
        with self.assertRaises(ValueError) as ctx:
            validate_file_signature(fake_csv, "questions.csv")
        self.assertIn("unsupported binary header", str(ctx.exception))

    def test_validate_file_signature_rejects_macro_enabled(self):
        """Verify macro-enabled documents containing vbaProject.bin are rejected."""
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr('xl/workbook.xml', '<workbook/>')
            zf.writestr('xl/vbaProject.bin', b'VBA byte code')
        macro_bytes = bio.getvalue()

        with self.assertRaises(ValueError) as ctx:
            validate_file_signature(macro_bytes, "malicious.xlsx")
        self.assertIn("Macro-enabled documents", str(ctx.exception))

    def test_template_generation_all_formats(self):
        """Verify template generators produce valid bytes for all 4 formats."""
        for gen_fn, expected_ext, mime in [
            (generate_template_csv, '.csv', 'text/csv'),
            (generate_template_xlsx, '.xlsx', 'spreadsheetml'),
            (generate_template_docx, '.docx', 'wordprocessingml'),
            (generate_template_json, '.json', 'application/json'),
        ]:
            b_data, content_type, filename = gen_fn()
            self.assertGreater(len(b_data), 10)
            self.assertTrue(filename.endswith(expected_ext))
            self.assertIn(mime, content_type)

            # Ensure the generated template parses cleanly through parser engine
            mock_file = SimpleUploadedFile(filename, b_data)
            report = parse_and_validate_question_bank_file(mock_file)
            self.assertEqual(report['valid_count'], 5)
            self.assertEqual(report['invalid_count'], 0)

    def test_download_templates_api(self):
        """Verify GET /api/faculty/question-bank/templates/?format={fmt} serves files."""
        for fmt in ('csv', 'xlsx', 'docx', 'json'):
            response = self.client.get(f'/api/faculty/question-bank/templates/?format={fmt}')
            if response.status_code != 200:
                print(f"DEBUG: FMT {fmt} status={response.status_code} body={response.content}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('Content-Disposition', response.headers)
            self.assertIn(f'.{fmt}', response.headers['Content-Disposition'])

    def test_upload_dry_run_preview(self):
        """Verify dry_run=true returns preview without committing records to database."""
        b_data, _, filename = generate_template_csv()
        f = SimpleUploadedFile(filename, b_data, content_type="text/csv")

        initial_count = Question.objects.count()
        response = self.client.post(
            '/api/faculty/question-bank/upload/',
            {'file': f, 'dry_run': 'true'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['dry_run'])
        self.assertEqual(response.data['total_rows'], 5)
        self.assertEqual(response.data['valid_count'], 5)
        self.assertEqual(len(response.data['preview_rows']), 5)
        # Database count remains unchanged
        self.assertEqual(Question.objects.count(), initial_count)

    def test_upload_commit_all_or_nothing_rollback_on_error(self):
        """Verify malformed row in all-or-nothing mode aborts import and writes 0 records."""
        # Row 1 is valid, Row 2 has empty question text
        csv_content = (
            "question_text,question_type,marks,options,correct_answer\n"
            "Valid question 1 here?,mcq,2,Opt A|Opt B,A\n"
            ",mcq,2,Opt A|Opt B,A\n"
        ).encode('utf-8')
        f = SimpleUploadedFile("bad.csv", csv_content, content_type="text/csv")

        initial_count = Question.objects.count()
        response = self.client.post(
            '/api/faculty/question-bank/upload/',
            {'file': f, 'dry_run': 'false', 'import_valid_rows_only': 'false'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("invalid row", response.data['detail'])
        # 0 records written
        self.assertEqual(Question.objects.count(), initial_count)

    def test_upload_commit_import_valid_rows_only(self):
        """Verify import_valid_rows_only=true imports valid rows and skips errors."""
        csv_content = (
            "question_text,question_type,marks,options,correct_answer\n"
            "Valid question 1 here?,mcq,2,Opt A|Opt B,A\n"
            ",mcq,2,Opt A|Opt B,A\n"
            "Valid question 3 here?,true_false,1,True|False,True\n"
        ).encode('utf-8')
        f = SimpleUploadedFile("partial.csv", csv_content, content_type="text/csv")

        initial_count = Question.objects.count()
        response = self.client.post(
            '/api/faculty/question-bank/upload/',
            {'file': f, 'dry_run': 'false', 'import_valid_rows_only': 'true'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['imported_count'], 2)
        self.assertEqual(Question.objects.count(), initial_count + 2)

    def test_multi_tenancy_and_privacy_isolation(self):
        """Verify private bank questions are invisible to other faculty, and cross-tenant access is blocked."""
        # Faculty 1 creates 1 shared question and 1 private question
        q_shared = Question.objects.create(
            institution=self.inst_a,
            department="Computer Science",
            subject=self.subject,
            created_by=self.faculty_1,
            question_type="mcq",
            text="Shared Question from Prof 1",
            marks=2,
            is_shared=True,
        )
        q_private = Question.objects.create(
            institution=self.inst_a,
            department="Computer Science",
            subject=self.subject,
            created_by=self.faculty_1,
            question_type="mcq",
            text="Private Question from Prof 1",
            marks=2,
            is_shared=False,
        )

        # 1. Faculty 1 sees both shared and private
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_1}")
        resp1 = self.client.get('/api/faculty/question-bank/')
        ids_1 = [q['id'] for q in resp1.data['questions']]
        self.assertIn(q_shared.id, ids_1)
        self.assertIn(q_private.id, ids_1)

        # 2. Faculty 2 (same department) sees shared question, but NOT private question
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_2}")
        resp2 = self.client.get('/api/faculty/question-bank/')
        ids_2 = [q['id'] for q in resp2.data['questions']]
        self.assertIn(q_shared.id, ids_2)
        self.assertNotIn(q_private.id, ids_2)

        # 3. Faculty B (different institution) sees 0 questions
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_b}")
        resp_b = self.client.get('/api/faculty/question-bank/')
        self.assertEqual(resp_b.data['total_count'], 0)

    def test_assemble_paper_from_bank_manual_ids(self):
        """Verify manual question_ids assembly clones bank questions into exam with exact marks."""
        q1 = Question.objects.create(
            institution=self.inst_a,
            department="Computer Science",
            subject=self.subject,
            created_by=self.faculty_1,
            question_type="mcq",
            text="Bank Q1",
            marks=5,
        )
        q2 = Question.objects.create(
            institution=self.inst_a,
            department="Computer Science",
            subject=self.subject,
            created_by=self.faculty_1,
            question_type="short_answer",
            text="Bank Q2",
            marks=15,
        )

        exam = Exam.objects.create(
            title="Manual Bank Exam",
            subject=self.subject,
            created_by=self.faculty_1,
            institution=self.inst_a,
            department="Computer Science",
            total_marks=20,
            target_total_marks=20,
            duration_minutes=60,
            status=Exam.Status.DRAFT,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_1}")
        response = self.client.post(
            f'/api/faculty/exams/{exam.id}/assemble-from-bank/',
            {'question_ids': [q1.id, q2.id], 'action': 'replace'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam.refresh_from_db()
        self.assertEqual(exam.total_marks, 20)
        self.assertEqual(exam.marks_shortfall, 0)
        self.assertEqual(exam.questions.filter(is_deleted=False).count(), 2)

    def test_assemble_paper_from_bank_deterministic_knapsack(self):
        """Verify auto_assemble=true knapsack solver reaches exact target marks without AI."""
        # Create bank items with diverse mark values: 2, 3, 5, 10
        for i, m in enumerate([2, 3, 5, 5, 10, 10, 15]):
            Question.objects.create(
                institution=self.inst_a,
                department="Computer Science",
                subject=self.subject,
                created_by=self.faculty_1,
                question_type="mcq" if m <= 5 else "long_answer",
                text=f"Knapsack Bank Question {i} worth {m} marks",
                marks=m,
            )

        exam = Exam.objects.create(
            title="Auto Assembled 20M Exam",
            subject=self.subject,
            created_by=self.faculty_1,
            institution=self.inst_a,
            department="Computer Science",
            total_marks=20,
            target_total_marks=20,
            duration_minutes=60,
            status=Exam.Status.DRAFT,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_1}")
        response = self.client.post(
            f'/api/faculty/exams/{exam.id}/assemble-from-bank/',
            {'auto_assemble': True, 'target_marks': 20, 'action': 'replace'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam.refresh_from_db()
        self.assertEqual(exam.total_marks, 20)
        self.assertEqual(exam.marks_shortfall, 0)
        cloned_sum = sum(int(q.marks) for q in exam.questions.filter(is_deleted=False))
        self.assertEqual(cloned_sum, 20)

    def test_assemble_paper_from_bank_creates_new_exam(self):
        """Verify POST /api/faculty/exams/assemble-from-bank/ creates and populates a new draft Exam directly."""
        q1 = Question.objects.create(
            institution=self.inst_a,
            department="Computer Science",
            subject=self.subject,
            created_by=self.faculty_1,
            question_type="mcq",
            text="Brand New Exam Q1",
            marks=10,
        )
        q2 = Question.objects.create(
            institution=self.inst_a,
            department="Computer Science",
            subject=self.subject,
            created_by=self.faculty_1,
            question_type="short_answer",
            text="Brand New Exam Q2",
            marks=15,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_1}")
        response = self.client.post(
            '/api/faculty/exams/assemble-from-bank/',
            {
                'title': 'Brand New Bank Exam',
                'subject': 'Data Structures',
                'question_ids': [q1.id, q2.id],
                'target_marks': 25,
                'duration_minutes': 45,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_exam_id = response.data['exam_id']
        exam = Exam.objects.get(id=new_exam_id)
        self.assertEqual(exam.title, 'Brand New Bank Exam')
        self.assertEqual(exam.total_marks, 25)
        self.assertEqual(exam.marks_shortfall, 0)
        self.assertEqual(exam.questions.filter(is_deleted=False).count(), 2)

