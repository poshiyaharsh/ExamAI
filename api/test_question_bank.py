"""Automated test suite for Question Bank feature covering validation, isolation, permissions, import, and caching."""

import io
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from api.models import (
    Exam,
    Option,
    Question,
    QuestionImportLog,
    StudentAnswer,
    StudentAttempt,
    Subject,
    Topic,
)
from api.tenant import get_tenant_cache_version
from faculty.models import FacultyProfile
from students.models import StudentProfile


def _create_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class QuestionBankBaseTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Institute A
        self.admin_user_a = User.objects.create_user(
            username='admin_a@gls.edu', email='admin_a@gls.edu', password='Password123!',
            first_name='Admin', last_name='A'
        )
        AdminProfile.objects.create(user=self.admin_user_a)
        self.inst_a = AdminInstitution.objects.create(
            admin=self.admin_user_a,
            institution_name='GLS University',
            institution_code='INST-A',
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.fac_user_a = User.objects.create_user(
            username='faculty_a@gls.edu', email='faculty_a@gls.edu', password='Password123!',
            first_name='Faculty', last_name='A'
        )
        self.fac_profile_a = FacultyProfile.objects.create(
            user=self.fac_user_a,
            institution=self.inst_a,
            department='Computer Science',
            employee_id='FAC-A-01',
        )

        self.stu_user_a = User.objects.create_user(
            username='student_a@gls.edu', email='student_a@gls.edu', password='Password123!',
            first_name='Student', last_name='A'
        )
        self.stu_profile_a = StudentProfile.objects.create(
            user=self.stu_user_a,
            institution=self.inst_a,
            department='Computer Science',
            student_id='STU-A-01',
        )

        self.token_admin_a = _create_token(self.admin_user_a, 'admin', self.inst_a)
        self.token_fac_a = _create_token(self.fac_user_a, 'faculty', self.inst_a)
        self.token_stu_a = _create_token(self.stu_user_a, 'student', self.inst_a)

        # Institute B
        self.admin_user_b = User.objects.create_user(
            username='admin_b@atmiya.edu', email='admin_b@atmiya.edu', password='Password123!',
            first_name='Admin', last_name='B'
        )
        AdminProfile.objects.create(user=self.admin_user_b)
        self.inst_b = AdminInstitution.objects.create(
            admin=self.admin_user_b,
            institution_name='Atmiya University',
            institution_code='INST-B',
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.token_admin_b = _create_token(self.admin_user_b, 'admin', self.inst_b)

        # Subjects and Topics
        self.sub_a = Subject.objects.create(
            institution=self.inst_a,
            department='Computer Science',
            name='Algorithms',
            code='CS101',
            created_by=self.admin_user_a,
        )
        self.top_a = Topic.objects.create(
            institution=self.inst_a,
            subject=self.sub_a,
            name='Sorting',
            created_by=self.admin_user_a,
        )

        self.sub_b = Subject.objects.create(
            institution=self.inst_b,
            department='Computer Science',
            name='Database Systems',
            code='CS201',
            created_by=self.admin_user_b,
        )


class QuestionBankValidationTests(QuestionBankBaseTestCase):
    def test_empty_or_too_short_text_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        payload = {
            'text': 'Short',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'MEDIUM',
            'marks': 2.0,
            'options': [{'text': 'Opt 1', 'is_correct': True}, {'text': 'Opt 2', 'is_correct': False}],
        }
        res = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('text', res.data)

    def test_placeholder_text_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        payload = {
            'text': 'Lorem ipsum dolor sit amet',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'MEDIUM',
            'marks': 2.0,
            'options': [{'text': 'Opt 1', 'is_correct': True}, {'text': 'Opt 2', 'is_correct': False}],
        }
        res = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('text', res.data)

    def test_mcq_single_validation_exact_one_correct(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        # Zero correct options
        payload_no_correct = {
            'text': 'What is the average time complexity of quicksort?',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'MEDIUM',
            'marks': 2.0,
            'options': [{'text': 'O(n)', 'is_correct': False}, {'text': 'O(n log n)', 'is_correct': False}],
        }
        res = self.client.post('/api/admin/question-bank/questions/', payload_no_correct, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('options', res.data)

        # Two correct options for MCQ_SINGLE
        payload_two_correct = {
            'text': 'What is the average time complexity of quicksort?',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'MEDIUM',
            'marks': 2.0,
            'options': [{'text': 'O(n)', 'is_correct': True}, {'text': 'O(n log n)', 'is_correct': True}],
        }
        res2 = self.client.post('/api/admin/question-bank/questions/', payload_two_correct, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_options_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        payload = {
            'text': 'Which data structure uses LIFO ordering?',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'EASY',
            'marks': 1.0,
            'options': [{'text': 'Stack', 'is_correct': True}, {'text': 'Stack', 'is_correct': False}],
        }
        res = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_marks_and_negative_marks_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        payload = {
            'text': 'Which data structure uses FIFO ordering?',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'EASY',
            'marks': 2.0,
            'negative_marks': 3.0,  # Negative marks > marks!
            'options': [{'text': 'Queue', 'is_correct': True}, {'text': 'Stack', 'is_correct': False}],
        }
        res = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('negative_marks', res.data)

    def test_short_answer_requires_model_answer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        payload = {
            'text': 'Explain the difference between primary and foreign keys in databases.',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'SHORT_ANSWER',
            'difficulty': 'MEDIUM',
            'marks': 5.0,
            'model_answer': '',
        }
        res = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('model_answer', res.data)


class QuestionBankDuplicateTests(QuestionBankBaseTestCase):
    def test_duplicate_prevention_at_serializer_and_db_level(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        payload = {
            'text': 'What is the time complexity of binary search in a sorted array?',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'EASY',
            'marks': 1.0,
            'options': [{'text': 'O(log n)', 'is_correct': True}, {'text': 'O(n)', 'is_correct': False}],
        }
        res1 = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Attempt to create exact duplicate
        res2 = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('text', res2.data)

        # Verify DB level constraint fails if bypassing serializer
        from api.validators.question_bank import compute_text_hash
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Question.objects.create(
                    institution=self.inst_a,
                    subject=self.sub_a,
                    department='Computer Science',
                    text='What is the time complexity of binary search in a sorted array?',
                    text_hash=compute_text_hash('What is the time complexity of binary search in a sorted array?'),
                    marks=Decimal('1.0'),
                    is_deleted=False,
                )


class MultiInstituteIsolationTests(QuestionBankBaseTestCase):
    def setUp(self):
        super().setUp()
        self.q_a = Question.objects.create(
            institution=self.inst_a,
            department='Computer Science',
            subject=self.sub_a,
            text='What is a balanced binary search tree?',
            text_hash='hash_a',
            marks=Decimal('2.0'),
            status='ACTIVE',
        )
        self.q_b = Question.objects.create(
            institution=self.inst_b,
            department='Computer Science',
            subject=self.sub_b,
            text='Explain B-Tree indexing in modern databases.',
            text_hash='hash_b',
            marks=Decimal('3.0'),
            status='ACTIVE',
        )

    def test_admin_cannot_list_other_institute_questions(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        res = self.client.get('/api/admin/question-bank/questions/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = [item['id'] for item in res.data['results']]
        self.assertIn(self.q_a.id, returned_ids)
        self.assertNotIn(self.q_b.id, returned_ids)

    def test_admin_cannot_access_or_modify_other_institute_question(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        # Direct GET -> 404
        res_get = self.client.get(f'/api/admin/question-bank/questions/{self.q_b.id}/')
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        # Direct PATCH -> 404
        res_patch = self.client.patch(f'/api/admin/question-bank/questions/{self.q_b.id}/', {'text': 'Hacked Question Text'})
        self.assertEqual(res_patch.status_code, status.HTTP_404_NOT_FOUND)

        # Direct DELETE -> 404
        res_del = self.client.delete(f'/api/admin/question-bank/questions/{self.q_b.id}/')
        self.assertEqual(res_del.status_code, status.HTTP_404_NOT_FOUND)

        # Direct Duplicate -> 404
        res_dup = self.client.post(f'/api/admin/question-bank/questions/{self.q_b.id}/duplicate/')
        self.assertEqual(res_dup.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_institute_subject_reference_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        payload = {
            'text': 'Can Institute A create a question with Institute B subject?',
            'department': 'Computer Science',
            'subject': self.sub_b.id,  # Belongs to Institute B!
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'EASY',
            'marks': 1.0,
            'options': [{'text': 'No', 'is_correct': True}, {'text': 'Yes', 'is_correct': False}],
        }
        res = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('subject', res.data)


class PermissionsAndAnswerLeakTests(QuestionBankBaseTestCase):
    def test_anonymous_and_student_permissions(self):
        # Anonymous
        res_anon = self.client.get('/api/admin/question-bank/questions/')
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # Student gets 403 on admin question bank
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')
        res_stu = self.client.get('/api/admin/question-bank/questions/')
        self.assertEqual(res_stu.status_code, status.HTTP_403_FORBIDDEN)

        res_stu_post = self.client.post('/api/admin/question-bank/questions/', {})
        self.assertEqual(res_stu_post.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_never_sees_answer_keys_during_exam(self):
        exam = Exam.objects.create(
            institution=self.inst_a,
            title='Midterm Algorithm Exam',
            department='Computer Science',
            duration_minutes=60,
            total_marks=10,
            created_by=self.fac_user_a,
            status=Exam.Status.PUBLISHED,
        )
        q = Question.objects.create(
            exam=exam,
            institution=self.inst_a,
            department='Computer Science',
            order=1,
            question_type='mcq',
            difficulty='easy',
            text='What is the complexity of inserting into a hash table on average?',
            options=['O(1)', 'O(n)'],
            correct_answer='O(1)',
            marks=5,
        )
        attempt = StudentAttempt.objects.create(
            exam=exam,
            institution=self.inst_a,
            student=self.stu_user_a,
            status=StudentAttempt.Status.IN_PROGRESS,
        )
        StudentAnswer.objects.create(
            attempt=attempt,
            institution=self.inst_a,
            question=q,
            answer_text='O(1)',
            is_correct=True,
            score_awarded=5.0,
            ai_feedback='Correct answer!',
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')
        res = self.client.get(f'/api/student/attempts/{attempt.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ans_data = res.data['answers'][0]
        # In-progress exam attempt MUST NEVER reveal correct_answer or is_correct
        self.assertIsNone(ans_data['correct_answer'])
        self.assertIsNone(ans_data['is_correct'])
        self.assertIsNone(ans_data['score_awarded'])
        self.assertEqual(ans_data['ai_feedback'], '')


class ExamQuestionImmutabilityTests(QuestionBankBaseTestCase):
    def test_editing_locked_question_is_blocked(self):
        exam = Exam.objects.create(
            institution=self.inst_a,
            title='Ongoing Published Exam',
            department='Computer Science',
            duration_minutes=45,
            total_marks=5,
            created_by=self.fac_user_a,
            status=Exam.Status.PUBLISHED,
        )
        q = Question.objects.create(
            exam=exam,
            institution=self.inst_a,
            subject=self.sub_a,
            department='Computer Science',
            order=1,
            text='Important exam question text for ongoing test.',
            marks=Decimal('5.0'),
            status='ACTIVE',
        )
        attempt = StudentAttempt.objects.create(
            exam=exam,
            institution=self.inst_a,
            student=self.stu_user_a,
            status=StudentAttempt.Status.SUBMITTED,
        )
        StudentAnswer.objects.create(
            attempt=attempt,
            institution=self.inst_a,
            question=q,
            answer_text='My Answer',
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        # Direct deletion blocked
        res_del = self.client.delete(f'/api/admin/question-bank/questions/{q.id}/')
        self.assertEqual(res_del.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot delete', res_del.data['detail'])

        # Modification blocked
        res_patch = self.client.patch(
            f'/api/admin/question-bank/questions/{q.id}/',
            {'text': 'Altered question text after exam is taken'},
            format='json',
        )
        self.assertEqual(res_patch.status_code, status.HTTP_400_BAD_REQUEST)


class BulkImportTests(QuestionBankBaseTestCase):
    def test_dry_run_saves_nothing_and_reports_correctly(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        csv_content = (
            "department,subject,topic,question_type,difficulty,marks,negative_marks,question_text,option_1,option_2,correct_options\n"
            "Computer Science,Algorithms,Sorting,MCQ_SINGLE,EASY,2.0,0.0,What is worst case complexity of quicksort?,O(n^2),O(n log n),1\n"
            "Computer Science,Algorithms,Sorting,MCQ_SINGLE,EASY,2.0,0.0,Short,O(n),O(1),1\n"  # Invalid row (too short)
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'import_test.csv'

        # Dry run = True
        res_dry = self.client.post('/api/admin/question-bank/questions/bulk-import/?dry_run=true', {'file': csv_file})
        self.assertEqual(res_dry.status_code, status.HTTP_200_OK)
        self.assertTrue(res_dry.data['dry_run'])
        self.assertEqual(res_dry.data['valid_count'], 1)
        self.assertEqual(res_dry.data['failed_count'], 1)

        # Verify nothing was saved in DB
        self.assertEqual(Question.objects.filter(text__icontains='quicksort').count(), 0)

    def test_all_or_nothing_rollback_works(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        csv_content = (
            "department,subject,topic,question_type,difficulty,marks,negative_marks,question_text,option_1,option_2,correct_options\n"
            "Computer Science,Algorithms,Sorting,MCQ_SINGLE,EASY,2.0,0.0,What is worst case complexity of bubblesort?,O(n^2),O(n log n),1\n"
            "Computer Science,Algorithms,Sorting,MCQ_SINGLE,EASY,2.0,0.0,Invalid,O(n),O(1),1\n"  # Invalid
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'import_fail.csv'

        res = self.client.post('/api/admin/question-bank/questions/bulk-import/', {'file': csv_file, 'mode': 'all_or_nothing'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # In all-or-nothing mode, 0 records should be created
        self.assertEqual(Question.objects.filter(text__icontains='bubblesort').count(), 0)

    def test_successful_import_creates_questions_and_options(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        csv_content = (
            "department,subject,topic,question_type,difficulty,marks,negative_marks,question_text,option_1,option_2,correct_options\n"
            "Computer Science,Algorithms,Sorting,MCQ_SINGLE,EASY,2.0,0.0,Which sorting algorithm has guaranteed O(n log n) worst case?,Merge Sort,Quick Sort,1\n"
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'import_success.csv'

        res = self.client.post('/api/admin/question-bank/questions/bulk-import/', {'file': csv_file})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['imported_count'], 1)

        imported_q = Question.objects.get(text__icontains='guaranteed O(n log n)')
        self.assertEqual(imported_q.institution_id, self.inst_a.id)
        self.assertEqual(imported_q.option_items.count(), 2)
        correct_opt = imported_q.option_items.get(is_correct=True)
        self.assertEqual(correct_opt.text, 'Merge Sort')


class CacheInvalidationTests(QuestionBankBaseTestCase):
    def test_cache_version_bumps_on_mutation(self):
        v1 = get_tenant_cache_version(self.inst_a.id)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        payload = {
            'text': 'What data structure is used to implement BFS in graphs?',
            'department': 'Computer Science',
            'subject': self.sub_a.id,
            'question_type': 'MCQ_SINGLE',
            'difficulty': 'MEDIUM',
            'marks': 2.0,
            'options': [{'text': 'Queue', 'is_correct': True}, {'text': 'Stack', 'is_correct': False}],
        }
        res = self.client.post('/api/admin/question-bank/questions/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        v2 = get_tenant_cache_version(self.inst_a.id)
        self.assertGreater(v2, v1)
