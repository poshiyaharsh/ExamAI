"""Comprehensive automated test suite for Faculty Paper Generation.
Tests deduplication engine, validation pipeline, cache performance,
pool exhaustion (422), multi-tenant isolation, variant shuffling, and exam immutability.
"""

from decimal import Decimal
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from api.models import (
    Exam,
    Option,
    Question,
    Subject,
    Topic,
)
from api.paper_engine.dedupe import CandidateQuestion, DeduplicationIndex
from api.paper_engine.validator import validate_single_candidate, validate_paper_plan
from api.paper_engine.cache import PaperCacheService


def _create_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class PaperGenerationDedupeUnitTestCase(TestCase):
    def setUp(self):
        self.index = DeduplicationIndex()

    def test_exact_id_duplicate(self):
        cand1 = CandidateQuestion(
            id=1, text="What is Python?", question_type="MCQ_SINGLE", difficulty="EASY",
            marks=1.0, subject_id=1, topic="Python Basics", options=["A language", "A snake"]
        )
        self.index.add(cand1)
        dup, reason = self.index.is_duplicate(cand1)
        self.assertTrue(dup)
        self.assertIn("Identical question ID", reason)

    def test_exact_normalized_text_duplicate(self):
        cand1 = CandidateQuestion(
            id=1, text="What is Python?", question_type="MCQ_SINGLE", difficulty="EASY",
            marks=1.0, subject_id=1, topic="Python Basics", options=["A", "B"]
        )
        cand2 = CandidateQuestion(
            id=2, text="what  is   python?  ", question_type="MCQ_SINGLE", difficulty="EASY",
            marks=1.0, subject_id=1, topic="Python Basics", options=["A", "B"]
        )
        self.index.add(cand1)
        dup, reason = self.index.is_duplicate(cand2)
        self.assertTrue(dup)
        self.assertIn("Identical question text hash", reason)

    def test_shingle_near_duplicate(self):
        cand1 = CandidateQuestion(
            id=1, text="Which of the following is a primary key constraint in relational database management systems?",
            question_type="MCQ_SINGLE", difficulty="MEDIUM", marks=1.0, subject_id=1, topic="Databases",
            options=["UNIQUE", "PRIMARY KEY"]
        )
        cand2 = CandidateQuestion(
            id=2, text="Which of the following is a primary key constraint in relational database management system?",
            question_type="MCQ_SINGLE", difficulty="MEDIUM", marks=1.0, subject_id=1, topic="Databases",
            options=["UNIQUE", "PRIMARY KEY"]
        )
        self.index.add(cand1)
        dup, reason = self.index.is_duplicate(cand2)
        self.assertTrue(dup)
        self.assertIn("Near-duplicate text", reason)

    def test_token_jaccard_duplicate(self):
        cand1 = CandidateQuestion(
            id=1, text="Explain why recursion requires a base case in quicksort algorithm",
            question_type="SHORT_ANSWER", difficulty="HARD", marks=5.0, subject_id=1, topic="Algorithms",
            options=[]
        )
        cand2 = CandidateQuestion(
            id=2, text="In quicksort algorithm explain why recursion requires a base case",
            question_type="SHORT_ANSWER", difficulty="HARD", marks=5.0, subject_id=1, topic="Algorithms",
            options=[]
        )
        self.index.add(cand1)
        dup, reason = self.index.is_duplicate(cand2)
        self.assertTrue(dup)
        self.assertIn("Near-duplicate", reason)

    def test_concept_and_options_match(self):
        cand1 = CandidateQuestion(
            id=1, text="Which protocol is used for secure browsing over the internet?",
            question_type="MCQ_SINGLE", difficulty="EASY", marks=1.0, subject_id=1, topic="Networking",
            options=["HTTP", "HTTPS", "FTP", "SSH"]
        )
        cand2 = CandidateQuestion(
            id=2, text="Identify the secure web protocol from the list below:",
            question_type="MCQ_SINGLE", difficulty="EASY", marks=1.0, subject_id=1, topic="Networking",
            options=["https", "http", "ftp", "ssh"]
        )
        self.index.add(cand1)
        dup, reason = self.index.is_duplicate(cand2)
        self.assertTrue(dup)
        self.assertIn("Same-concept duplicate", reason)

    def test_intra_question_duplicate_options(self):
        cand = CandidateQuestion(
            id=1, text="What is 2+2?", question_type="MCQ_SINGLE", difficulty="EASY",
            marks=1.0, subject_id=1, topic="Math",
            options=["4", "Four", "4", "5"]
        )
        dup, reason = self.index.is_duplicate(cand)
        self.assertTrue(dup)
        self.assertIn("duplicate option", reason)


