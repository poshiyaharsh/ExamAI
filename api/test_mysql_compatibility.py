from django.test import TestCase
from django.db import connection, OperationalError
from api.models import Question, Exam, StudentAttempt, StudentAnswer, Option
from admins.models import AdminInstitution
from django.contrib.auth.models import User
from api.utils.db_retry import is_lock_or_deadlock, retry_on_deadlock

class MySQLCompatibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mysql_tester@example.com",
            password="testpassword123"
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.user,
            institution_name="MySQL Test Institute",
            institution_code="MYSQL_TEST",
            address="123 Database Way",
            phone="1234567890",
            status="active"
        )

    def test_utf8mb4_emoji_and_multilingual_roundtrip(self):
        """Verify 4-byte UTF-8 emojis, mathematical symbols, and multilingual text round-trip cleanly."""
        emoji_text = "What is the capital of 🇮🇳 India? 🚀 🎯 (Explain: ∑(x_i) ≥ 0 & こんにちは!)"
        question = Question.objects.create(
            institution=self.institution,
            created_by=self.user,
            text=emoji_text,
            question_type="MCQ",
            difficulty="medium",
            marks=2.5,
            status="approved"
        )
        
        # Create option with emoji
        opt = Option.objects.create(
            question=question,
            text="New Delhi 🏛️",
            is_correct=True,
            order=1
        )

        question.refresh_from_db()
        opt.refresh_from_db()

        self.assertEqual(question.text, emoji_text)
        self.assertEqual(opt.text, "New Delhi 🏛️")

    def test_deadlock_detection_helper(self):
        """Test is_lock_or_deadlock correctly identifies MySQL deadlock error 1213 and timeout 1205."""
        # Simulated MySQL OperationalError with error code 1213 (Deadlock found when trying to get lock)
        deadlock_err = OperationalError(1213, "Deadlock found when trying to get lock; try restarting transaction")
        self.assertTrue(is_lock_or_deadlock(deadlock_err))

        # Simulated MySQL OperationalError with error code 1205 (Lock wait timeout exceeded)
        lock_timeout_err = OperationalError(1205, "Lock wait timeout exceeded; try restarting transaction")
        self.assertTrue(is_lock_or_deadlock(lock_timeout_err))

        # Simulated other operational error (e.g. syntax error or unknown column)
        other_err = OperationalError(1054, "Unknown column 'foo' in 'field list'")
        self.assertFalse(is_lock_or_deadlock(other_err))

    def test_retry_on_deadlock_decorator(self):
        """Test retry_on_deadlock retries upon deadlock and succeeds."""
        call_count = 0

        @retry_on_deadlock(max_retries=3, base_delay=0.01)
        def flaky_transaction():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError(1213, "Deadlock found")
            return "SUCCESS"

        result = flaky_transaction()
        self.assertEqual(result, "SUCCESS")
        self.assertEqual(call_count, 3)

    def test_active_hash_and_null_uniqueness(self):
        """Verify active_hash uniqueness allows duplicate hashes when active_hash is None (soft deleted)."""
        import hashlib
        from api.models import Subject
        subject = Subject.objects.create(
            institution=self.institution,
            created_by=self.user,
            name="Database Systems",
            code="CS401",
            department="Computer Science"
        )
        text = "Sample Question for Hash"
        hash_val = hashlib.sha256(text.encode()).hexdigest()

        # Create active question with subject
        q1 = Question.objects.create(
            institution=self.institution,
            created_by=self.user,
            subject=subject,
            text=text,
            text_hash=hash_val,
            is_deleted=False,
            marks=1
        )
        self.assertEqual(q1.active_hash, hash_val)

        # Soft-delete q1
        q1.is_deleted = True
        q1.save()
        self.assertIsNone(q1.active_hash)

        # Now creating another active question with same text/hash should succeed because q1 has active_hash=None
        q2 = Question.objects.create(
            institution=self.institution,
            created_by=self.user,
            subject=subject,
            text=text,
            text_hash=hash_val,
            is_deleted=False,
            marks=1
        )
        self.assertEqual(q2.active_hash, hash_val)
