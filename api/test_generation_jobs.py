from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution
from faculty.models import FacultyProfile
from api.models import Exam, Notification, PaperGenerationJob, Question


def _get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class PaperGenerationJobTestCase(TestCase):
    def setUp(self):
        self.admin1 = User.objects.create_user(username='admin1', password='password123', email='admin1@test.edu')
        self.inst = AdminInstitution.objects.create(admin=self.admin1, institution_name='Test University', institution_code='INST-TEST-1')

        self.admin2 = User.objects.create_user(username='admin2', password='password123', email='admin2@test.edu')
        self.inst2 = AdminInstitution.objects.create(admin=self.admin2, institution_name='Other College', institution_code='INST-TEST-2')

        # Faculty 1 (Computer Science)
        self.user1 = User.objects.create_user(username='prof_cs', password='password123', email='cs@test.edu')
        self.prof1 = FacultyProfile.objects.create(user=self.user1, institution=self.inst, department='Computer Science')

        # Faculty 2 (Mechanical Engineering, same inst)
        self.user2 = User.objects.create_user(username='prof_mech', password='password123', email='mech@test.edu')
        self.prof2 = FacultyProfile.objects.create(user=self.user2, institution=self.inst, department='Mechanical Engineering')

        # Faculty 3 (Different institution)
        self.user3 = User.objects.create_user(username='prof_other', password='password123', email='other@test.edu')
        self.prof3 = FacultyProfile.objects.create(user=self.user3, institution=self.inst2, department='Computer Science')

        self.client1 = APIClient()
        self.client1.credentials(HTTP_AUTHORIZATION=f'Bearer {_get_token(self.user1, "Faculty", self.inst)}')

        self.client2 = APIClient()
        self.client2.credentials(HTTP_AUTHORIZATION=f'Bearer {_get_token(self.user2, "Faculty", self.inst)}')

        self.client3 = APIClient()
        self.client3.credentials(HTTP_AUTHORIZATION=f'Bearer {_get_token(self.user3, "Faculty", self.inst2)}')

    def test_job_creation_and_status_polling(self):
        """Generation creates a PaperGenerationJob and returns 202 with job_id."""
        with patch('api.generate_paper.threading.Thread'):
            res = self.client1.post('/api/faculty/exams/generate/', {
                'title': 'Operating Systems Midterm',
                'duration_minutes': 60,
                'total_marks': 20,
                'topics': ['Memory Management', 'Deadlocks'],
                'question_types': ['mcq', 'subjective'],
                'ai_model': 'phi3-mini',
                'department': 'Computer Science',
            })
            self.assertEqual(res.status_code, 202)
            data = res.json()
            self.assertIn('job_id', data)
            self.assertEqual(data['status'], 'queued')
            job_id = data['job_id']

            # Poll job status
            status_res = self.client1.get(f'/api/papers/generations/{job_id}/')
            self.assertEqual(status_res.status_code, 200)
            status_data = status_res.json()
            self.assertEqual(status_data['id'], job_id)
            self.assertEqual(status_data['status'], 'queued')
            self.assertEqual(status_data['exam_title'], 'Operating Systems Midterm')

    def test_double_submission_prevented(self):
        """If a generation job is already active, subsequent generate requests return 409 Conflict."""
        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user1,
            department='Computer Science',
            model='phi3-mini',
            status=PaperGenerationJob.Status.RUNNING,
            current_step='Contacting AI model',
            progress=25,
            question_count_requested=10,
        )

        res = self.client1.post('/api/faculty/exams/generate/', {
            'title': 'Second Click Attempt',
            'duration_minutes': 60,
            'total_marks': 20,
            'topics': ['Networking'],
            'question_types': ['mcq'],
            'ai_model': 'phi3-mini',
            'department': 'Computer Science',
        })
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()['active_job_id'], job.id)

    def test_idor_protection_for_generation_job(self):
        """Faculty from a different department or institution cannot access another faculty's job."""
        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user1,
            department='Computer Science',
            model='phi3-mini',
            status=PaperGenerationJob.Status.RUNNING,
            progress=30,
        )

        # Faculty 2 (Mechanical) tries to read Job of Faculty 1
        res2 = self.client2.get(f'/api/papers/generations/{job.id}/')
        self.assertEqual(res2.status_code, 403)

        # Faculty 3 (Different institution) tries to read Job of Faculty 1
        res3 = self.client3.get(f'/api/papers/generations/{job.id}/')
        self.assertEqual(res3.status_code, 403)

        # Creator Faculty 1 CAN read it
        res1 = self.client1.get(f'/api/papers/generations/{job.id}/')
        self.assertEqual(res1.status_code, 200)

    def test_active_job_and_list_endpoints(self):
        """Active job returns the running job and list endpoint returns recent jobs."""
        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user1,
            department='Computer Science',
            model='phi3-mini',
            status=PaperGenerationJob.Status.RUNNING,
            progress=40,
        )

        # Active job endpoint
        res = self.client1.get('/api/papers/generations/active/')
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.json()['active_job'])
        self.assertEqual(res.json()['active_job']['id'], job.id)

        # List endpoint
        list_res = self.client1.get('/api/papers/generations/')
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(len(list_res.json()['results']), 1)

    def test_cancel_generation_job(self):
        """Cancelling a running job sets is_cancelled and cleans up draft state."""
        exam = Exam.objects.create(
            institution=self.inst,
            title='Cancelled Exam',
            created_by=self.user1,
            department='Computer Science',
            duration_minutes=30,
            total_marks=10,
            ai_model_used='phi3-mini',
            status=Exam.Status.GENERATING,
        )
        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user1,
            department='Computer Science',
            exam=exam,
            model='phi3-mini',
            status=PaperGenerationJob.Status.RUNNING,
            progress=35,
        )

        res = self.client1.post(f'/api/papers/generations/{job.id}/cancel/')
        self.assertEqual(res.status_code, 200)

        job.refresh_from_db()
        self.assertTrue(job.is_cancelled)
        self.assertEqual(job.status, PaperGenerationJob.Status.CANCELLED)

        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.FAILED)

    def test_job_timeout_handling(self):
        """Job running for longer than 10 minutes transitions to FAILED upon query."""
        old_time = timezone.now() - timedelta(minutes=15)
        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user1,
            department='Computer Science',
            model='phi3-mini',
            status=PaperGenerationJob.Status.RUNNING,
            progress=50,
        )
        # Manually backdate created_at
        PaperGenerationJob.objects.filter(id=job.id).update(created_at=old_time)

        res = self.client1.get(f'/api/papers/generations/{job.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['status'], 'failed')
        self.assertIn('timed out', res.json()['error_message'])

    def test_review_required_before_publishing(self):
        """Generated exams are drafts and require confirm-review before publishing."""
        exam = Exam.objects.create(
            institution=self.inst,
            title='AI Generated Paper',
            created_by=self.user1,
            department='Computer Science',
            duration_minutes=60,
            total_marks=5,
            ai_model_used='phi3-mini',
            status=Exam.Status.DRAFT,
            is_reviewed=False,
        )
        Question.objects.create(
            exam=exam,
            institution=self.inst,
            department='Computer Science',
            order=1,
            question_type='mcq',
            difficulty='medium',
            text='What is a process?',
            options=['Program in execution', 'A file', 'A mouse', 'A monitor'],
            correct_answer='Program in execution',
            marks=5,
        )

        # Attempt to publish without reviewing
        pub_res = self.client1.post(f'/api/faculty/exams/{exam.id}/publish/')
        self.assertEqual(pub_res.status_code, 400)
        self.assertIn('reviewed and confirmed', pub_res.json()['detail'])

        # Confirm review
        rev_res = self.client1.post(f'/api/faculty/exams/{exam.id}/confirm-review/')
        self.assertEqual(rev_res.status_code, 200)
        exam.refresh_from_db()
        self.assertTrue(exam.is_reviewed)

        # Now publish succeeds
        pub_success = self.client1.post(f'/api/faculty/exams/{exam.id}/publish/')
        self.assertEqual(pub_success.status_code, 200)
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.PUBLISHED)

    def test_notification_endpoints(self):
        """Notification list, single read, and mark-all-read work as expected."""
        n1 = Notification.objects.create(
            user=self.user1,
            institution=self.inst,
            title='Paper Ready',
            message='Your exam is ready for review.',
            type='success',
            link='/faculty/exams/1/edit',
        )
        n2 = Notification.objects.create(
            user=self.user1,
            institution=self.inst,
            title='System Alert',
            message='Maintenance scheduled.',
            type='info',
        )

        list_res = self.client1.get('/api/notifications/')
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.json()['unread_count'], 2)

        # Mark single as read
        read_res = self.client1.post(f'/api/notifications/{n1.id}/read/')
        self.assertEqual(read_res.status_code, 200)
        n1.refresh_from_db()
        self.assertTrue(n1.is_read)

        # Mark all read
        all_res = self.client1.post('/api/notifications/read-all/')
        self.assertEqual(all_res.status_code, 200)
        n2.refresh_from_db()
        self.assertTrue(n2.is_read)

    def test_student_forbidden_from_generation_jobs(self):
        """Students cannot read, list, or cancel faculty paper generation jobs."""
        student_user = User.objects.create_user(username='student1', password='password123', email='student@test.edu')
        student_client = APIClient()
        student_client.credentials(HTTP_AUTHORIZATION=f'Bearer {_get_token(student_user, "Student", self.inst)}')

        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user1,
            department='Computer Science',
            model='phi3-mini',
            status=PaperGenerationJob.Status.RUNNING,
        )

        res_get = student_client.get(f'/api/papers/generations/{job.id}/')
        self.assertEqual(res_get.status_code, 403)

        res_cancel = student_client.post(f'/api/papers/generations/{job.id}/cancel/')
        self.assertEqual(res_cancel.status_code, 403)

        res_list = student_client.get('/api/papers/generations/')
        self.assertEqual(res_list.status_code, 403)

    def test_server_restart_cleanup(self):
        """cleanup_stuck_generation_jobs transitions stuck queued/running jobs to failed."""
        from api.apps import cleanup_stuck_generation_jobs
        exam = Exam.objects.create(
            institution=self.inst,
            title='Interrupted Exam',
            created_by=self.user1,
            department='Computer Science',
            duration_minutes=45,
            total_marks=20,
            ai_model_used='phi3-mini',
            status=Exam.Status.GENERATING,
        )
        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user1,
            department='Computer Science',
            exam=exam,
            model='phi3-mini',
            status=PaperGenerationJob.Status.RUNNING,
        )

        cleanup_stuck_generation_jobs()

        job.refresh_from_db()
        self.assertEqual(job.status, PaperGenerationJob.Status.FAILED)
        self.assertIn('server restart', job.error_message)

        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.FAILED)
        self.assertIn('server restart', exam.error_message)

    def test_ollama_failure_states_handled(self):
        """_run_generation gracefully handles connection errors, missing model, timeouts without crashing or staying running."""
        from api.generate_paper import _run_generation

        # Case 1: Ollama Connection Refused
        exam1 = Exam.objects.create(
            institution=self.inst, title='Conn Error Exam', created_by=self.user1,
            department='Computer Science', duration_minutes=30, total_marks=5,
            ai_model_used='phi3-mini', status=Exam.Status.GENERATING,
        )
        job1 = PaperGenerationJob.objects.create(
            institution=self.inst, faculty=self.user1, department='Computer Science',
            exam=exam1, model='phi3-mini', status=PaperGenerationJob.Status.RUNNING,
        )
        with patch('api.generate_paper._generate_type_questions', side_effect=Exception('Failed to establish a new connection: Connection refused')):
            _run_generation(job1.id, exam1.id, 'phi3-mini', ['Intro'], ['mcq'], 5, {}, '')

        job1.refresh_from_db()
        self.assertEqual(job1.status, PaperGenerationJob.Status.FAILED)
        self.assertIn('Could not reach Ollama', job1.error_message)

        # Case 2: Model not found
        exam2 = Exam.objects.create(
            institution=self.inst, title='Missing Model Exam', created_by=self.user1,
            department='Computer Science', duration_minutes=30, total_marks=5,
            ai_model_used='nonexistent-model', status=Exam.Status.GENERATING,
        )
        job2 = PaperGenerationJob.objects.create(
            institution=self.inst, faculty=self.user1, department='Computer Science',
            exam=exam2, model='nonexistent-model', status=PaperGenerationJob.Status.RUNNING,
        )
        with patch('api.generate_paper._generate_type_questions', side_effect=Exception("model 'nonexistent-model' not found")):
            _run_generation(job2.id, exam2.id, 'nonexistent-model', ['Intro'], ['mcq'], 5, {}, '')

        job2.refresh_from_db()
        self.assertEqual(job2.status, PaperGenerationJob.Status.FAILED)
        self.assertIn('was not found', job2.error_message)

        # Case 3: Timeout
        exam3 = Exam.objects.create(
            institution=self.inst, title='Timeout Exam', created_by=self.user1,
            department='Computer Science', duration_minutes=30, total_marks=5,
            ai_model_used='phi3-mini', status=Exam.Status.GENERATING,
        )
        job3 = PaperGenerationJob.objects.create(
            institution=self.inst, faculty=self.user1, department='Computer Science',
            exam=exam3, model='phi3-mini', status=PaperGenerationJob.Status.RUNNING,
        )
        with patch('api.generate_paper._generate_type_questions', side_effect=Exception("Request timed out after 180s")):
            _run_generation(job3.id, exam3.id, 'phi3-mini', ['Intro'], ['mcq'], 5, {}, '')

        job3.refresh_from_db()
        self.assertEqual(job3.status, PaperGenerationJob.Status.FAILED)
        self.assertIn('took too long', job3.error_message)

    def test_exam_deletion_endpoint(self):
        """Faculty can delete an unattempted exam."""
        exam = Exam.objects.create(
            institution=self.inst,
            title='Delete Me',
            created_by=self.user1,
            department='Computer Science',
            duration_minutes=30,
            total_marks=10,
            ai_model_used='phi3-mini',
            status=Exam.Status.DRAFT,
        )
        del_res = self.client1.delete(f'/api/faculty/exams/{exam.id}/')
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(Exam.objects.filter(id=exam.id).exists())

