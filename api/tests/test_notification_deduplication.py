from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from api.models import (
    AdminInstitution,
    Exam,
    Notification,
    PaperGenerationJob,
)
from api.generate_paper import _save_generated_exam_questions


class TestNotificationDeduplication(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin_notif_test',
            email='admin_notif@test.com',
            password='password123',
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name='Notification Test University',
            institution_code='NTU-2026',
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.faculty_user = User.objects.create_user(
            username='faculty_notif_test',
            email='faculty_notif@test.com',
            password='password123',
        )
        self.exam = Exam.objects.create(
            title='Deduplication Test Exam',
            created_by=self.faculty_user,
            institution=self.institution,
            department='Computer Science',
            total_marks=50,
            duration_minutes=60,
            status=Exam.Status.GENERATING,
        )
        self.job = PaperGenerationJob.objects.create(
            institution=self.institution,
            faculty=self.faculty_user,
            department='Computer Science',
            exam=self.exam,
            model='qwen2.5:3b-instruct',
            status=PaperGenerationJob.Status.RUNNING,
            question_count_requested=10,
            target_marks=50,
        )

    def test_single_notification_created_on_save(self):
        # Initial questions
        questions = [
            {'type': 'mcq', 'text': f'Sample Question {i}', 'marks': 5.0, 'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
            for i in range(10)
        ]

        # Call save
        _save_generated_exam_questions(
            job=self.job,
            exam_id=self.exam.id,
            generated_questions=questions,
            target_marks=50,
            planned_marks=50,
            initial_generated_marks=50,
            dropped_dups=0,
            rejected_duplicates_marks=0,
            round_idx=0,
            warnings=[],
            syllabus_text='',
            model_name='qwen2.5:3b-instruct',
            has_shortfall=False,
        )

        notifs = Notification.objects.filter(user=self.faculty_user)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.title, 'Paper Ready')
        self.assertEqual(notif.type, Notification.NotificationType.SUCCESS)
        self.assertEqual(notif.link, f"/faculty/exams/{self.exam.id}/edit")

    def test_multiple_saves_coalesce_into_single_notification(self):
        questions = [
            {'type': 'mcq', 'text': f'Sample Question {i}', 'marks': 5.0, 'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
            for i in range(10)
        ]

        # First save
        _save_generated_exam_questions(
            job=self.job,
            exam_id=self.exam.id,
            generated_questions=questions,
            target_marks=50,
            planned_marks=50,
            initial_generated_marks=50,
            dropped_dups=0,
            rejected_duplicates_marks=0,
            round_idx=0,
            warnings=[],
            syllabus_text='',
            model_name='qwen2.5:3b-instruct',
            has_shortfall=False,
        )

        # Mark notification as read
        notif = Notification.objects.get(user=self.faculty_user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])

        # Second save (e.g., partial fallback or retry)
        _save_generated_exam_questions(
            job=self.job,
            exam_id=self.exam.id,
            generated_questions=questions,
            target_marks=50,
            planned_marks=50,
            initial_generated_marks=50,
            dropped_dups=0,
            rejected_duplicates_marks=0,
            round_idx=1,
            warnings=['Top-up completed'],
            syllabus_text='',
            model_name='qwen2.5:3b-instruct',
            has_shortfall=False,
        )

        # Exactly 1 notification should exist, not 2
        notifs = Notification.objects.filter(user=self.faculty_user)
        self.assertEqual(notifs.count(), 1)
        updated_notif = notifs.first()
        self.assertEqual(updated_notif.id, notif.id)
        # Should be unread again to notify of the update
        self.assertFalse(updated_notif.is_read)

    def test_failure_notification_deduplication(self):
        from api.generate_paper import _run_generation

        # Create failure notification
        fail_title = 'Paper Generation Failed'
        fail_msg = "Failed to generate paper: Model timed out."
        Notification.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            title=fail_title,
            message=fail_msg,
            type=Notification.NotificationType.ERROR,
            link='/faculty/generate',
        )

        # Another failure within 5 minutes
        recent_fail = Notification.objects.filter(
            user=self.faculty_user,
            title=fail_title,
            created_at__gte=timezone.now() - timedelta(minutes=5),
        ).first()
        self.assertIsNotNone(recent_fail)
        recent_fail.message = "Failed to generate paper: New error detail."
        recent_fail.is_read = False
        recent_fail.created_at = timezone.now()
        recent_fail.save(update_fields=['message', 'is_read', 'created_at'])

        # Total failures remains 1
        fails = Notification.objects.filter(user=self.faculty_user, title=fail_title)
        self.assertEqual(fails.count(), 1)
        self.assertEqual(fails.first().message, "Failed to generate paper: New error detail.")
