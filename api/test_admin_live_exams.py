"""Comprehensive Automated Test Suite for Admin Live Examinations Multi-Tenant Isolation.

Validates:
1. Institute A vs Institute B isolation (eligible_count matches ONLY Institute A students).
2. Live Roster drill-down isolation (Admin B receives HTTP 404 for Institute A exam).
3. Spoofed institution headers/query parameters are strictly ignored.
4. Inactive and transferred students are excluded from the eligible cohort.
5. Invariant: not_started + in_progress + submitted == eligible_count holds;
   ineligible attempts reported separately.
6. Live window schedule boundaries (starts_at <= now <= ends_at).
7. Zero eligible students handled gracefully without ZeroDivisionError.
8. Role-based access control (HTTP 403 for Faculty/Students, HTTP 401 for Anon).
9. Database query count stays constant with batch computation (O(1) database queries).
"""

from datetime import timedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from api.exams.eligibility import (
    compute_batch_live_exam_metrics,
    compute_live_exam_metrics,
    eligible_students_queryset,
    live_exams_queryset,
)
from api.models import Exam, Question, StudentAttempt
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


class AdminLiveExamsIsolationTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.now = timezone.now()

        # ====================================================
        # Institution A (GLS University)
        # ====================================================
        self.admin_user_a = User.objects.create_user(
            username='admin_a@gls.edu', email='admin_a@gls.edu', password='Password123!',
            first_name='Admin', last_name='GLS'
        )
        AdminProfile.objects.create(user=self.admin_user_a)
        self.inst_a = AdminInstitution.objects.create(
            admin=self.admin_user_a,
            institution_name='GLS University',
            institution_code='GLS-001',
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.fac_user_a = User.objects.create_user(
            username='fac_a@gls.edu', email='fac_a@gls.edu', password='Password123!',
            first_name='Faculty', last_name='A'
        )
        FacultyProfile.objects.create(
            user=self.fac_user_a,
            institution=self.inst_a,
            department='Computer Science',
            employee_id='FAC-GLS-101',
        )

        # 3 Active CS Students in GLS
        self.stu_a1 = User.objects.create_user(
            username='stu_a1@gls.edu', email='stu_a1@gls.edu', password='Password123!',
            first_name='Alice', last_name='A'
        )
        StudentProfile.objects.create(
            user=self.stu_a1, institution=self.inst_a, department='Computer Science', student_id='GLS-CS-01'
        )

        self.stu_a2 = User.objects.create_user(
            username='stu_a2@gls.edu', email='stu_a2@gls.edu', password='Password123!',
            first_name='Bob', last_name='A'
        )
        StudentProfile.objects.create(
            user=self.stu_a2, institution=self.inst_a, department='Computer Science', student_id='GLS-CS-02'
        )

        self.stu_a3 = User.objects.create_user(
            username='stu_a3@gls.edu', email='stu_a3@gls.edu', password='Password123!',
            first_name='Charlie', last_name='A'
        )
        StudentProfile.objects.create(
            user=self.stu_a3, institution=self.inst_a, department='Computer Science', student_id='GLS-CS-03'
        )

        # Live exam for Institute A (starts 10m ago, ends in 50m)
        self.live_exam_a = Exam.objects.create(
            institution=self.inst_a,
            title='Algorithms Live GLS',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=60,
            total_marks=100,
            starts_at=self.now - timedelta(minutes=10),
            ends_at=self.now + timedelta(minutes=50),
            status=Exam.Status.PUBLISHED,
        )

        # ====================================================
        # Institution B (Atmiya University)
        # ====================================================
        self.admin_user_b = User.objects.create_user(
            username='admin_b@atmiya.edu', email='admin_b@atmiya.edu', password='Password123!',
            first_name='Admin', last_name='Atmiya'
        )
        AdminProfile.objects.create(user=self.admin_user_b)
        self.inst_b = AdminInstitution.objects.create(
            admin=self.admin_user_b,
            institution_name='Atmiya University',
            institution_code='ATM-002',
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.fac_user_b = User.objects.create_user(
            username='fac_b@atmiya.edu', email='fac_b@atmiya.edu', password='Password123!',
            first_name='Faculty', last_name='B'
        )
        FacultyProfile.objects.create(
            user=self.fac_user_b,
            institution=self.inst_b,
            department='Computer Science',
            employee_id='FAC-ATM-201',
        )

        # 2 Active CS Students in Atmiya
        self.stu_b1 = User.objects.create_user(
            username='stu_b1@atmiya.edu', email='stu_b1@atmiya.edu', password='Password123!',
            first_name='Dave', last_name='B'
        )
        StudentProfile.objects.create(
            user=self.stu_b1, institution=self.inst_b, department='Computer Science', student_id='ATM-CS-01'
        )

        self.stu_b2 = User.objects.create_user(
            username='stu_b2@atmiya.edu', email='stu_b2@atmiya.edu', password='Password123!',
            first_name='Eve', last_name='B'
        )
        StudentProfile.objects.create(
            user=self.stu_b2, institution=self.inst_b, department='Computer Science', student_id='ATM-CS-02'
        )

        # Tokens
        self.token_admin_a = _create_token(self.admin_user_a, 'admin', self.inst_a)
        self.token_admin_b = _create_token(self.admin_user_b, 'admin', self.inst_b)
        self.token_fac_a = _create_token(self.fac_user_a, 'faculty', self.inst_a)
        self.token_stu_a1 = _create_token(self.stu_a1, 'student', self.inst_a)

    def test_01_institution_isolation_eligible_count(self):
        """Test 1: Admin A sees strictly 3 eligible students; Admin B sees 0 exams."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        res_a = self.client.get('/api/admin/dashboard/')
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        data_a = res_a.data.get('data', res_a.data)
        ongoing_a = data_a.get('ongoing_exams', [])
        self.assertEqual(len(ongoing_a), 1)
        exam_item = ongoing_a[0]
        # Invariant check: eligible count MUST be exactly 3 (GLS students only, not 5!)
        self.assertEqual(exam_item['eligible_count'], 3)
        self.assertEqual(exam_item['eligible_students'], 3)

        # Admin B should see 0 ongoing exams
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_b}')
        res_b = self.client.get('/api/admin/dashboard/')
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)
        data_b = res_b.data.get('data', res_b.data)
        ongoing_b = data_b.get('ongoing_exams', [])
        self.assertEqual(len(ongoing_b), 0)

    def test_02_drilldown_live_roster_404_on_cross_tenant(self):
        """Test 2: Admin A gets 200 on Exam A roster; Admin B gets 404 Not Found."""
        # Admin A requesting Exam A live roster
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        res_a = self.client.get(f'/api/admin/exams/{self.live_exam_a.id}/live-roster/')
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        self.assertIn('roster', res_a.data['data'])
        self.assertEqual(res_a.data['data']['metrics']['eligible_count'], 3)
        # All students in roster belong to Institute A
        for student in res_a.data['data']['roster']:
            self.assertIn('gls.edu', student['email'])

        # Admin B requesting Exam A live roster must return 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_b}')
        res_b = self.client.get(f'/api/admin/exams/{self.live_exam_a.id}/live-roster/')
        self.assertEqual(res_b.status_code, status.HTTP_404_NOT_FOUND)

    def test_03_spoofed_institution_parameters_ignored(self):
        """Test 3: Passing another institution ID in query params/headers is ignored."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}',
            HTTP_X_INSTITUTION_ID=str(self.inst_b.id),
        )
        # Dashboard with spoofed param
        res = self.client.get(f'/api/admin/dashboard/?institution={self.inst_b.id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data.get('data', res.data)
        ongoing = data.get('ongoing_exams', [])
        self.assertEqual(len(ongoing), 1)
        self.assertEqual(ongoing[0]['eligible_count'], 3)

        # Live roster with spoofed param
        res_roster = self.client.get(
            f'/api/admin/exams/{self.live_exam_a.id}/live-roster/?institution_id={self.inst_b.id}'
        )
        self.assertEqual(res_roster.status_code, status.HTTP_200_OK)
        self.assertEqual(res_roster.data['data']['metrics']['eligible_count'], 3)

    def test_04_inactive_and_transferred_students_excluded(self):
        """Test 4: Deactivated user and transferred department student are excluded."""
        # Deactivate Alice
        self.stu_a1.is_active = False
        self.stu_a1.save()

        # Transfer Bob to Mechanical Engineering
        bob_profile = self.stu_a2.student_profile
        bob_profile.department = 'Mechanical Engineering'
        bob_profile.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        res = self.client.get(f'/api/admin/exams/{self.live_exam_a.id}/live-roster/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Only Charlie is active and in Computer Science
        self.assertEqual(res.data['data']['metrics']['eligible_count'], 1)
        self.assertEqual(len(res.data['data']['roster']), 1)
        self.assertEqual(res.data['data']['roster'][0]['email'], 'stu_a3@gls.edu')

    def test_05_invariant_and_ineligible_attempts(self):
        """Test 5: not_started + in_progress + submitted == eligible_count holds;
        ineligible attempts reported separately."""
        # Student A1 submitted
        StudentAttempt.objects.create(
            exam=self.live_exam_a,
            institution=self.inst_a,
            student=self.stu_a1,
            status=StudentAttempt.Status.SUBMITTED,
            total_score=85,
            submitted_at=self.now,
        )
        # Student A2 in progress
        StudentAttempt.objects.create(
            exam=self.live_exam_a,
            institution=self.inst_a,
            student=self.stu_a2,
            status=StudentAttempt.Status.IN_PROGRESS,
            total_score=0,
            started_at=self.now,
        )
        # Student A3 not started

        # Ineligible attempt: Student B1 from Atmiya somehow attempted Exam A
        StudentAttempt.objects.create(
            exam=self.live_exam_a,
            institution=self.inst_b,
            student=self.stu_b1,
            status=StudentAttempt.Status.SUBMITTED,
            total_score=70,
            submitted_at=self.now,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        res = self.client.get(f'/api/admin/exams/{self.live_exam_a.id}/live-roster/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        m = res.data['data']['metrics']

        # Invariant check
        self.assertEqual(m['eligible_count'], 3)
        self.assertEqual(m['submitted_count'], 1)
        self.assertEqual(m['in_progress_count'], 1)
        self.assertEqual(m['not_started_count'], 1)
        self.assertEqual(
            m['not_started_count'] + m['in_progress_count'] + m['submitted_count'],
            m['eligible_count']
        )

        # Ineligible attempts check
        self.assertEqual(m['ineligible_attempts'], 1)
        inel = res.data['data']['ineligible_attempts']
        self.assertEqual(len(inel), 1)
        self.assertEqual(inel[0]['email'], 'stu_b1@atmiya.edu')
        self.assertIn('different institution', inel[0]['reason'].lower())

    def test_06_schedule_boundaries(self):
        """Test 6: Past exams and future exams are excluded from live window."""
        # Future exam
        Exam.objects.create(
            institution=self.inst_a,
            title='Future Exam',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=60,
            total_marks=100,
            starts_at=self.now + timedelta(hours=2),
            ends_at=self.now + timedelta(hours=3),
            status=Exam.Status.PUBLISHED,
        )
        # Past exam
        Exam.objects.create(
            institution=self.inst_a,
            title='Past Exam',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=60,
            total_marks=100,
            starts_at=self.now - timedelta(hours=3),
            ends_at=self.now - timedelta(hours=2),
            status=Exam.Status.PUBLISHED,
        )

        live_qs = live_exams_queryset(self.inst_a, self.now)
        self.assertEqual(live_qs.count(), 1)
        self.assertEqual(live_qs.first().id, self.live_exam_a.id)

    def test_07_zero_eligible_students_no_crash(self):
        """Test 7: Exam with 0 eligible students returns 0 participation without crash."""
        exam_empty = Exam.objects.create(
            institution=self.inst_a,
            title='Civil Eng Exam',
            created_by=self.fac_user_a,
            department='Civil Engineering',
            duration_minutes=60,
            total_marks=50,
            starts_at=self.now - timedelta(minutes=10),
            ends_at=self.now + timedelta(minutes=50),
            status=Exam.Status.PUBLISHED,
        )
        metrics = compute_live_exam_metrics(exam_empty, self.now)
        self.assertEqual(metrics['eligible_count'], 0)
        self.assertEqual(metrics['submitted_count'], 0)
        self.assertEqual(metrics['in_progress_count'], 0)
        self.assertEqual(metrics['not_started_count'], 0)
        self.assertEqual(metrics['participation_percent'], 0.0)

    def test_08_rbac_live_roster_permissions(self):
        """Test 8: Faculty and Students receive HTTP 403 on live roster."""
        # Faculty
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        res_fac = self.client.get(f'/api/admin/exams/{self.live_exam_a.id}/live-roster/')
        self.assertEqual(res_fac.status_code, status.HTTP_403_FORBIDDEN)

        # Student
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_stu_a1}')
        res_stu = self.client.get(f'/api/admin/exams/{self.live_exam_a.id}/live-roster/')
        self.assertEqual(res_stu.status_code, status.HTTP_403_FORBIDDEN)

        # Anonymous
        self.client.credentials()
        res_anon = self.client.get(f'/api/admin/exams/{self.live_exam_a.id}/live-roster/')
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_09_constant_database_queries_batch_metrics(self):
        """Test 9: Batch live exam metrics runs in constant O(1) database queries."""
        # Create 4 more live exams in GLS across different departments
        depts = ['Information Technology', 'Civil Engineering', 'Mechanical Engineering', 'Electrical Engineering']
        created_exams = [self.live_exam_a]
        for idx, dept in enumerate(depts, start=2):
            e = Exam.objects.create(
                institution=self.inst_a,
                title=f'Live Exam {idx}',
                created_by=self.fac_user_a,
                department=dept,
                duration_minutes=60,
                total_marks=50,
                starts_at=self.now - timedelta(minutes=10),
                ends_at=self.now + timedelta(minutes=50),
                status=Exam.Status.PUBLISHED,
            )
            created_exams.append(e)

        # Evaluate 5 live exams with compute_batch_live_exam_metrics
        # Should execute only 2 queries: 1 for student profiles + 1 for attempts
        with self.assertNumQueries(2):
            batch_results, live_summary = compute_batch_live_exam_metrics(created_exams, self.inst_a, self.now)

        self.assertEqual(len(batch_results), 5)
        batch_map = {item['id']: item for item in batch_results}
        self.assertEqual(batch_map[self.live_exam_a.id]['eligible_count'], 3)
        self.assertEqual(live_summary['live_exams_count'], 5)

    def test_10_dashboard_limits_to_6_when_15_live_exams_and_orders_desc(self):
        """Test 10: 15 live exams returns strictly 6, live_total=15, has_more=True,
        and ordered by starts_at descending."""
        # Remove live_exam_a to have exactly 15 clean live exams
        Exam.objects.filter(institution=self.inst_a).delete()
        cache.clear()

        # Create 15 live exams with staggered starts_at
        created_exams = []
        for i in range(15):
            e = Exam.objects.create(
                institution=self.inst_a,
                title=f'Live Exam #{i+1:02d}',
                created_by=self.fac_user_a,
                department='Computer Science',
                duration_minutes=60,
                total_marks=100,
                starts_at=self.now - timedelta(minutes=15 - i),  # #15 started most recently (-0m), #01 started 15m ago
                ends_at=self.now + timedelta(minutes=45 + i),
                status=Exam.Status.PUBLISHED,
            )
            created_exams.append(e)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        res = self.client.get('/api/admin/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data.get('data', res.data)

        ongoing = data.get('ongoing_exams', [])
        # Strictly limited to 6
        self.assertEqual(len(ongoing), 6)
        self.assertEqual(data.get('live_total'), 15)
        self.assertEqual(data.get('shown_count'), 6)
        self.assertTrue(data.get('has_more'))

        # Check ordering: most recently started first (#15, #14, #13, #12, #11, #10)
        expected_titles = [f'Live Exam #{i:02d}' for i in range(15, 9, -1)]
        actual_titles = [item['title'] for item in ongoing]
        self.assertEqual(actual_titles, expected_titles)

        # live_summary must reflect all 15 live exams
        summary = data.get('live_summary', {})
        self.assertEqual(summary.get('live_exams_count'), 15)
        self.assertEqual(summary.get('total_eligible_unique'), 3)

    def test_11_dashboard_exact_counts_and_boundaries(self):
        """Test 11: Boundaries: 6 exams (has_more=False), 3 exams (has_more=False),
        0 exams (has_more=False), 7 exams (has_more=True)."""
        Exam.objects.filter(institution=self.inst_a).delete()
        cache.clear()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        # Case 0 exams
        res0 = self.client.get('/api/admin/dashboard/')
        data0 = res0.data.get('data', res0.data)
        self.assertEqual(len(data0.get('ongoing_exams', [])), 0)
        self.assertEqual(data0.get('live_total'), 0)
        self.assertEqual(data0.get('shown_count'), 0)
        self.assertFalse(data0.get('has_more'))

        # Case 3 exams
        cache.clear()
        for i in range(3):
            Exam.objects.create(
                institution=self.inst_a,
                title=f'Exam 3-{i}',
                created_by=self.fac_user_a,
                department='Computer Science',
                duration_minutes=60,
                total_marks=50,
                starts_at=self.now - timedelta(minutes=5),
                ends_at=self.now + timedelta(minutes=55),
                status=Exam.Status.PUBLISHED,
            )
        res3 = self.client.get('/api/admin/dashboard/')
        data3 = res3.data.get('data', res3.data)
        self.assertEqual(len(data3.get('ongoing_exams', [])), 3)
        self.assertEqual(data3.get('live_total'), 3)
        self.assertEqual(data3.get('shown_count'), 3)
        self.assertFalse(data3.get('has_more'))

        # Case 6 exams
        cache.clear()
        for i in range(3, 6):
            Exam.objects.create(
                institution=self.inst_a,
                title=f'Exam 6-{i}',
                created_by=self.fac_user_a,
                department='Computer Science',
                duration_minutes=60,
                total_marks=50,
                starts_at=self.now - timedelta(minutes=5),
                ends_at=self.now + timedelta(minutes=55),
                status=Exam.Status.PUBLISHED,
            )
        res6 = self.client.get('/api/admin/dashboard/')
        data6 = res6.data.get('data', res6.data)
        self.assertEqual(len(data6.get('ongoing_exams', [])), 6)
        self.assertEqual(data6.get('live_total'), 6)
        self.assertEqual(data6.get('shown_count'), 6)
        self.assertFalse(data6.get('has_more'))

        # Case 7 exams
        cache.clear()
        Exam.objects.create(
            institution=self.inst_a,
            title='Exam 7th',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=60,
            total_marks=50,
            starts_at=self.now - timedelta(minutes=1),
            ends_at=self.now + timedelta(minutes=59),
            status=Exam.Status.PUBLISHED,
        )
        res7 = self.client.get('/api/admin/dashboard/')
        data7 = res7.data.get('data', res7.data)
        self.assertEqual(len(data7.get('ongoing_exams', [])), 6)
        self.assertEqual(data7.get('live_total'), 7)
        self.assertEqual(data7.get('shown_count'), 6)
        self.assertTrue(data7.get('has_more'))

    def test_12_admin_exams_manager_live_status_filter_sync(self):
        """Test 12: Admin Exams Manager endpoint (/api/admin/exams/?status=live) returns
        all live exams for the institution, strictly tenant-isolated, matching live_total."""
        Exam.objects.filter(institution=self.inst_a).delete()
        cache.clear()

        # Create 8 live exams in Inst A
        for i in range(8):
            Exam.objects.create(
                institution=self.inst_a,
                title=f'Live A #{i}',
                created_by=self.fac_user_a,
                department='Computer Science',
                duration_minutes=60,
                total_marks=100,
                starts_at=self.now - timedelta(minutes=10),
                ends_at=self.now + timedelta(minutes=50),
                status=Exam.Status.PUBLISHED,
            )
        # Create 1 draft exam and 1 past exam in Inst A
        Exam.objects.create(
            institution=self.inst_a,
            title='Draft Exam A',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=60,
            total_marks=100,
            starts_at=self.now - timedelta(minutes=10),
            ends_at=self.now + timedelta(minutes=50),
            status=Exam.Status.DRAFT,
        )
        Exam.objects.create(
            institution=self.inst_a,
            title='Past Exam A',
            created_by=self.fac_user_a,
            department='Computer Science',
            duration_minutes=60,
            total_marks=100,
            starts_at=self.now - timedelta(hours=5),
            ends_at=self.now - timedelta(hours=4),
            status=Exam.Status.PUBLISHED,
        )
        # Create 1 live exam in Inst B (should NEVER appear for Admin A)
        Exam.objects.create(
            institution=self.inst_b,
            title='Live Exam B',
            created_by=self.fac_user_b,
            department='Computer Science',
            duration_minutes=60,
            total_marks=100,
            starts_at=self.now - timedelta(minutes=10),
            ends_at=self.now + timedelta(minutes=50),
            status=Exam.Status.PUBLISHED,
        )

        # 1. Dashboard reports live_total = 8
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        res_dash = self.client.get('/api/admin/dashboard/')
        data_dash = res_dash.data.get('data', res_dash.data)
        self.assertEqual(data_dash.get('live_total'), 8)
        self.assertEqual(data_dash.get('shown_count'), 6)
        self.assertTrue(data_dash.get('has_more'))

        # 2. Exam Manager with ?status=live returns all 8
        res_mgr = self.client.get('/api/admin/exams/?status=live&page_size=20')
        self.assertEqual(res_mgr.status_code, status.HTTP_200_OK)
        mgr_data = res_mgr.data
        self.assertEqual(mgr_data['pagination']['total_count'], 8)
        self.assertEqual(len(mgr_data['data']), 8)
        # Verify all 8 are live Inst A exams
        for item in mgr_data['data']:
            self.assertTrue(item['title'].startswith('Live A #'))
            self.assertEqual(item['department'], 'Computer Science')

        # Admin B querying ?status=live gets strictly Inst B live exams (1 exam)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_b}')
        res_mgr_b = self.client.get('/api/admin/exams/?status=live')
        self.assertEqual(res_mgr_b.status_code, status.HTTP_200_OK)
        self.assertEqual(res_mgr_b.data['pagination']['total_count'], 1)
        self.assertEqual(res_mgr_b.data['data'][0]['title'], 'Live Exam B')

    def test_13_cache_invalidation_on_attempt_lifecycle(self):
        """Test 13: Tenant cache is invalidated immediately when student attempt is saved."""
        cache.clear()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        # 1. First fetch populates cache
        res1 = self.client.get('/api/admin/dashboard/')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        summary1 = res1.data.get('data', res1.data).get('live_summary', {})
        self.assertEqual(summary1.get('total_submitted'), 0)
        self.assertEqual(summary1.get('total_in_progress'), 0)

        # 2. Student starts attempt -> bump_tenant_cache_version
        att = StudentAttempt.objects.create(
            exam=self.live_exam_a,
            institution=self.inst_a,
            student=self.stu_a1,
            status=StudentAttempt.Status.IN_PROGRESS,
            started_at=self.now,
        )

        # 3. Next fetch reflects the new in_progress count
        res2 = self.client.get('/api/admin/dashboard/')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        summary2 = res2.data.get('data', res2.data).get('live_summary', {})
        self.assertEqual(summary2.get('total_in_progress'), 1)

        # 4. Student submits attempt -> bump_tenant_cache_version
        att.status = StudentAttempt.Status.SUBMITTED
        att.submitted_at = timezone.now()
        att.total_score = 90
        att.save()

        # 5. Next fetch reflects the new submitted count
        res3 = self.client.get('/api/admin/dashboard/')
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        summary3 = res3.data.get('data', res3.data).get('live_summary', {})
        self.assertEqual(summary3.get('total_submitted'), 1)
        self.assertEqual(summary3.get('total_in_progress'), 0)

