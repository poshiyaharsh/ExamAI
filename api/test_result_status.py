import unittest
from types import SimpleNamespace
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from api.utils.results import compute_attempt_result_status, ResultStatusCode


class TestAttemptResultStatus(TestCase):
    def test_not_attempted(self):
        exam = SimpleNamespace(total_marks=100)
        res = compute_attempt_result_status(attempt=None, exam=exam)
        self.assertEqual(res['status_code'], ResultStatusCode.NOT_ATTEMPTED)
        self.assertEqual(res['label'], 'Not attempted')
        self.assertIsNone(res['is_passed'])
        self.assertIsNone(res['marks_obtained'])
        self.assertIsNone(res['percentage'])
        self.assertEqual(res['badge_variant'], 'slate')

    def test_in_progress(self):
        attempt = SimpleNamespace(
            status='in_progress',
            submit_reason='',
            total_score=15.0,
            max_score=50.0,
            expires_at=timezone.now() + timedelta(minutes=30),
            violation_count=0,
        )
        res = compute_attempt_result_status(attempt=attempt)
        self.assertEqual(res['status_code'], ResultStatusCode.IN_PROGRESS)
        self.assertEqual(res['label'], 'In progress')
        self.assertIsNone(res['is_passed'])
        self.assertTrue(res['is_provisional'])
        self.assertEqual(res['percentage'], 30.0)

    def test_expired_in_progress(self):
        attempt = SimpleNamespace(
            status='in_progress',
            submit_reason='',
            total_score=10.0,
            max_score=50.0,
            expires_at=timezone.now() - timedelta(minutes=5),
            violation_count=0,
        )
        res = compute_attempt_result_status(attempt=attempt)
        self.assertEqual(res['status_code'], ResultStatusCode.EXPIRED)
        self.assertFalse(res['is_passed'])

    def test_pending_grading_submitted(self):
        attempt = SimpleNamespace(
            status='submitted',
            submit_reason='manual',
            total_score=25.0,
            max_score=100.0,
            violation_count=0,
        )
        res = compute_attempt_result_status(attempt=attempt, has_pending_subjectives=True)
        self.assertEqual(res['status_code'], ResultStatusCode.PENDING_GRADING)
        self.assertEqual(res['label'], 'Pending grading')
        self.assertTrue(res['is_provisional'])
        self.assertIsNone(res['is_passed'], "Pending grading must not show Pass or Fail")
        self.assertEqual(res['badge_variant'], 'amber')

    def test_auto_submitted_violations(self):
        attempt = SimpleNamespace(
            status='auto_submitted',
            submit_reason='violations',
            total_score=0.0,
            max_score=100.0,
            violation_count=4,
        )
        res = compute_attempt_result_status(attempt=attempt, has_pending_subjectives=False)
        self.assertEqual(res['status_code'], ResultStatusCode.AUTO_SUBMITTED)
        self.assertEqual(res['label'], 'Auto-submitted')
        self.assertIn('Rule violations', res['sub_label'])
        self.assertFalse(res['is_passed'])
        self.assertEqual(res['badge_variant'], 'rose')

    def test_auto_submitted_time_up_passed(self):
        attempt = SimpleNamespace(
            status='auto_submitted',
            submit_reason='time_up',
            total_score=60.0,
            max_score=100.0,
            violation_count=0,
        )
        res = compute_attempt_result_status(attempt=attempt, has_pending_subjectives=False)
        self.assertEqual(res['status_code'], ResultStatusCode.AUTO_SUBMITTED)
        self.assertTrue(res['is_passed'])
        self.assertEqual(res['badge_variant'], 'amber')

    def test_pass_and_fail_boundaries(self):
        # 40% passing threshold
        # Exactly 40.0 marks on 100 max = 40.0% -> PASS
        att_exact = SimpleNamespace(status='evaluated', submit_reason='manual', total_score=40.0, max_score=100.0, violation_count=0)
        res_exact = compute_attempt_result_status(attempt=att_exact, has_pending_subjectives=False)
        self.assertEqual(res_exact['status_code'], ResultStatusCode.PASS)
        self.assertTrue(res_exact['is_passed'])
        self.assertEqual(res_exact['badge_variant'], 'emerald')

        # 39.9 marks on 100 max = 39.9% -> FAIL
        att_under = SimpleNamespace(status='evaluated', submit_reason='manual', total_score=39.9, max_score=100.0, violation_count=0)
        res_under = compute_attempt_result_status(attempt=att_under, has_pending_subjectives=False)
        self.assertEqual(res_under['status_code'], ResultStatusCode.FAIL)
        self.assertFalse(res_under['is_passed'])
        self.assertEqual(res_under['badge_variant'], 'rose')

    def test_zero_total_marks_safe(self):
        attempt = SimpleNamespace(status='evaluated', submit_reason='manual', total_score=0.0, max_score=0.0, violation_count=0)
        res = compute_attempt_result_status(attempt=attempt, has_pending_subjectives=False)
        self.assertEqual(res['percentage'], 0.0)
        self.assertEqual(res['status_code'], ResultStatusCode.FAIL)
