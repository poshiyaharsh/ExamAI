"""Automated Unit Tests for Admin Faculty DRF Pagination & RBAC.

Validates:
1. Default pagination returns 10 items per page with complete pagination metadata.
2. Custom allowed page sizes (10, 25, 50, 100) are respected.
3. Invalid or out-of-range page_size falls back safely to 10.
4. Out-of-range page numbers clamp gracefully without 404 or 500 errors.
5. Multi-tenant isolation: Admin only sees faculty in their own institution.
6. Department filtering and search combine correctly with pagination.
7. Role-based access control: Student and Faculty receive HTTP 403; unauthenticated receives HTTP 401.
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
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


class AdminFacultyPaginationTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Institution A
        self.admin_user_a = User.objects.create_user(
            username='admin_a@alpha.edu', email='admin_a@alpha.edu', password='Password123!',
            first_name='Admin', last_name='Alpha'
        )
        AdminProfile.objects.create(user=self.admin_user_a)
        self.inst_a = AdminInstitution.objects.create(
            admin=self.admin_user_a,
            institution_name="Alpha University",
            status="active"
        )
        self.token_admin_a = _create_token(self.admin_user_a, 'admin', self.inst_a)

        # Institution B
        self.admin_user_b = User.objects.create_user(
            username='admin_b@beta.edu', email='admin_b@beta.edu', password='Password123!',
            first_name='Admin', last_name='Beta'
        )
        AdminProfile.objects.create(user=self.admin_user_b)
        self.inst_b = AdminInstitution.objects.create(
            admin=self.admin_user_b,
            institution_name="Beta Institute",
            status="active"
        )
        self.token_admin_b = _create_token(self.admin_user_b, 'admin', self.inst_b)

        # Create 25 faculty members for Institution A
        self.faculty_members_a = []
        for i in range(1, 26):
            dept = "Computer Science" if i <= 15 else "Mechanical Engineering"
            u = User.objects.create_user(
                username=f'faculty_a_{i:02d}@alpha.edu',
                email=f'faculty_a_{i:02d}@alpha.edu',
                password='Password123!',
                first_name=f'FacultyA{i:02d}',
                last_name='Professor'
            )
            fp = FacultyProfile.objects.create(
                user=u,
                institution=self.inst_a,
                employee_id=f'EMP-A-{i:03d}',
                department=dept,
                designation='Assistant Professor'
            )
            self.faculty_members_a.append(fp)

        # Create 5 faculty members for Institution B
        self.faculty_members_b = []
        for i in range(1, 6):
            u = User.objects.create_user(
                username=f'faculty_b_{i:02d}@beta.edu',
                email=f'faculty_b_{i:02d}@beta.edu',
                password='Password123!',
                first_name=f'FacultyB{i:02d}',
                last_name='Lecturer'
            )
            fp = FacultyProfile.objects.create(
                user=u,
                institution=self.inst_b,
                employee_id=f'EMP-B-{i:03d}',
                department='Civil Engineering',
                designation='Lecturer'
            )
            self.faculty_members_b.append(fp)

        # Faculty user for RBAC test
        self.faculty_user = self.faculty_members_a[0].user
        self.token_faculty = _create_token(self.faculty_user, 'faculty', self.inst_a)

        # Student user for RBAC test
        self.student_user = User.objects.create_user(
            username='student@alpha.edu', email='student@alpha.edu', password='Password123!',
            first_name='Student', last_name='Alpha'
        )
        StudentProfile.objects.create(
            user=self.student_user, institution=self.inst_a, student_id='STU-001', department='Computer Science'
        )
        self.token_student = _create_token(self.student_user, 'student', self.inst_a)

    def test_default_pagination(self):
        """Default request without page params should return 10 items on page 1 with metadata."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        response = self.client.get('/api/admin/faculty/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data = response.json()

        self.assertEqual(res_data['status'], 'success')
        self.assertEqual(res_data['count'], 25)
        self.assertEqual(res_data['total_count'], 25)
        self.assertEqual(res_data['page'], 1)
        self.assertEqual(res_data['page_size'], 10)
        self.assertEqual(res_data['total_pages'], 3)
        self.assertTrue(res_data['has_next'])
        self.assertFalse(res_data['has_prev'])
        self.assertEqual(len(res_data['results']), 10)
        self.assertEqual(len(res_data['data']), 10)

        # Check pagination dict compatibility
        pag = res_data['pagination']
        self.assertEqual(pag['page'], 1)
        self.assertEqual(pag['page_size'], 10)
        self.assertEqual(pag['total_count'], 25)
        self.assertEqual(pag['total_pages'], 3)

    def test_custom_page_size_and_navigation(self):
        """Requesting page_size=25 should return all 25 items on page 1 with total_pages=1."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        response = self.client.get('/api/admin/faculty/?page=1&page_size=25')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data = response.json()
        self.assertEqual(res_data['page_size'], 25)
        self.assertEqual(len(res_data['results']), 25)
        self.assertEqual(res_data['total_pages'], 1)
        self.assertFalse(res_data['has_next'])
        self.assertFalse(res_data['has_prev'])

    def test_page_two_and_last_page(self):
        """Requesting page 2 and page 3 with page_size=10 should return correct slices."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        # Page 2
        r2 = self.client.get('/api/admin/faculty/?page=2&page_size=10')
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        d2 = r2.json()
        self.assertEqual(d2['page'], 2)
        self.assertEqual(len(d2['results']), 10)
        self.assertTrue(d2['has_next'])
        self.assertTrue(d2['has_prev'])

        # Page 3 (last page with remaining 5 items)
        r3 = self.client.get('/api/admin/faculty/?page=3&page_size=10')
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        d3 = r3.json()
        self.assertEqual(d3['page'], 3)
        self.assertEqual(len(d3['results']), 5)
        self.assertFalse(d3['has_next'])
        self.assertTrue(d3['has_prev'])

        # Ensure no overlap between page 1, 2, and 3
        r1 = self.client.get('/api/admin/faculty/?page=1&page_size=10')
        ids_p1 = {item['id'] for item in r1.json()['results']}
        ids_p2 = {item['id'] for item in d2['results']}
        ids_p3 = {item['id'] for item in d3['results']}
        self.assertTrue(ids_p1.isdisjoint(ids_p2))
        self.assertTrue(ids_p2.isdisjoint(ids_p3))
        self.assertEqual(len(ids_p1 | ids_p2 | ids_p3), 25)

    def test_invalid_page_size_fallback(self):
        """Invalid page_size values should safely fall back to default of 10."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        for invalid_size in ['999', '-10', '0', 'not_a_number', '15']:
            resp = self.client.get(f'/api/admin/faculty/?page_size={invalid_size}')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertEqual(resp.json()['page_size'], 10)

    def test_out_of_bounds_page_clamping(self):
        """Page out of bounds should clamp gracefully to 1 or total_pages without 500 error."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        # Page 9999 should clamp to page 3 (total_pages)
        resp_high = self.client.get('/api/admin/faculty/?page=9999&page_size=10')
        self.assertEqual(resp_high.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_high.json()['page'], 3)

        # Page -5 should clamp to page 1
        resp_low = self.client.get('/api/admin/faculty/?page=-5&page_size=10')
        self.assertEqual(resp_low.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_low.json()['page'], 1)

    def test_multi_tenant_isolation(self):
        """Admin A should only see Admin A faculty (25), Admin B should only see Admin B faculty (5)."""
        # Admin A
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')
        res_a = self.client.get('/api/admin/faculty/').json()
        self.assertEqual(res_a['count'], 25)
        for f in res_a['results']:
            self.assertTrue(f['email'].startswith('faculty_a_'))

        # Admin B
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_b}')
        res_b = self.client.get('/api/admin/faculty/').json()
        self.assertEqual(res_b['count'], 5)
        for f in res_b['results']:
            self.assertTrue(f['email'].startswith('faculty_b_'))

    def test_filter_and_search_with_pagination(self):
        """Filtering by department should paginate only within the filtered subset."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_admin_a}')

        # 15 Computer Science faculty -> page 1 should have 10, total_pages 2
        resp = self.client.get('/api/admin/faculty/?department=Computer Science&page=1&page_size=10')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data['count'], 15)
        self.assertEqual(data['total_pages'], 2)
        self.assertEqual(len(data['results']), 10)

        # Search for specific faculty
        resp_search = self.client.get('/api/admin/faculty/?search=FacultyA05')
        self.assertEqual(resp_search.status_code, status.HTTP_200_OK)
        search_data = resp_search.json()
        self.assertEqual(search_data['count'], 1)
        self.assertEqual(search_data['results'][0]['email'], 'faculty_a_05@alpha.edu')

    def test_rbac_security(self):
        """Faculty and Student must be denied with 403 Forbidden; unauthenticated with 401."""
        # Unauthenticated
        self.client.credentials()
        resp_anon = self.client.get('/api/admin/faculty/')
        self.assertEqual(resp_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # Faculty
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_faculty}')
        resp_fac = self.client.get('/api/admin/faculty/')
        self.assertEqual(resp_fac.status_code, status.HTTP_403_FORBIDDEN)

        # Student
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_student}')
        resp_stu = self.client.get('/api/admin/faculty/')
        self.assertEqual(resp_stu.status_code, status.HTTP_403_FORBIDDEN)
