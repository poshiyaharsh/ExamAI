from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from admins.models import AdminInstitution
from students.models import StudentProfile
from faculty.models import FacultyProfile
from api.models import Exam, Question, StudentAttempt, StudentAnswer
from api.utils.analytics import (
    CLASSIFICATION_CONFIG,
    MIN_COHORT_SIZE,
    classify_score,
    resolve_short_subject,
    is_attempt_fully_graded,
    compute_student_subjects_breakdown,
    compute_faculty_exam_performance_overview,
)


class AnalyticsCoreTests(TestCase):
    def test_classification_boundary_values(self):
        # Boundary at 75%
        strong_exact = classify_score(75.0)
        self.assertEqual(strong_exact['code'], 'strong')
        self.assertEqual(strong_exact['color'], '#10B981')

        just_under_strong = classify_score(74.9)
        self.assertEqual(just_under_strong['code'], 'average')
        self.assertEqual(just_under_strong['color'], '#3B82F6')

        # Boundary at 50%
        avg_exact = classify_score(50.0)
        self.assertEqual(avg_exact['code'], 'average')

        just_under_avg = classify_score(49.9)
        self.assertEqual(just_under_avg['code'], 'needs_focus')
        self.assertEqual(just_under_avg['color'], '#F59E0B')

        # Real 0% stays needs_focus
        zero_score = classify_score(0.0)
        self.assertEqual(zero_score['code'], 'needs_focus')

        # None is no_results
        none_score = classify_score(None)
        self.assertEqual(none_score['code'], 'no_results')
        self.assertEqual(none_score['color'], '#9CA3AF')

    def test_resolve_short_subject_fallbacks(self):
        class MockExam:
            def __init__(self, title='', subject='', department='', topics=None):
                self.title = title
                self.subject = subject
                self.department = department
                self.topics = topics or []

        # Clean subject field directly
        e1 = MockExam(subject="Operating Systems")
        self.assertEqual(resolve_short_subject(e1), "Operating Systems")

        # Comma separated topic string inside subject
        e2 = MockExam(subject="Data Structures, Algorithms, Complexity")
        self.assertEqual(resolve_short_subject(e2), "Data Structures")

        # Strip CH_ / Unit from title
        e3 = MockExam(title="Java Programming CH_1 Fundamentals")
        self.assertEqual(resolve_short_subject(e3), "Java Programming")

        e4 = MockExam(title="Data Warehouse Unit_1 Overview")
        self.assertEqual(resolve_short_subject(e4), "Data Warehouse")

        # Fallback to department when Exam_XX
        e5 = MockExam(title="Exam_08", department="Computer Science")
        self.assertEqual(resolve_short_subject(e5), "Computer Science")


class AnalyticsWorkflowTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_test@test.edu", email="admin_test@test.edu", password="password123"
        )
        self.inst = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Test Tech University",
            status="active",
        )
        self.faculty_user = User.objects.create_user(
            username="faculty_test@test.edu", email="faculty_test@test.edu", password="password123"
        )
        self.fac_prof = FacultyProfile.objects.create(
            user=self.faculty_user, institution=self.inst, department="Computer Science", employee_id="FAC001"
        )

        self.student_user = User.objects.create_user(
            username="student_test@test.edu", email="student_test@test.edu", password="password123"
        )
        self.stud_prof = StudentProfile.objects.create(
            user=self.student_user, institution=self.inst, department="Computer Science", student_id="STU001"
        )

    def test_analytics_grading_and_quarantine(self):
        # Exam 1: 100 marks, Student took it and scored real 0%
        exam1 = Exam.objects.create(
            institution=self.inst,
            created_by=self.faculty_user,
            title="Database Systems CH_1",
            subject="Database Systems",
            department="Computer Science",
            duration_minutes=60,
            total_marks=100,
            status=Exam.Status.PUBLISHED,
        )
        # Attempt 1: evaluated, score 0.0
        StudentAttempt.objects.create(
            exam=exam1,
            institution=self.inst,
            student=self.student_user,
            status=StudentAttempt.Status.EVALUATED,
            total_score=0.0,
            max_score=100.0,
        )

        # Exam 2: 50 marks, Student took it, status submitted (pending grading)
        exam2 = Exam.objects.create(
            institution=self.inst,
            created_by=self.faculty_user,
            title="Networks CH_2",
            subject="Networks",
            department="Computer Science",
            duration_minutes=60,
            total_marks=50,
            status=Exam.Status.PUBLISHED,
        )
        StudentAttempt.objects.create(
            exam=exam2,
            institution=self.inst,
            student=self.student_user,
            status=StudentAttempt.Status.SUBMITTED,
            total_score=20.0,
            max_score=50.0,
        )

        # Exam 3: 100 marks, Not attempted by student
        exam3 = Exam.objects.create(
            institution=self.inst,
            created_by=self.faculty_user,
            title="Software Engineering",
            subject="Software Engineering",
            department="Computer Science",
            duration_minutes=60,
            total_marks=100,
            status=Exam.Status.PUBLISHED,
        )

        # Compute Student Breakdown
        s_data = compute_student_subjects_breakdown(self.student_user, self.inst)

        # Graded subjects should only contain Database Systems
        active_subjs = {s['subject']: s for s in s_data['subjects']}
        self.assertIn("Database Systems", active_subjs)
        self.assertNotIn("Networks", active_subjs, "Networks is pending grading and must NOT be in active graded chart")

        db_subj = active_subjs["Database Systems"]
        self.assertEqual(db_subj['average_score'], 0.0, "Real 0% score must be preserved as 0.0%")
        self.assertEqual(db_subj['exams_counted'], 1)
        self.assertEqual(db_subj['classification']['code'], 'needs_focus')

        # Networks must be listed in unattempted_subjects with pending_grading status
        unatt = {u['subject']: u for u in s_data['unattempted_subjects']}
        self.assertIn("Networks", unatt)
        self.assertEqual(unatt["Networks"]['status'], 'pending_grading')

        self.assertEqual(s_data['total_pending_exams'], 1)
        self.assertIn("1 exam is pending grading", s_data['excluded_exams_note'])

        # Compute Faculty Exam Performance Overview
        f_data = compute_faculty_exam_performance_overview(self.faculty_user, self.inst, limit=8)
        exams_by_title = {e['exam_title']: e for e in f_data['exams']}

        # exam1 has results
        self.assertEqual(exams_by_title["Database Systems CH_1"]['status'], 'has_results')
        self.assertEqual(exams_by_title["Database Systems CH_1"]['average_score'], 0.0)

        # exam2 is pending grading
        self.assertEqual(exams_by_title["Networks CH_2"]['status'], 'pending_grading')
        self.assertIsNone(exams_by_title["Networks CH_2"]['average_score'], "Pending grading must return average: null")

        # exam3 has no submissions
        self.assertEqual(exams_by_title["Software Engineering"]['status'], 'no_submissions')
        self.assertIsNone(exams_by_title["Software Engineering"]['average_score'], "No submissions must return average: null")

        # Badge summary text
        self.assertEqual(f_data['summary']['with_results'], 1)
        self.assertEqual(f_data['summary']['badge_text'], "3 exams · 1 with results")

    def test_cohort_size_privacy_enforcement(self):
        # Create exam
        exam = Exam.objects.create(
            institution=self.inst,
            created_by=self.faculty_user,
            title="Cloud Architecture",
            subject="Cloud Architecture",
            department="Computer Science",
            duration_minutes=60,
            total_marks=100,
            status=Exam.Status.PUBLISHED,
        )

        # Create attempts for only 3 students (< MIN_COHORT_SIZE = 5)
        for i in range(3):
            u = User.objects.create_user(username=f"s_{i}@test.edu", email=f"s_{i}@test.edu", password="pass")
            StudentProfile.objects.create(user=u, institution=self.inst, department="Computer Science", student_id=f"ID_{i}")
            StudentAttempt.objects.create(
                exam=exam, institution=self.inst, student=u, status=StudentAttempt.Status.EVALUATED, total_score=80.0, max_score=100.0
            )

        # Student query
        res = compute_student_subjects_breakdown(self.student_user, self.inst)
        # For Cloud Architecture, cohort_average must be None to protect privacy
        for s in res['subjects']:
            if s['subject'] == "Cloud Architecture":
                self.assertIsNone(s['cohort_average'], "Cohort average must be suppressed when cohort size < 5")

    def test_divide_by_zero_safe(self):
        # Zero total marks exam
        zero_exam = Exam.objects.create(
            institution=self.inst,
            created_by=self.faculty_user,
            title="Zero Marks Exam",
            subject="Edge Cases",
            department="Computer Science",
            duration_minutes=30,
            total_marks=0,
            status=Exam.Status.PUBLISHED,
        )
        StudentAttempt.objects.create(
            exam=zero_exam,
            institution=self.inst,
            student=self.student_user,
            status=StudentAttempt.Status.EVALUATED,
            total_score=0.0,
            max_score=0.0,
        )
        # Must not raise ZeroDivisionError
        s_data = compute_student_subjects_breakdown(self.student_user, self.inst)
        edge_subjs = [s for s in s_data['subjects'] if s['subject'] == "Edge Cases"]
        self.assertEqual(len(edge_subjs), 1)
        self.assertEqual(edge_subjs[0]['average_score'], 0.0)

    def test_student_and_faculty_isolation(self):
        # Create second faculty and second student
        faculty_b = User.objects.create_user(username="fac_b@test.edu", email="fac_b@test.edu", password="pass")
        FacultyProfile.objects.create(user=faculty_b, institution=self.inst, department="Electrical", employee_id="FAC002")

        student_b = User.objects.create_user(username="stud_b@test.edu", email="stud_b@test.edu", password="pass")
        StudentProfile.objects.create(user=student_b, institution=self.inst, department="Electrical", student_id="STU002")

        exam_b = Exam.objects.create(
            institution=self.inst,
            created_by=faculty_b,
            title="Circuits 101",
            subject="Circuits",
            department="Electrical",
            duration_minutes=60,
            total_marks=100,
            status=Exam.Status.PUBLISHED,
        )
        StudentAttempt.objects.create(
            exam=exam_b, institution=self.inst, student=student_b, status=StudentAttempt.Status.EVALUATED, total_score=95.0, max_score=100.0
        )

        # Student A must not see Student B's Circuits subject
        s_a_data = compute_student_subjects_breakdown(self.student_user, self.inst)
        self.assertNotIn("Circuits", [s['subject'] for s in s_a_data['subjects']])

        # Faculty A must not see Faculty B's exam
        f_a_data = compute_faculty_exam_performance_overview(self.faculty_user, self.inst)
        self.assertNotIn("Circuits 101", [e['exam_title'] for e in f_a_data['exams']])
