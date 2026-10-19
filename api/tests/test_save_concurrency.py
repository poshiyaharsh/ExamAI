import concurrent.futures
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITransactionTestCase, APIClient

from admins.models import AdminInstitution, AdminProfile
from api.models import Exam, Question, StudentAttempt, StudentAnswer
from faculty.models import FacultyProfile
from students.models import StudentProfile


def _create_token(user, role, institution):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['email'] = user.email
    refresh['institution_id'] = institution.id
    refresh['institution_name'] = institution.institution_name
    return str(refresh.access_token)


class SaveAnswerConcurrencyTestSuite(APITransactionTestCase):
    def setUp(self):
        cache.clear()
        # Admin & Institution
        self.admin_user = User.objects.create_user(
            username='admin_gls@gls.edu', email='admin_gls@gls.edu', password='Password123!'
        )
        AdminProfile.objects.create(user=self.admin_user)
        self.inst = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name='GLS University',
            institution_code='INST-2026-GLS',
            status=AdminInstitution.STATUS_ACTIVE,
        )

        # Faculty
        self.fac_user = User.objects.create_user(
            username='fac_gls@gls.edu', email='fac_gls@gls.edu', password='Password123!'
        )
        FacultyProfile.objects.create(
            user=self.fac_user, institution=self.inst, department='Computer Science', employee_id='FAC-GLS-99'
        )

        # Student
        self.stu_user = User.objects.create_user(
            username='stu_gls@gls.edu', email='stu_gls@gls.edu', password='Password123!'
        )
        self.stu_profile = StudentProfile.objects.create(
            user=self.stu_user, institution=self.inst, department='Computer Science', student_id='STU-GLS-99'
        )
        self.token = _create_token(self.stu_user, 'student', self.inst)

        # Exam with 5 questions
        self.exam = Exam.objects.create(
            institution=self.inst,
            title='Concurrent Exam',
            created_by=self.fac_user,
            department='Computer Science',
            duration_minutes=60,
            total_marks=5,
            status=Exam.Status.PUBLISHED,
        )
        self.questions = []
        for i in range(1, 6):
            q = Question.objects.create(
                exam=self.exam,
                institution=self.inst,
                order=i,
                question_type=Question.QuestionType.MCQ,
                difficulty=Question.Difficulty.EASY,
                text=f'Question {i}',
                options=['A', 'B', 'C', 'D'],
                correct_answer='A',
                marks=1,
            )
            self.questions.append(q)

        # Attempt
        self.attempt = StudentAttempt.objects.create(
            exam=self.exam,
            student=self.stu_user,
            institution=self.inst,
            status=StudentAttempt.Status.IN_PROGRESS,
        )

    def test_01_batch_save_endpoint(self):
        """Batch save stores all answers in one transaction with correct count."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        payload = {
            'answers': [
                {'question_id': self.questions[0].id, 'answer_text': 'Option A'},
                {'question_id': self.questions[1].id, 'answer_text': 'Option B'},
                {'question_id': self.questions[2].id, 'answer_text': 'Option C'},
            ]
        }
        resp = client.post(f'/api/student/attempts/{self.attempt.id}/save/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['saved'])
        self.assertEqual(resp.data['count'], 3)

        answers = StudentAnswer.objects.filter(attempt=self.attempt)
        self.assertEqual(answers.count(), 3)
        self.assertEqual(
            StudentAnswer.objects.get(attempt=self.attempt, question=self.questions[0]).answer_text,
            'Option A',
        )

    def test_02_fifty_parallel_saves_zero_500s_and_no_duplicates(self):
        """50 parallel save requests produce zero 500 errors and zero duplicate rows."""
        token = self.token
        attempt_id = self.attempt.id
        questions = self.questions

        def _fire_save(worker_id):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            # Target question based on worker_id modulo 5
            q = questions[worker_id % len(questions)]
            if worker_id % 3 == 0:
                # Batch save
                payload = {
                    'answers': [
                        {'question_id': q.id, 'answer_text': f'Answer from worker {worker_id}'},
                        {'question_id': questions[(worker_id + 1) % len(questions)].id, 'answer_text': f'Next from worker {worker_id}'},
                    ]
                }
            else:
                # Single save
                payload = {
                    'question_id': q.id,
                    'answer_text': f'Answer from worker {worker_id}',
                }
            resp = client.post(f'/api/student/attempts/{attempt_id}/save/', payload, format='json')
            return resp.status_code

        # Fire 50 requests across 10 concurrent threads
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_fire_save, i) for i in range(50)]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        # Verify zero 500 errors
        status_500_count = sum(1 for s in results if s == 500)
        self.assertEqual(status_500_count, 0, f"Encountered {status_500_count} HTTP 500 errors!")

        # All requests should be 200 (or clean 503 if database busy)
        for s in results:
            self.assertIn(s, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])

        # Verify no duplicate StudentAnswer rows in database
        total_answers = StudentAnswer.objects.filter(attempt_id=attempt_id).count()
        self.assertLessEqual(total_answers, len(questions))

        # Distinct question count must equal total rows
        distinct_questions = StudentAnswer.objects.filter(attempt_id=attempt_id).values('question_id').distinct().count()
        self.assertEqual(total_answers, distinct_questions, "Duplicate answer rows detected for the same question!")

    def test_03_cross_tenant_attempt_save_returns_404(self):
        """Cross-tenant save attempt returns 404 (IDOR protected)."""
        other_admin = User.objects.create_user(username='other_adm@uni.edu', email='other_adm@uni.edu', password='Password123!')
        AdminProfile.objects.create(user=other_admin)
        other_inst = AdminInstitution.objects.create(
            admin=other_admin, institution_name='Other Univ', institution_code='INST-OTH-01', status=AdminInstitution.STATUS_ACTIVE
        )
        other_stu = User.objects.create_user(username='other_stu@uni.edu', email='other_stu@uni.edu', password='Password123!')
        StudentProfile.objects.create(user=other_stu, institution=other_inst, department='Computer Science')
        other_token = _create_token(other_stu, 'student', other_inst)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {other_token}')
        # Try to save answer to self.attempt (which belongs to GLS)
        resp = client.post(
            f'/api/student/attempts/{self.attempt.id}/save/',
            {'question_id': self.questions[0].id, 'answer_text': 'Hacked'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_04_save_rejected_on_submitted_attempt(self):
        """Once attempt is submitted, saves return 400 Bad Request."""
        self.attempt.status = StudentAttempt.Status.SUBMITTED
        self.attempt.save(update_fields=['status'])

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        resp = client.post(
            f'/api/student/attempts/{self.attempt.id}/save/',
            {'question_id': self.questions[0].id, 'answer_text': 'Late answer'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active', resp.data['detail'].lower())
