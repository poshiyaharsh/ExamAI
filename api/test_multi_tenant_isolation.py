import json
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from api.models import Exam, Question, StudentAttempt, StudentAnswer
from faculty.models import FacultyProfile, Paper
from students.models import StudentProfile


def _create_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class MultiTenantIsolationTestSuite(TestCase):
    def setUp(self):
        self.client = APIClient()

        # ----------------------------------------------------
        # Seed Institute A (GLS)
        from django.core.cache import cache
        cache.clear()

        # ----------------------------------------------------
        self.admin_user_a = User.objects.create_user(
            username='admin_a@gls.edu', email='admin_a@gls.edu', password='Password123!',
            first_name='Admin', last_name='GLS'
        )
        AdminProfile.objects.create(user=self.admin_user_a)
        self.inst_a = AdminInstitution.objects.create(
            admin=self.admin_user_a,
            institution_name='GLS University',
            institution_code='INST-2026-001',
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
            employee_id='FAC-GLS-001',
        )

        self.stu_user_a = User.objects.create_user(
            username='student_a@gls.edu', email='student_a@gls.edu', password='Password123!',
            first_name='Student', last_name='A'
        )
        self.stu_profile_a = StudentProfile.objects.create(
            user=self.stu_user_a,
            institution=self.inst_a,
            department='Computer Science',
            student_id='STU-GLS-001',
        )

        self.exam_a = Exam.objects.create(
            institution=self.inst_a,
            title='Data Structures - GLS',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=60,
            total_marks=50,
            topics=['Algorithms'],
            ai_model_used='qwen2.5-3b',
            status=Exam.Status.PUBLISHED,
        )
        self.q_a1 = Question.objects.create(
            exam=self.exam_a,
            institution=self.inst_a,
            order=1,
            question_type=Question.QuestionType.MCQ,
            difficulty=Question.Difficulty.EASY,
            text='What is a queue?',
            options=['FIFO', 'LIFO', 'None', 'All'],
            correct_answer='FIFO',
            marks=10,
        )
        self.attempt_a = StudentAttempt.objects.create(
            exam=self.exam_a,
            institution=self.inst_a,
            student=self.stu_user_a,
            status=StudentAttempt.Status.IN_PROGRESS,
            total_score=0,
        )

        # ----------------------------------------------------
        # Seed Institute B (Gujarat University)
        # ----------------------------------------------------
        self.admin_user_b = User.objects.create_user(
            username='admin_b@gu.edu', email='admin_b@gu.edu', password='Password123!',
            first_name='Admin', last_name='GU'
        )
        AdminProfile.objects.create(user=self.admin_user_b)
        self.inst_b = AdminInstitution.objects.create(
            admin=self.admin_user_b,
            institution_name='Gujarat University',
            institution_code='INST-2026-002',
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.fac_user_b = User.objects.create_user(
            username='faculty_b@gu.edu', email='faculty_b@gu.edu', password='Password123!',
            first_name='Faculty', last_name='B'
        )
        self.fac_profile_b = FacultyProfile.objects.create(
            user=self.fac_user_b,
            institution=self.inst_b,
            department='Computer Science',
            employee_id='FAC-GU-001',
        )

        self.stu_user_b = User.objects.create_user(
            username='student_b@gu.edu', email='student_b@gu.edu', password='Password123!',
            first_name='Student', last_name='B'
        )
        self.stu_profile_b = StudentProfile.objects.create(
            user=self.stu_user_b,
            institution=self.inst_b,
            department='Computer Science',
            student_id='STU-GU-001',
        )

        self.exam_b = Exam.objects.create(
            institution=self.inst_b,
            title='Operating Systems - GU',
            created_by=self.fac_user_b,
            department='Computer Science',
            duration_minutes=60,
            total_marks=50,
            topics=['Kernel'],
            ai_model_used='qwen2.5-3b',
            status=Exam.Status.PUBLISHED,
        )
        self.q_b1 = Question.objects.create(
            exam=self.exam_b,
            institution=self.inst_b,
            order=1,
            question_type=Question.QuestionType.MCQ,
            difficulty=Question.Difficulty.EASY,
            text='What is a semaphore?',
            options=['Variable', 'Thread', 'None', 'All'],
            correct_answer='Variable',
            marks=10,
        )

        # ----------------------------------------------------
        # Seed Institute C (Suspended Institute)
        # ----------------------------------------------------
        self.admin_user_c = User.objects.create_user(
            username='admin_c@ld.edu', email='admin_c@ld.edu', password='Password123!',
            first_name='Admin', last_name='LD'
        )
        AdminProfile.objects.create(user=self.admin_user_c)
        self.inst_c = AdminInstitution.objects.create(
            admin=self.admin_user_c,
            institution_name='Suspended University',
            institution_code='INST-2026-003',
            status=AdminInstitution.STATUS_SUSPENDED,
        )
        self.stu_user_c = User.objects.create_user(
            username='student_c@ld.edu', email='student_c@ld.edu', password='Password123!',
            first_name='Student', last_name='C'
        )
        self.stu_profile_c = StudentProfile.objects.create(
            user=self.stu_user_c,
            institution=self.inst_c,
            department='Computer Science',
            student_id='STU-LD-001',
        )

        # Tokens
        self.token_admin_a = _create_token(self.admin_user_a, 'admin', self.inst_a)
        self.token_admin_b = _create_token(self.admin_user_b, 'admin', self.inst_b)
        self.token_fac_a = _create_token(self.fac_user_a, 'faculty', self.inst_a)
        self.token_fac_b = _create_token(self.fac_user_b, 'faculty', self.inst_b)
        self.token_stu_a = _create_token(self.stu_user_a, 'student', self.inst_a)
        self.token_stu_b = _create_token(self.stu_user_b, 'student', self.inst_b)

    def test_01_faculty_sees_only_own_institute_students(self):
        """1. Faculty A dashboard lists only Institute A students; never B or C."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        resp = self.client.get('/api/faculty/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data['data']
        # Institute A has exactly 1 student in CS; Institute B also has 1 in CS.
        # total_students in CS must be 1, not 2 or 3!
        self.assertEqual(data['stats']['total_students'], 1)

    def test_02_student_lists_only_own_institute_exams(self):
        """2. Student A lists exams -> only Institute A + own department exams."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')
        resp = self.client.get('/api/student/exams/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        exam_ids = [item['exam']['id'] for item in resp.data]
        self.assertIn(self.exam_a.id, exam_ids)
        self.assertNotIn(self.exam_b.id, exam_ids)

    def test_03_admin_dashboard_and_lists_isolated(self):
        """3. Admin A dashboard, students, exams -> only Institute A data."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        resp_dash = self.client.get('/api/admin/dashboard/')
        self.assertEqual(resp_dash.status_code, status.HTTP_200_OK)
        dash_data = resp_dash.data['data']
        self.assertEqual(dash_data['stats']['total_students'], 1)
        self.assertEqual(dash_data['stats']['total_faculty'], 1)
        self.assertEqual(dash_data['stats']['total_exams'], 1)

        # Admin students list
        resp_stu = self.client.get('/api/admin/students/')
        self.assertEqual(resp_stu.status_code, status.HTTP_200_OK)
        student_emails = [s.get('email') or (s.get('user', {}) if isinstance(s.get('user'), dict) else {}).get('email') for s in resp_stu.data['data']]
        self.assertIn(self.stu_user_a.email, student_emails)
        self.assertNotIn(self.stu_user_b.email, student_emails)

        # Admin exams list
        resp_ex = self.client.get('/api/admin/exams/')
        self.assertEqual(resp_ex.status_code, status.HTTP_200_OK)
        exam_titles = [e['title'] for e in resp_ex.data['data']]
        self.assertIn(self.exam_a.title, exam_titles)
        self.assertNotIn(self.exam_b.title, exam_titles)

    def test_04_idor_cross_institute_returns_404(self):
        """4. Cross-institute ID fetching/editing returns 404 (never 403)."""
        # Student A tries to start Exam B (from Institute B) -> must return 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')
        resp_start = self.client.post(f'/api/student/exams/{self.exam_b.id}/start/')
        self.assertEqual(resp_start.status_code, status.HTTP_404_NOT_FOUND)

        # Faculty A tries to view/edit Exam B -> must return 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        resp_exam_get = self.client.get(f'/api/faculty/exams/{self.exam_b.id}/')
        self.assertEqual(resp_exam_get.status_code, status.HTTP_404_NOT_FOUND)
        resp_exam_patch = self.client.patch(f'/api/faculty/exams/{self.exam_b.id}/', {'title': 'Hacked'})
        self.assertEqual(resp_exam_patch.status_code, status.HTTP_404_NOT_FOUND)

        # Admin A tries to view Student B details -> must return 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        resp_admin_stu = self.client.get(f'/api/admin/students/{self.stu_profile_b.id}/')
        self.assertEqual(resp_admin_stu.status_code, status.HTTP_404_NOT_FOUND)
        resp_admin_res = self.client.get(f'/api/admin/students/{self.stu_profile_b.id}/results/')
        self.assertEqual(resp_admin_res.status_code, status.HTTP_404_NOT_FOUND)

        # Admin A tries to view Exam B -> must return 404
        resp_admin_ex = self.client.get(f'/api/admin/exams/{self.exam_b.id}/')
        self.assertEqual(resp_admin_ex.status_code, status.HTTP_404_NOT_FOUND)

    def test_05_cross_institute_references_blocked(self):
        """5. Student from Institute B cannot save answers or submit attempt of Institute A."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_b}')
        resp_save = self.client.post(
            f'/api/student/attempts/{self.attempt_a.id}/save/',
            {'question_id': self.q_a1.id, 'answer_text': 'FIFO'},
        )
        self.assertEqual(resp_save.status_code, status.HTTP_404_NOT_FOUND)

        resp_submit = self.client.post(f'/api/student/attempts/{self.attempt_a.id}/submit/')
        self.assertEqual(resp_submit.status_code, status.HTTP_404_NOT_FOUND)

    def test_06_search_and_pagination_isolated(self):
        """6. Search, autocomplete, pagination never leaks cross-institute data."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        resp_search = self.client.get('/api/admin/students/?search=Student')
        self.assertEqual(resp_search.status_code, status.HTTP_200_OK)
        # Should only find Student A, not Student B
        self.assertEqual(resp_search.data['stats']['total_students'], 1)
        first_email = resp_search.data['data'][0].get('email') or (resp_search.data['data'][0].get('user', {}) if isinstance(resp_search.data['data'][0].get('user'), dict) else {}).get('email')
        self.assertEqual(first_email, self.stu_user_a.email)

    def test_07_spoofing_tenant_param_is_ignored(self):
        """7. Spoofing instituteId in body, query, or headers is completely ignored."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')
        # Send instituteId of Institute B in headers and query params
        resp = self.client.get(
            f'/api/student/exams/?instituteId={self.inst_b.id}&institution_id={self.inst_b.id}',
            HTTP_X_INSTITUTE_ID=str(self.inst_b.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        exam_ids = [item['exam']['id'] for item in resp.data]
        self.assertIn(self.exam_a.id, exam_ids)
        self.assertNotIn(self.exam_b.id, exam_ids)

    def test_08_cache_keys_scoped_per_tenant(self):
        """8. Cache keys are strictly isolated per institution."""
        from api.tenant import get_tenant_cache_key
        key_a = get_tenant_cache_key(self.inst_a.id, 'dashboard_summary')
        key_b = get_tenant_cache_key(self.inst_b.id, 'dashboard_summary')
        self.assertNotEqual(key_a, key_b)
        self.assertIn(str(self.inst_a.id), key_a)
        self.assertIn(str(self.inst_b.id), key_b)

    def test_09_same_identifier_across_institutes(self):
        """9. Duplicate roll numbers in different institutes can coexist."""
        # Create student in Inst B with same roll number as Student A
        stu_duplicate = User.objects.create_user(
            username='student_dup@gu.edu', email='student_dup@gu.edu', password='Password123!',
        )
        # Both share student_id STU-GLS-001 in different institutes
        profile_dup = StudentProfile.objects.create(
            user=stu_duplicate,
            institution=self.inst_b,
            department='Computer Science',
            student_id='STU-GLS-001',
        )
        self.assertEqual(profile_dup.student_id, self.stu_profile_a.student_id)
        self.assertNotEqual(profile_dup.institution_id, self.stu_profile_a.institution_id)

    def test_10_suspended_institute_blocked_from_login(self):
        """10. Suspended institute users cannot log in."""
        resp_login = self.client.post('/api/student/login/', {
            'email': self.stu_user_c.email,
            'password': 'Password123!',
        })
        self.assertEqual(resp_login.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('suspended', resp_login.data['message'].lower())

    def test_11_route_coverage_tenant_enforcement(self):
        """11. Verify AuthMe returns tenant institution and rejects unauthenticated/tampered tokens."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        resp_me = self.client.get('/api/auth/me/')
        self.assertEqual(resp_me.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_me.data['user']['institution']['id'], self.inst_a.id)

        # Tampered token: Institute A token with mismatched ID in payload
        tampered_token = _create_token(self.fac_user_a, 'faculty', self.inst_b)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tampered_token}')
        resp_tampered = self.client.get('/api/auth/me/')
        self.assertEqual(resp_tampered.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_12_per_tab_session_isolation(self):
        """12. Separate concurrent client tokens operate in full isolation."""
        client_admin_a = APIClient()
        client_admin_a.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        client_fac_b = APIClient()
        client_fac_b.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_b}')

        client_stu_a = APIClient()
        client_stu_a.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')

        res_a = client_admin_a.get('/api/admin/dashboard/')
        res_b = client_fac_b.get('/api/faculty/dashboard/')
        res_c = client_stu_a.get('/api/student/exams/')

        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)
        self.assertEqual(res_c.status_code, status.HTTP_200_OK)

        self.assertEqual(res_a.data['data']['stats']['total_exams'], 1)
        self.assertEqual(res_b.data['data']['stats']['total_exams'], 1)
        self.assertEqual(len(res_c.data), 1)

    def test_13_scoring_and_department_filtering_preserved(self):
        """13. Existing scoring and department filtering continue to function smoothly."""
        from api.utils.scoring import is_objective_answer_correct
        self.assertTrue(is_objective_answer_correct(self.q_a1, 'FIFO'))
        self.assertFalse(is_objective_answer_correct(self.q_a1, 'LIFO'))

    def test_14_atmiya_exam_visible_to_same_dept_student(self):
        """14. Exam created by faculty is visible to students of same institute and department."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')
        resp_exams = self.client.get('/api/student/exams/')
        self.assertEqual(resp_exams.status_code, status.HTTP_200_OK)
        exam_ids = [item['exam']['id'] for item in resp_exams.data]
        self.assertIn(self.exam_a.id, exam_ids)

        # Check student dashboard
        resp_dash = self.client.get('/api/student/dashboard/')
        self.assertEqual(resp_dash.status_code, status.HTTP_200_OK)
        ongoing_or_upcoming = [e['id'] for e in resp_dash.data['data']['ongoing_exams']] + [e['id'] for e in resp_dash.data['data']['upcoming_exams']]
        self.assertIn(self.exam_a.id, ongoing_or_upcoming)

    def test_15_different_department_student_does_not_see_exam(self):
        """15. Student of same institute but DIFFERENT department does NOT see the exam."""
        diff_dept_user = User.objects.create_user(
            username='diff_dept@gls.edu', email='diff_dept@gls.edu', password='Password123!',
        )
        diff_profile = StudentProfile.objects.create(
            user=diff_dept_user, institution=self.inst_a, department='Mechanical Engineering', student_id='STU-DIFF-01'
        )
        token_diff = _create_token(diff_dept_user, 'student', self.inst_a)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_diff}')

        resp_exams = self.client.get('/api/student/exams/')
        self.assertEqual(resp_exams.status_code, status.HTTP_200_OK)
        exam_ids = [item['exam']['id'] for item in resp_exams.data]
        self.assertNotIn(self.exam_a.id, exam_ids)

        resp_dash = self.client.get('/api/student/dashboard/')
        self.assertEqual(resp_dash.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_dash.data['data']['stats']['total_available'], 0)

        # Starting the exam returns 404 (IDOR protection)
        resp_start = self.client.post(f'/api/student/exams/{self.exam_a.id}/start/')
        self.assertEqual(resp_start.status_code, status.HTTP_404_NOT_FOUND)

    def test_16_other_institute_student_does_not_see_and_returns_404(self):
        """16. Student of ANOTHER institute with same department does not see exam and gets 404 on ID."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_b}')
        resp_exams = self.client.get('/api/student/exams/')
        self.assertEqual(resp_exams.status_code, status.HTTP_200_OK)
        exam_ids = [item['exam']['id'] for item in resp_exams.data]
        self.assertNotIn(self.exam_a.id, exam_ids)

        resp_start = self.client.post(f'/api/student/exams/{self.exam_a.id}/start/')
        self.assertEqual(resp_start.status_code, status.HTTP_404_NOT_FOUND)

    def test_17_exam_visibility_checker_and_publish_flow(self):
        """17. Faculty visibility checker displays student count and reasons; publish invalidates cache."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')

        # View exam detail with visibility
        resp_detail = self.client.get(f'/api/faculty/exams/{self.exam_a.id}/')
        self.assertEqual(resp_detail.status_code, status.HTTP_200_OK)
        self.assertIn('visibility', resp_detail.data)
        vis = resp_detail.data['visibility']
        self.assertTrue(vis['is_visible'])
        self.assertEqual(vis['eligible_students_count'], 1)
        self.assertIn('Computer Science', vis['status_summary'])

        # Create draft exam and publish
        draft_exam = Exam.objects.create(
            institution=self.inst_a,
            title='New Draft Exam',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=30,
            total_marks=1,
            status=Exam.Status.DRAFT,
        )
        Question.objects.create(
            exam=draft_exam,
            institution=self.inst_a,
            order=1,
            question_type=Question.QuestionType.MCQ,
            difficulty=Question.Difficulty.EASY,
            text='Draft Q?',
            marks=1,
        )

        resp_pub = self.client.post(f'/api/faculty/exams/{draft_exam.id}/publish/')
        self.assertEqual(resp_pub.status_code, status.HTTP_200_OK)
        self.assertIn('Visible to', resp_pub.data['message'])

        # Student immediately sees it after publish (cache invalidated)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')
        resp_student = self.client.get('/api/student/exams/')
        self.assertEqual(resp_student.status_code, status.HTTP_200_OK)
        exam_ids = [item['exam']['id'] for item in resp_student.data]
        self.assertIn(draft_exam.id, exam_ids)

    def test_18_exam_schedule_rules(self):
        """18. Future scheduled exam is shown as upcoming but cannot start; ended exam cannot start."""
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()

        # Future exam
        future_exam = Exam.objects.create(
            institution=self.inst_a,
            title='Future Midterm',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=45,
            total_marks=1,
            status=Exam.Status.PUBLISHED,
            starts_at=now + timedelta(days=2),
            ends_at=now + timedelta(days=3),
        )
        Question.objects.create(
            exam=future_exam, institution=self.inst_a, order=1,
            question_type=Question.QuestionType.MCQ, difficulty=Question.Difficulty.EASY,
            text='Q1', marks=1,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a}')
        resp_student = self.client.get('/api/student/exams/')
        self.assertEqual(resp_student.status_code, status.HTTP_200_OK)
        future_entry = next((e for e in resp_student.data if e['exam']['id'] == future_exam.id), None)
        self.assertIsNotNone(future_entry)
        self.assertFalse(future_entry['available'])
        self.assertIn('scheduled for', future_entry['availability_reason'].lower())

        # Attempt to start future exam -> rejected with 400
        resp_start = self.client.post(f'/api/student/exams/{future_exam.id}/start/')
        self.assertEqual(resp_start.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('scheduled', resp_start.data['detail'].lower())

        # Ended exam
        ended_exam = Exam.objects.create(
            institution=self.inst_a,
            title='Ended Exam',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=30,
            total_marks=1,
            status=Exam.Status.PUBLISHED,
            starts_at=now - timedelta(days=5),
            ends_at=now - timedelta(days=1),
        )
        Question.objects.create(
            exam=ended_exam, institution=self.inst_a, order=1,
            question_type=Question.QuestionType.MCQ, difficulty=Question.Difficulty.EASY,
            text='Q1', marks=1,
        )
        resp_start_ended = self.client.post(f'/api/student/exams/{ended_exam.id}/start/')
        self.assertEqual(resp_start_ended.status_code, status.HTTP_404_NOT_FOUND)

    def test_19_admin_exam_audit_endpoint(self):
        """19. Admin audit endpoint scans exams and reports health metrics."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        resp_audit = self.client.get('/api/admin/exams/audit/')
        self.assertEqual(resp_audit.status_code, status.HTTP_200_OK)
        audit_data = resp_audit.data['data']
        self.assertIn('total_exams', audit_data)
        self.assertIn('healthy_exams_count', audit_data)
        self.assertIn('issue_exams_count', audit_data)
        self.assertGreaterEqual(audit_data['healthy_exams_count'], 1)