class PaperGenerationIntegrationTestCase(TestCase):
    def setUp(self):
        PaperCacheService.clear_all()
        self.client = APIClient()

        # Institute A
        self.admin_user_a = User.objects.create_user(
            username='admin_a@gls.edu', email='admin_a@gls.edu', password='Password123!',
            first_name='Admin', last_name='A'
        )
        AdminProfile.objects.create(user=self.admin_user_a)
        self.inst_a = AdminInstitution.objects.create(
            admin=self.admin_user_a,
            institution_name='GLS University',
            institution_code='INST-A',
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
            employee_id='FAC-A-01',
        )

        # Institute B
        self.admin_user_b = User.objects.create_user(
            username='admin_b@zenith.edu', email='admin_b@zenith.edu', password='Password123!',
            first_name='Admin', last_name='B'
        )
        AdminProfile.objects.create(user=self.admin_user_b)
        self.inst_b = AdminInstitution.objects.create(
            admin=self.admin_user_b,
            institution_name='Zenith University',
            institution_code='INST-B',
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.fac_user_b = User.objects.create_user(
            username='faculty_b@zenith.edu', email='faculty_b@zenith.edu', password='Password123!',
            first_name='Faculty', last_name='B'
        )
        self.fac_profile_b = FacultyProfile.objects.create(
            user=self.fac_user_b,
            institution=self.inst_b,
            department='Information Technology',
            employee_id='FAC-B-01',
        )

        self.token_fac_a = _create_token(self.fac_user_a, 'faculty', self.inst_a)
        self.token_fac_b = _create_token(self.fac_user_b, 'faculty', self.inst_b)

        # Subjects
        self.subject_a = Subject.objects.create(
            institution=self.inst_a,
            department='Computer Science',
            name='Algorithms & Data Structures',
            code='CS201',
        )
        self.subject_b = Subject.objects.create(
            institution=self.inst_b,
            department='Information Technology',
            name='Web Engineering',
            code='IT201',
        )

        self.topic_a1 = Topic.objects.create(institution=self.inst_a, subject=self.subject_a, name='Binary Trees')
        self.topic_a2 = Topic.objects.create(institution=self.inst_a, subject=self.subject_a, name='Sorting Algorithms')

        # 20 diverse, realistic non-duplicate questions for inst_a
        question_data = [
            ("What is the time complexity of searching in a balanced binary search tree?", self.topic_a1, "EASY"),
            ("Which traversal of a binary search tree visits nodes in ascending sorted order?", self.topic_a1, "EASY"),
            ("What is the maximum number of nodes at level k of a binary tree?", self.topic_a1, "EASY"),
            ("In a complete binary tree with N nodes, what is the asymptotic height?", self.topic_a1, "EASY"),
            ("What is the primary condition for a binary tree to be considered a full binary tree?", self.topic_a1, "EASY"),
            ("Which sorting algorithm has worst case O(N^2) but runs in O(N) on sorted arrays?", self.topic_a2, "EASY"),
            ("What is the average time complexity of standard merge sort algorithm?", self.topic_a2, "EASY"),
            ("Which sorting technique is non-comparative and operates directly on digits?", self.topic_a2, "EASY"),
            ("What auxiliary space complexity is required by standard array-based merge sort?", self.topic_a2, "EASY"),
            ("Which element is commonly selected as the pivot in Lomuto partition scheme?", self.topic_a2, "EASY"),
            ("Explain the rotation required when an AVL tree becomes right-heavy after right insertion.", self.topic_a1, "MEDIUM"),
            ("How does a red-black tree maintain balance during consecutive node insertions?", self.topic_a1, "MEDIUM"),
            ("Under what specific conditions does quicksort degrade to quadratic runtime complexity?", self.topic_a2, "MEDIUM"),
            ("What makes heapsort an in-place comparison sort with guaranteed O(N log N) worst case?", self.topic_a2, "MEDIUM"),
            ("How does dual-pivot quicksort reduce memory cache misses during partitioning phases?", self.topic_a2, "MEDIUM"),
            ("Analyze the number of comparisons made by binary search in a sorted array of size 1024.", self.topic_a2, "MEDIUM"),
            ("Derive the asymptotic solution to the recurrence relation T(n) = 2T(n/2) + O(n log n).", self.topic_a1, "HARD"),
            ("Prove whether an optimal binary search tree can be constructed using dynamic programming.", self.topic_a1, "HARD"),
            ("Analyze the amortized runtime of splay tree operations across M consecutive accesses.", self.topic_a1, "HARD"),
            ("Evaluate why external sorting requires a multi-way merge phase for secondary storage blocks.", self.topic_a2, "HARD"),
        ]

        self.questions = []
        for idx, (q_text, top, diff) in enumerate(question_data, start=1):
            q = Question.objects.create(
                institution=self.inst_a,
                department='Computer Science',
                subject=self.subject_a,
                topic=top,
                topic_text=top.name,
                created_by=self.fac_user_a,
                text=q_text,
                question_type="MCQ_SINGLE",
                difficulty=diff,
                marks=Decimal("1.00"),
                status=Question.Status.ACTIVE,
            )
            Option.objects.create(question=q, text=f"Correct Option for Q{idx}", is_correct=True, order=1)
            Option.objects.create(question=q, text=f"Plausible Distractor 1 for Q{idx}", is_correct=False, order=2)
            Option.objects.create(question=q, text=f"Plausible Distractor 2 for Q{idx}", is_correct=False, order=3)
            Option.objects.create(question=q, text=f"Plausible Distractor 3 for Q{idx}", is_correct=False, order=4)
            self.questions.append(q)

    def test_fast_generation_and_validation(self):
        """Test paper generation creates non-duplicate exam with matching marks and valid report."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Midterm Examination",
            "subject": self.subject_a.id,
            "department": "Computer Science",
            "total_marks": 10,
            "duration_minutes": 60,
            "topics": ["Binary Trees", "Sorting Algorithms"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 50, "medium": 30, "hard": 20},
            "avoid_repeats": True,
            "seed": 42
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertFalse(data.get("loaded_from_cache", False))
        self.assertIn("exam", data)
        exam_id = data["exam"]["id"]

        exam = Exam.objects.get(id=exam_id)
        self.assertEqual(exam.institution, self.inst_a)
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertEqual(exam.total_marks, Decimal("10.00"))
        self.assertEqual(exam.questions.count(), 10)

        # Verify deduplication
        q_texts = [q.text for q in exam.questions.all()]
        self.assertEqual(len(q_texts), len(set(q_texts)))

        # Verify validation report
        self.assertIsNotNone(exam.validation_report)
        self.assertTrue(exam.validation_report["is_valid"])
        self.assertEqual(len(exam.validation_report["errors"]), 0)

    def test_cache_hit_returns_cached_exam(self):
        """Identical generation request should hit cache."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Midterm Examination Cached",
            "subject": self.subject_a.id,
            "department": "Computer Science",
            "total_marks": 10,
            "duration_minutes": 30,
            "topics": ["Binary Trees", "Sorting Algorithms"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 50, "medium": 30, "hard": 20},
            "seed": 777
        }
        # First request (miss)
        res1 = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertEqual(res1.status_code, 201)
        data1 = res1.json()
        self.assertFalse(data1.get("loaded_from_cache", False))

        # Second request (hit)
        res2 = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2.get("loaded_from_cache", True))
        self.assertEqual(data1["exam"]["id"], data2["exam"]["id"])

    def test_pool_exhausted_returns_422(self):
        """When question bank cannot satisfy criteria, returns 422 with no fallback padding."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Massive Exam Exceeding Pool",
            "subject": self.subject_a.id,
            "department": "Computer Science",
            "total_marks": 200,
            "duration_minutes": 180,
            "topics": ["Binary Trees"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 30, "medium": 50, "hard": 20}
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertEqual(res.status_code, 422)
        err = res.json().get("detail", "")
        self.assertIn("Question pool exhausted", err)
        self.assertFalse(Exam.objects.filter(title="Massive Exam Exceeding Pool").exists())

    def test_multi_tenant_isolation(self):
        """Faculty in Zenith cannot generate paper using GLS subject or questions."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_b}')
        payload = {
            "title": "Unauthorized Cross-Tenant Paper",
            "subject": self.subject_a.id,  # belongs to GLS
            "department": "Information Technology",
            "total_marks": 10,
            "duration_minutes": 30,
            "topics": ["Binary Trees"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 100, "medium": 0, "hard": 0}
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertIn(res.status_code, [400, 404, 422])

    def test_published_exam_immutability(self):
        """Published exam questions cannot be swapped or modified."""
        exam = Exam.objects.create(
            institution=self.inst_a,
            department='Computer Science',
            created_by=self.fac_user_a,
            title="Published Final Exam",
            total_marks=Decimal("2.00"),
            duration_minutes=30,
            status=Exam.Status.PUBLISHED,
            is_immutable=True
        )
        exam.questions.set([self.questions[0], self.questions[1]])

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        target_q_id = self.questions[0].id
        swap_res = self.client.post(
            f"/api/faculty/exams/{exam.id}/questions/{target_q_id}/swap/",
            format="json"
        )
        self.assertEqual(swap_res.status_code, 400)
        self.assertIn("immutable", swap_res.json().get("detail", "").lower())

    def test_swap_question_replaces_with_non_duplicate(self):
        """Draft exam single question swap picks a valid replacement from the pool."""
        exam = Exam.objects.create(
            institution=self.inst_a,
            department='Computer Science',
            created_by=self.fac_user_a,
            title="Draft Exam for Swapping",
            total_marks=Decimal("2.00"),
            duration_minutes=30,
            status=Exam.Status.DRAFT
        )
        exam.questions.set([self.questions[0], self.questions[1]])

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        old_q = self.questions[0]
        old_text = old_q.text
        swap_res = self.client.post(
            f"/api/faculty/exams/{exam.id}/questions/{old_q.id}/swap/",
            format="json"
        )
        self.assertEqual(swap_res.status_code, 200)
        data = swap_res.json()
        new_text = data["question"]["text"]
        self.assertNotEqual(old_text, new_text)

        old_q.refresh_from_db()
        self.assertEqual(old_q.text, new_text)

    def test_shuffle_exam_variants(self):
        """Shuffle endpoint produces a randomized permutation with seed support."""
        exam = Exam.objects.create(
            institution=self.inst_a,
            department='Computer Science',
            created_by=self.fac_user_a,
            title="Draft Exam for Shuffle",
            total_marks=Decimal("3.00"),
            duration_minutes=30,
            status=Exam.Status.DRAFT
        )
        exam.questions.set([self.questions[0], self.questions[1], self.questions[2]])

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        res = self.client.post(
            f"/api/faculty/exams/{exam.id}/shuffle/",
            {"seed": 12345},
            format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("questions", res.json())
        self.assertEqual(len(res.json()["questions"]), 3)

    def test_generate_with_unregistered_subject_string_does_not_crash(self):
        """Regression test for 500 error: subject='DS' (unregistered string) must not crash with ValueError."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Data Structures Midterm",
            "subject": "DS",
            "department": "Computer Science",
            "total_marks": 5,
            "duration_minutes": 45,
            "topics": ["Binary Trees", "Sorting Algorithms"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 60, "medium": 40, "hard": 0},
            "seed": 101,
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertNotEqual(res.status_code, 500, f"Server returned HTTP 500: {res.data}")
        self.assertIn(res.status_code, (200, 201))
        data = res.json()
        self.assertIn("exam", data)
        exam = Exam.objects.get(id=data["exam"]["id"])
        self.assertEqual(exam.subject, "DS")
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertEqual(exam.questions.count(), 5)

    def test_generate_with_subject_code_resolution(self):
        """Faculty providing subject='CS201' resolves to registered Subject ID and generates paper."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "CS201 Exam",
            "subject": "CS201",
            "department": "Computer Science",
            "total_marks": 5,
            "duration_minutes": 45,
            "topics": ["Binary Trees"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 100, "medium": 0, "hard": 0},
            "seed": 202,
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertIn(res.status_code, (200, 201))
        exam = Exam.objects.get(id=res.json()["exam"]["id"])
        self.assertEqual(exam.subject, self.subject_a.name)

    def test_generate_with_subject_name_resolution(self):
        """Faculty providing exact subject name resolves to registered Subject ID and generates paper."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Algorithms Exam",
            "subject": "Algorithms & Data Structures",
            "department": "Computer Science",
            "total_marks": 5,
            "duration_minutes": 45,
            "topics": ["Sorting Algorithms"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 100, "medium": 0, "hard": 0},
            "seed": 303,
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertIn(res.status_code, (200, 201))
        exam = Exam.objects.get(id=res.json()["exam"]["id"])
        self.assertEqual(exam.subject, self.subject_a.name)

    def test_generate_with_valid_numeric_subject_id(self):
        """Faculty providing subject_id=<int> generates paper properly."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Subject ID Exam",
            "subject_id": self.subject_a.id,
            "department": "Computer Science",
            "total_marks": 5,
            "duration_minutes": 45,
            "topics": ["Binary Trees"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 100, "medium": 0, "hard": 0},
            "seed": 404,
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertIn(res.status_code, (200, 201))
        exam = Exam.objects.get(id=res.json()["exam"]["id"])
        self.assertEqual(exam.subject, self.subject_a.name)

    def test_generate_with_invalid_subject_id_string_returns_400(self):
        """Faculty providing a non-numeric subject_id receives HTTP 400 with INVALID_SUBJECT_ID."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Invalid Subject ID Exam",
            "subject_id": "not-a-number",
            "department": "Computer Science",
            "total_marks": 5,
            "duration_minutes": 45,
            "topics": ["Binary Trees"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 100, "medium": 0, "hard": 0},
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "INVALID_SUBJECT_ID")

    def test_generate_with_cross_tenant_subject_id_returns_400(self):
        """Faculty from institution A cannot generate an exam using a subject_id belonging to institution B."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Cross-Tenant Exam",
            "subject_id": self.subject_b.id,
            "department": "Computer Science",
            "total_marks": 5,
            "duration_minutes": 45,
            "topics": ["Binary Trees"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 100, "medium": 0, "hard": 0},
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "SUBJECT_NOT_FOUND")

    def test_generate_with_cross_department_subject_id_returns_400(self):
        """Faculty cannot use a subject_id that belongs to another department."""
        ee_subject = Subject.objects.create(
            institution=self.inst_a,
            department="Electrical Engineering",
            name="Circuits & Systems",
            code="EE101",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token_fac_a}')
        payload = {
            "title": "Cross-Dept Exam",
            "subject_id": ee_subject.id,
            "department": "Computer Science",
            "total_marks": 5,
            "duration_minutes": 45,
            "topics": ["Binary Trees"],
            "question_types": ["MCQ_SINGLE"],
            "difficulty_distribution": {"easy": 100, "medium": 0, "hard": 0},
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("code"), "SUBJECT_DEPARTMENT_MISMATCH")


class PoolFetchDefensiveTestCase(TestCase):
    def test_pool_fetch_rejects_non_integer_subject_id(self):
        from api.paper_engine.pool import fetch_candidate_pool
        with self.assertRaises(ValueError) as ctx:
            fetch_candidate_pool(institution_id=1, subject_id="DS")
        self.assertIn("subject_id must be an integer", str(ctx.exception))

    def test_cache_hash_separates_subject_id_and_subject(self):
        from api.paper_engine.cache import compute_request_hash
        payload1 = {"title": "Exam", "total_marks": 10, "subject_id": 1}
        payload2 = {"title": "Exam", "total_marks": 10, "subject": "DS"}
        hash1 = compute_request_hash(payload1)
        hash2 = compute_request_hash(payload2)
        self.assertNotEqual(hash1, hash2)

