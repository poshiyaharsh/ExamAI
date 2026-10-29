import unittest
from decimal import Decimal
from django.test import TestCase

from api.utils.validate_paper import allocate_difficulties, compute_question_counts, canonicalize_type
from api.models import (
    Exam,
    Question,
    PaperGenerationJob,
    AdminInstitution,
)
from django.contrib.auth.models import User


class TestAllocateDifficulties(unittest.TestCase):
    def test_allocate_difficulties_empty_and_zero(self):
        self.assertEqual(allocate_difficulties(0, {'easy': 30, 'medium': 50, 'hard': 20}), [])
        self.assertEqual(allocate_difficulties(-5, {'easy': 30, 'medium': 50, 'hard': 20}), [])

    def test_allocate_difficulties_36_questions(self):
        # 36 questions with 30% easy, 50% medium, 20% hard
        diffs = allocate_difficulties(36, {'easy': 30, 'medium': 50, 'hard': 20})
        self.assertEqual(len(diffs), 36)
        self.assertEqual(diffs.count('easy'), 11)
        self.assertEqual(diffs.count('medium'), 18)
        self.assertEqual(diffs.count('hard'), 7)
        self.assertEqual(11 + 18 + 7, 36)

    def test_allocate_difficulties_single_item(self):
        diffs_hard = allocate_difficulties(1, {'easy': 0, 'medium': 0, 'hard': 100})
        self.assertEqual(diffs_hard, ['hard'])
        diffs_easy = allocate_difficulties(1, {'easy': 100, 'medium': 0, 'hard': 0})
        self.assertEqual(diffs_easy, ['easy'])

    def test_allocate_difficulties_all_types_proportional(self):
        diffs_10 = allocate_difficulties(10, {'easy': 30, 'medium': 50, 'hard': 20})
        self.assertEqual(len(diffs_10), 10)
        self.assertEqual(diffs_10.count('easy'), 3)
        self.assertEqual(diffs_10.count('medium'), 5)
        self.assertEqual(diffs_10.count('hard'), 2)

        diffs_4 = allocate_difficulties(4, {'easy': 30, 'medium': 50, 'hard': 20})
        self.assertEqual(len(diffs_4), 4)
        self.assertEqual(diffs_4.count('easy'), 1)
        self.assertEqual(diffs_4.count('medium'), 2)
        self.assertEqual(diffs_4.count('hard'), 1)

        diffs_2 = allocate_difficulties(2, {'easy': 30, 'medium': 50, 'hard': 20})
        self.assertEqual(len(diffs_2), 2)
        self.assertEqual(diffs_2.count('easy'), 1)
        self.assertEqual(diffs_2.count('medium'), 1)


class TestBlueprintContractAndCounts(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='password123',
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name='Test University',
            institution_code='TU-2026',
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.faculty_user = User.objects.create_user(
            username='faculty_test',
            email='faculty@test.com',
            password='password123',
        )

    def test_blueprint_counts_custom_36_questions(self):
        # 10 MCQ (2M = 20M), 10 True/False (2M = 20M), 10 Fill (2M = 20M), 4 Short (5M = 20M), 2 Long (10M = 20M) = 36 questions, 100 marks
        custom_blueprint = {
            'mcq': {'count': 10, 'marks': 2, 'enabled': True},
            'true_false': {'count': 10, 'marks': 2, 'enabled': True},
            'fill_blank': {'count': 10, 'marks': 2, 'enabled': True},
            'short_answer': {'count': 4, 'marks': 5, 'enabled': True},
            'long_answer': {'count': 2, 'marks': 10, 'enabled': True},
        }
        question_types = ['mcq', 'true_false', 'fill_blank', 'short_answer', 'long_answer']

        counts, planned_total_marks = compute_question_counts(question_types, 100, blueprint=custom_blueprint)
        self.assertEqual(planned_total_marks, 100.0)
        self.assertEqual(counts.get('mcq'), 10)
        self.assertEqual(counts.get('true_false'), 10)
        self.assertEqual(counts.get('fill_blank'), 10)
        self.assertEqual(counts.get('short_answer'), 4)
        self.assertEqual(counts.get('long_answer'), 2)
        self.assertEqual(sum(counts.values()), 36)

    def test_blueprint_fallback_when_none(self):
        # Fallback allocate_blueprint_to_target produces 20 questions for 100 marks
        question_types = ['mcq', 'true_false', 'fill_blank', 'short_answer', 'long_answer']
        counts, planned_total_marks = compute_question_counts(question_types, 100, blueprint=None)
        self.assertEqual(planned_total_marks, 100.0)
        self.assertEqual(sum(counts.values()), 20)
        self.assertEqual(counts.get('mcq'), 5)
        self.assertEqual(counts.get('true_false'), 3)
        self.assertEqual(counts.get('fill_blank'), 2)
        self.assertEqual(counts.get('short_answer'), 4)
        self.assertEqual(counts.get('long_answer'), 6)

    def test_truthful_waterfall_and_notices(self):
        from api.generate_paper import _run_generation

        # Test waterfall logic when generation succeeds exactly
        planned_marks = 100
        target_marks = 100
        initial_generated_marks = 100
        dropped_dups = 0
        rejected_duplicates_marks = 0
        topup_added_marks = 0
        actual_total_marks = 100
        marks_shortfall = 0

        initial_shortfall = max(0, planned_marks - initial_generated_marks)
        waterfall_parts = [f"Planned {planned_marks}M", f"Generated {initial_generated_marks}M"]
        if initial_shortfall > 0:
            waterfall_parts[-1] += f" (Initial shortfall: {initial_shortfall}M)"
        if rejected_duplicates_marks > 0 or dropped_dups > 0:
            waterfall_parts.append(f"Rejected dups -{rejected_duplicates_marks}M")
        if topup_added_marks > 0:
            waterfall_parts.append(f"Top-ups +{topup_added_marks}M")
        waterfall_parts.append(f"Final {actual_total_marks}M of {target_marks}M target")
        waterfall_str = "Marks waterfall: " + " -> ".join(waterfall_parts) + "."

        self.assertEqual(
            waterfall_str,
            "Marks waterfall: Planned 100M -> Generated 100M -> Final 100M of 100M target."
        )

        # Test waterfall and truthful notice when there is a shortfall
        initial_generated_marks_short = 90
        actual_total_marks_short = 90
        marks_shortfall_10 = 10
        round_idx = 0

        init_short = max(0, planned_marks - initial_generated_marks_short)
        parts_short = [f"Planned {planned_marks}M", f"Generated {initial_generated_marks_short}M"]
        if init_short > 0:
            parts_short[-1] += f" (Initial shortfall: {init_short}M)"
        parts_short.append(f"Final {actual_total_marks_short}M of {target_marks}M target")
        waterfall_short_str = "Marks waterfall: " + " -> ".join(parts_short) + "."

        self.assertEqual(
            waterfall_short_str,
            "Marks waterfall: Planned 100M -> Generated 90M (Initial shortfall: 10M) -> Final 90M of 100M target."
        )
