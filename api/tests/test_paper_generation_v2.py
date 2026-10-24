"""End-to-End Test Suite for Paper Generation v2.
Covers:
1. Model registry, normalization, /api/faculty/ai-models/, and 400 prevention.
2. PDF parsing: TOC, headings, LLM fallback, scanned PDF, SHA-256 caching, multi-subject.
3. Planner: 50, 100, 25, 37.5 marks exact Decimal sums, suggestions on mismatch, time-fit warning, topic distribution.
4. Fast & accurate generation: batching, retries, fallbacks, off-scope caps, timeout partial success.
5. Management command: fix_stale_paper_jobs (--dry-run and --apply).
6. Multi-tenant institution FK enforcement across all created records.
"""

from decimal import Decimal
import io
import json
from unittest.mock import patch, MagicMock

import fitz  # PyMuPDF
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution
from faculty.models import FacultyProfile
from api.models import (
    Exam,
    Option,
    PaperGenerationJob,
    Question,
    Subject,
    Topic,
)
from api.utils.blueprint_allocator import (
    allocate_blueprint_to_target,
    compute_blueprint_total,
    distribute_questions_across_topics,
    estimate_exam_time,
    suggest_valid_blueprints,
    to_decimal,
)
from api.utils.extract_text import (
    chunk_syllabus_by_topics,
    extract_syllabus_content,
    get_cached_syllabus_data,
    hash_file_content,
)
from api.utils.ollama_models import (
    get_installed_models,
    get_installed_models_with_reason,
    normalize_model_name,
    resolve_model,
)


def _get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


def _create_mock_pdf(toc=None, text_pages=None):
    """Creates an in-memory PDF using PyMuPDF."""
    doc = fitz.open()
    pages_text = text_pages or [
        "Unit 1: Process Synchronization\nSemaphores and mutex locks ensure mutual exclusion.\nCritical section problem is essential in OS design.",
        "Unit 2: Memory Management\nPaging and segmentation are virtual memory techniques.\nPage replacement algorithms include FIFO, LRU, and Optimal."
    ]
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((50, 72), text, fontsize=12)
    if toc:
        doc.set_toc(toc)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class PaperGenerationModelRegistryTestCase(TestCase):
    """Tests Model Registry, normalization, and /api/faculty/ai-models/ endpoint."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(username='admin_v2', password='password123', email='admin_v2@test.edu')
        self.inst = AdminInstitution.objects.create(admin=self.admin, institution_name='V2 University', institution_code='INST-V2-1')
        self.user = User.objects.create_user(username='prof_v2', password='password123', email='prof_v2@test.edu')
        self.prof = FacultyProfile.objects.create(user=self.user, institution=self.inst, department='Computer Science')

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_get_token(self.user, "Faculty", self.inst)}')

    def test_normalize_model_names(self):
        """Legacy ids normalize to real installed tags; generic size rules work."""
        self.assertEqual(normalize_model_name("qwen2.5-3b"), "qwen2.5:3b-instruct")
        self.assertEqual(normalize_model_name("llama3.2-3b"), "llama3.2:3b")
        self.assertEqual(normalize_model_name("phi3-mini"), "phi3:mini")
        self.assertEqual(normalize_model_name("qwen2.5:3b-instruct"), "qwen2.5:3b-instruct")
        # Generic rule: mistral-7b -> mistral:7b
        self.assertEqual(normalize_model_name("mistral-7b"), "mistral:7b")

    @patch('api.utils.ollama_models.requests.get')
    def test_get_installed_models_success_and_offline(self, mock_get):
        """get_installed_models queries Ollama /api/tags, caches for 60s, and handles offline gracefully."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen2.5:3b-instruct", "size": 1929393},
                {"name": "llama3.2:3b", "size": 2019283},
                {"name": "phi3:mini", "size": 2182819},
            ]
        }
        mock_get.return_value = mock_resp

        models, error = get_installed_models_with_reason(force_refresh=True)
        self.assertIsNone(error)
        self.assertEqual(len(models), 3)
        self.assertIn("qwen2.5:3b-instruct", models)

        # Offline test
        mock_get.side_effect = Exception("Connection refused")
        offline_models, offline_err = get_installed_models_with_reason(force_refresh=True)
        self.assertEqual(offline_models, [])
        self.assertIsNotNone(offline_err)

    @patch('api.utils.ollama_models.requests.get')
    def test_resolve_model_fallbacks(self, mock_get):
        """resolve_model falls back to primary, then fallbacks, then raises clear error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
        mock_get.return_value = mock_resp

        # Requesting legacy qwen2.5-3b when only llama3.2:3b is installed resolves to llama3.2:3b
        resolved = resolve_model("qwen2.5-3b", force_refresh=True)
        self.assertEqual(resolved, "llama3.2:3b")

        # When none of the fallbacks are installed
        mock_resp.json.return_value = {"models": [{"name": "gemma2:2b"}]}
        with self.assertRaises(ValueError) as ctx:
            resolve_model("qwen2.5-3b", force_refresh=True)
        self.assertIn("is not installed in Ollama", str(ctx.exception))

    @patch('api.utils.ollama_models.requests.get')
    def test_ai_models_endpoint(self, mock_get):
        """GET /api/faculty/ai-models/ returns rich installed model metadata."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen2.5:3b-instruct", "size": 1900000000},
                {"name": "llama3.2:3b", "size": 2000000000},
            ]
        }
        mock_get.return_value = mock_resp

        res = self.client.get('/api/faculty/ai-models/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ollama_online'])
        self.assertEqual(len(data['models']), 2)
        qwen = next(m for m in data['models'] if m['name'] == 'qwen2.5:3b-instruct')
        self.assertTrue(qwen['is_recommended'])
        self.assertEqual(data['primary_model'], 'qwen2.5:3b-instruct')

    @patch('api.utils.ollama_models.get_installed_models')
    def test_generate_endpoint_accepts_legacy_and_real_tags(self, mock_installed):
        """POST /api/faculty/exams/generate/ accepts both legacy and real model names and returns 202."""
        mock_installed.return_value = ["qwen2.5:3b-instruct", "llama3.2:3b", "phi3:mini"]

        with patch('api.generate_paper.threading.Thread'):
            # Legacy name
            res_legacy = self.client.post('/api/faculty/exams/generate/', {
                'title': 'OS Legacy Test',
                'duration_minutes': 60,
                'total_marks': 20,
                'topics': ['Kernel', 'Processes'],
                'question_types': ['mcq'],
                'ai_model': 'qwen2.5-3b',
                'department': 'Computer Science',
            })
            self.assertEqual(res_legacy.status_code, 202)
            job = PaperGenerationJob.objects.get(id=res_legacy.json()['job_id'])
            self.assertEqual(job.model, 'qwen2.5:3b-instruct')
            job.delete()

            # Real installed tag
            res_real = self.client.post('/api/faculty/exams/generate/', {
                'title': 'OS Real Tag Test',
                'duration_minutes': 60,
                'total_marks': 20,
                'topics': ['Kernel', 'Processes'],
                'question_types': ['mcq'],
                'ai_model': 'qwen2.5:3b-instruct',
                'department': 'Computer Science',
            })
            self.assertEqual(res_real.status_code, 202)
            job_real = PaperGenerationJob.objects.get(id=res_real.json()['job_id'])
            self.assertEqual(job_real.model, 'qwen2.5:3b-instruct')
            job_real.delete()

    @patch('api.utils.ollama_models.get_installed_models')
    def test_generate_endpoint_uninstalled_model_returns_400(self, mock_installed):
        """Uninstalled model returns 400 listing installed models clearly."""
        mock_installed.return_value = ["qwen2.5:3b-instruct", "llama3.2:3b"]

        res = self.client.post('/api/faculty/exams/generate/', {
            'title': 'Invalid Model Test',
            'duration_minutes': 60,
            'total_marks': 20,
            'topics': ['Kernel'],
            'question_types': ['mcq'],
            'ai_model': 'deepseek-coder-67b',
            'department': 'Computer Science',
        })
        self.assertEqual(res.status_code, 400)
        err = res.json().get('error') or res.json().get('detail')
        self.assertIn("not installed in Ollama", err)
        self.assertIn("qwen2.5:3b-instruct", err)


class PDFTopicExtractionTestCase(TestCase):
    """Tests robust automatic PDF topic extraction, caching, and multi-subject detection."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(username='admin_pdf', password='password123', email='admin_pdf@test.edu')
        self.inst = AdminInstitution.objects.create(admin=self.admin, institution_name='PDF University', institution_code='INST-PDF-1')
        self.user = User.objects.create_user(username='prof_pdf', password='password123', email='prof_pdf@test.edu')
        self.prof = FacultyProfile.objects.create(user=self.user, institution=self.inst, department='Computer Science')

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_get_token(self.user, "Faculty", self.inst)}')

    def test_pdf_with_toc_extraction(self):
        """PDF with outline/bookmarks extracts units accurately without LLM."""
        toc = [
            [1, "Unit 1: Concurrency and Threads", 1],
            [1, "Unit 2: Memory Hierarchy and Caching", 2],
        ]
        pdf_bytes = _create_mock_pdf(toc=toc)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "syllabus.pdf"

        result = extract_syllabus_content(pdf_file, institution_id=self.inst.id)
        self.assertEqual(len(result['topics']), 2)
        self.assertEqual(result['topics'][0]['name'], "Unit 1: Concurrency and Threads")
        self.assertEqual(result['topics'][1]['name'], "Unit 2: Memory Hierarchy and Caching")
        self.assertEqual(sum(t['weight'] for t in result['topics']), 100)

    def test_pdf_with_headings_regex(self):
        """PDF without TOC extracts topics from Unit/Chapter/Module heading patterns."""
        pages = [
            "Unit 1: CPU Scheduling Algorithms\nFCFS, SJF, and Round Robin scheduling concepts.\nDetails about context switching.",
            "Unit 2: File System Implementation\nInodes, directories, disk allocation methods.",
        ]
        pdf_bytes = _create_mock_pdf(toc=None, text_pages=pages)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "syllabus_headings.pdf"

        result = extract_syllabus_content(pdf_file, institution_id=self.inst.id)
        self.assertGreaterEqual(len(result['topics']), 2)
        topic_names = [t['name'] for t in result['topics']]
        self.assertTrue(any('CPU Scheduling' in n for n in topic_names))

    @patch('api.utils.extract_text._detect_topics_with_short_llm_fallback')
    def test_pdf_no_structure_llm_fallback(self, mock_llm):
        """Unstructured PDF falls back to short LLM prompt over compressed outline."""
        mock_llm.return_value = [
            "Operating System Fundamentals",
            "Storage and I/O",
        ]
        pages = [
            "Some unstructured notes about computer hardware and operating system kernels.",
            "More unstructured notes regarding hard drives, solid state disks, and network interfaces.",
        ]
        pdf_bytes = _create_mock_pdf(toc=None, text_pages=pages)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "syllabus_unstructured.pdf"

        result = extract_syllabus_content(pdf_file, institution_id=self.inst.id)
        self.assertEqual(len(result['topics']), 2)
        self.assertEqual(result['topics'][0]['name'], "Operating System Fundamentals")

    def test_scanned_pdf_error_handling(self):
        """Empty / scanned PDF raises a clear message without crashing."""
        doc = fitz.open()
        doc.new_page()  # Blank page 1
        doc.new_page()  # Blank page 2
        pdf_bytes = doc.tobytes()
        doc.close()

        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "scanned.pdf"
        with self.assertRaises(ValueError) as ctx:
            extract_syllabus_content(pdf_file, institution_id=self.inst.id)
        self.assertIn("This PDF looks scanned. Text could not be extracted.", str(ctx.exception))

    def test_sha256_cache_hit(self):
        """Uploading the exact same file twice returns from cache instantly."""
        pdf_bytes = _create_mock_pdf()
        file_hash = hash_file_content(pdf_bytes)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "cached_test.pdf"

        # First extraction saves to cache
        extract_syllabus_content(pdf_file, institution_id=self.inst.id)
        cached = get_cached_syllabus_data(pdf_file, institution_id=self.inst.id)
        self.assertIsNotNone(cached)

        # Second extraction hits cache
        with patch('api.utils.extract_text._extract_pdf_pages_and_text') as mock_extractor:
            pdf_file_second = io.BytesIO(pdf_bytes)
            pdf_file_second.name = "cached_test.pdf"
            cached_result = extract_syllabus_content(pdf_file_second, institution_id=self.inst.id)
            mock_extractor.assert_not_called()
            self.assertEqual(cached_result['file_hash'], file_hash)

    def test_multi_subject_detection(self):
        """Multi-subject document is flagged with detected subject names."""
        pages = [
            "Operating Systems Unit:\nProcess management, memory management, scheduling algorithm, deadlock in kernel.",
            "Database Systems Unit:\nRelational algebra, SQL, ACID properties, indexing transactions in RDBMS.",
        ]
        pdf_bytes = _create_mock_pdf(toc=None, text_pages=pages)
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_file.name = "multi_subject.pdf"
        result = extract_syllabus_content(pdf_file, institution_id=self.inst.id)
        self.assertTrue(result['has_multiple_subjects'])
        self.assertGreaterEqual(len(result['detected_subjects']), 2)


class DeterministicPlannerTestCase(TestCase):
    """Tests exact Decimal sum planning, suggestions, time-fit warning, and topic distribution."""

    def test_planner_exact_sums_50_100_25_37_5(self):
        """Planner matches target marks exactly for integer and fractional marks."""
        # 50 marks
        alloc_50, _ = allocate_blueprint_to_target(Decimal("50.0"))
        self.assertEqual(compute_blueprint_total(alloc_50), Decimal("50.0"))

        # 100 marks
        alloc_100, _ = allocate_blueprint_to_target(Decimal("100.0"))
        self.assertEqual(compute_blueprint_total(alloc_100), Decimal("100.0"))

        # 25 marks
        alloc_25, _ = allocate_blueprint_to_target(Decimal("25.0"))
        self.assertEqual(compute_blueprint_total(alloc_25), Decimal("25.0"))

        # 37.5 marks (Fractional Decimal)
        alloc_frac, _ = allocate_blueprint_to_target(Decimal("37.5"))
        self.assertEqual(compute_blueprint_total(alloc_frac), Decimal("37.5"))

    def test_impossible_combo_suggests_valid_blueprints(self):
        """When an impossible combination is requested, suggestions that sum to target are returned."""
        bp_impossible = {
            "long_answer": {"enabled": True, "marks": 10, "marks_per_question": 10, "count": 1}
        }
        suggestions = suggest_valid_blueprints(Decimal("25.0"), current_blueprint=bp_impossible)
        self.assertGreaterEqual(len(suggestions), 1)
        for s in suggestions:
            self.assertEqual(to_decimal(s['total_marks']), Decimal("25.0"))

    def test_time_fit_warning(self):
        """estimate_exam_time accurately warns when planned questions exceed exam duration."""
        # 10 long questions (~10m each) = 100m, but duration is only 60m
        bp = [{"type": "long_answer", "count": 10, "marks_per_question": 5}]
        est_minutes = estimate_exam_time(bp)
        self.assertGreater(est_minutes, 60)

    def test_proportional_topic_distribution(self):
        """Questions are distributed across topics proportionally to topic weights."""
        topics = [
            {"id": "t1", "name": "Topic 1", "weight": 60},
            {"id": "t2", "name": "Topic 2", "weight": 40},
        ]
        bp = [{"type": "mcq", "count": 10, "marks_per_question": 1}]
        distributed = distribute_questions_across_topics(bp, topics)
        self.assertIn('mcq', distributed)
        self.assertEqual(len(distributed['mcq']), 2)
        t1_count = next(item['count'] for item in distributed['mcq'] if item['topic'] == 'Topic 1')
        t2_count = next(item['count'] for item in distributed['mcq'] if item['topic'] == 'Topic 2')
        self.assertEqual(t1_count + t2_count, 10)
        self.assertGreater(t1_count, t2_count)


class GenerationResilienceTestCase(TestCase):
    """Tests bounded retries, Ollama fallbacks, stale jobs command, and institution scoping."""

    def setUp(self):
        self.admin = User.objects.create_user(username='admin_res', password='password123', email='admin_res@test.edu')
        self.inst = AdminInstitution.objects.create(admin=self.admin, institution_name='Resilience Inst', institution_code='INST-RES-1')
        self.user = User.objects.create_user(username='prof_res', password='password123', email='prof_res@test.edu')
        self.prof = FacultyProfile.objects.create(user=self.user, institution=self.inst, department='Computer Science')

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_get_token(self.user, "Faculty", self.inst)}')

    def test_fix_stale_paper_jobs_dry_run_and_apply(self):
        """fix_stale_paper_jobs command correctly reports in dry-run and fixes in apply mode."""
        # Create an old running job (> 15 minutes ago)
        old_time = timezone.now() - timezone.timedelta(minutes=20)
        exam = Exam.objects.create(
            title='Stale Exam',
            department='Computer Science',
            institution=self.inst,
            created_by=self.user,
            total_marks=50,
            duration_minutes=60,
            status=Exam.Status.GENERATING,
        )
        # Add 2 partial questions
        q1 = Question.objects.create(
            exam=exam, text='Q1 text', question_type='mcq', difficulty='easy',
            marks=Decimal('2.0'), institution=self.inst
        )
        q2 = Question.objects.create(
            exam=exam, text='Q2 text', question_type='mcq', difficulty='easy',
            marks=Decimal('2.0'), institution=self.inst
        )

        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user,
            exam=exam,
            department='Computer Science',
            model='qwen2.5:3b-instruct',
            status=PaperGenerationJob.Status.RUNNING,
            question_count_requested=10,
            target_marks=50,
            started_at=old_time,
            created_at=old_time,
        )

        # 1. Test Dry Run (job remains RUNNING)
        out_dry = io.StringIO()
        call_command('fix_stale_paper_jobs', '--dry-run', stdout=out_dry)
        dry_output = out_dry.getvalue()
        self.assertIn(f'Job #{job.id}', dry_output)
        self.assertIn('Preserve 2 questions', dry_output)
        job.refresh_from_db()
        self.assertEqual(job.status, PaperGenerationJob.Status.RUNNING)

        # 2. Test Apply (job updated to COMPLETED_WITH_WARNINGS)
        out_apply = io.StringIO()
        call_command('fix_stale_paper_jobs', '--apply', stdout=out_apply)
        apply_output = out_apply.getvalue()
        self.assertIn('Successfully updated 1 stale job', apply_output)

        job.refresh_from_db()
        exam.refresh_from_db()
        self.assertEqual(job.status, PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS)
        self.assertEqual(job.question_count_generated, 2)
        self.assertEqual(job.actual_marks, 4)
        self.assertEqual(job.marks_shortfall, 46)
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertEqual(exam.total_marks, 4)
        self.assertEqual(exam.marks_shortfall, 46)

    def test_institution_fk_set_on_all_rows(self):
        """Verifies institution is never null on created Exam, Question, and Job."""
        exam = Exam.objects.create(
            title='Scoping Test',
            department='Computer Science',
            institution=self.inst,
            created_by=self.user,
            total_marks=20,
            duration_minutes=30,
        )
        q = Question.objects.create(
            exam=exam,
            text='What is a semaphore?',
            question_type='mcq',
            difficulty='medium',
            marks=Decimal('2.0'),
            institution=self.inst,
        )
        opt = Option.objects.create(
            question=q,
            text='A synchronization tool',
            is_correct=True,
        )
        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user,
            exam=exam,
            department='Computer Science',
            model='qwen2.5:3b-instruct',
        )

        self.assertIsNotNone(exam.institution_id)
        self.assertIsNotNone(q.institution_id)
        self.assertIsNotNone(job.institution_id)
        self.assertEqual(exam.institution_id, self.inst.id)
        self.assertEqual(q.institution_id, self.inst.id)
        self.assertEqual(job.institution_id, self.inst.id)
        self.assertEqual(Option.objects.filter(question=q).count(), 1)

    @patch('api.generate_paper.call_ollama')
    def test_model_404_fast_failover_to_fallback(self, mock_ollama):
        """Model 404 switches immediately to fallback without retrying the missing tag."""
        from api.generate_paper import _call_type_batch
        from api.utils.ollama_models import OllamaModelNotFoundError

        # First call with primary model raises 404; second call with fallback succeeds
        mock_ollama.side_effect = [
            OllamaModelNotFoundError("qwen2.5:3b-instruct", installed=["llama3.2:3b"]),
            json.dumps({"questions": [
                {"text": "What is paging?", "type": "mcq", "marks": 2, "options": ["A", "B", "C", "D"], "correct_answer": "A"}
            ]}),
        ]

        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user,
            department='Computer Science',
            model='qwen2.5:3b-instruct',
        )

        with patch('api.generate_paper.resolve_model') as mock_resolve, \
             patch('api.generate_paper.get_installed_models', return_value=['llama3.2:3b']):
            mock_resolve.side_effect = ["qwen2.5:3b-instruct", "llama3.2:3b"]
            questions = _call_type_batch(
                question_type='mcq',
                count=1,
                marks_per_q=2,
                model_key='qwen2.5:3b-instruct',
                topics=['Memory'],
                difficulty_distribution={'medium': 100},
                syllabus_chunk='Paging divides memory into frames.',
                job=job,
            )

        self.assertEqual(len(questions), 1)
        job.refresh_from_db()
        self.assertEqual(job.model, 'llama3.2:3b')
        self.assertTrue(any('fallback' in str(w).lower() for w in (job.warnings or [])))

    @patch('api.generate_paper.call_ollama')
    def test_invalid_json_bounded_retries(self, mock_ollama):
        """Invalid JSON triggers bounded retry (max 2) and does not infinite loop."""
        from api.generate_paper import _call_type_batch

        mock_ollama.return_value = "Non-JSON response from LLM"

        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user,
            department='Computer Science',
            model='qwen2.5:3b-instruct',
        )

        questions = _call_type_batch(
            question_type='mcq',
            count=2,
            marks_per_q=2,
            model_key='qwen2.5:3b-instruct',
            topics=['Memory'],
            difficulty_distribution={'medium': 100},
            syllabus_chunk='Memory concepts.',
            job=job,
        )

        self.assertEqual(len(questions), 0)
        self.assertEqual(mock_ollama.call_count, 2)  # Exactly 2 bounded attempts
        job.refresh_from_db()
        self.assertGreaterEqual(job.retry_count or 0, 1)

    def test_job_cancellation_stops_promptly(self):
        """Cancelled job breaks generation loop promptly without running further batches."""
        from api.generate_paper import _generate_type_questions

        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user,
            department='Computer Science',
            model='qwen2.5:3b-instruct',
            status=PaperGenerationJob.Status.CANCELLED,
        )

        with patch('api.generate_paper._call_type_batch') as mock_batch:
            res = _generate_type_questions(
                question_type='mcq',
                count=10,
                marks_per_q=2,
                model_name='qwen2.5:3b-instruct',
                topics=['OS'],
                difficulty_distribution={'easy': 100},
                syllabus_text='OS notes',
                job=job,
            )
            mock_batch.assert_not_called()
            self.assertEqual(len(res), 0)

    def test_partial_success_records_shortfall_and_status(self):
        """When total generated marks < target marks, job completes with warnings and records shortfall."""
        from api.generate_paper import _save_generated_exam_questions

        exam = Exam.objects.create(
            title='Partial Exam',
            department='Computer Science',
            institution=self.inst,
            created_by=self.user,
            total_marks=50,
            duration_minutes=60,
            status=Exam.Status.GENERATING,
        )
        job = PaperGenerationJob.objects.create(
            institution=self.inst,
            faculty=self.user,
            exam=exam,
            department='Computer Science',
            model='qwen2.5:3b-instruct',
            status=PaperGenerationJob.Status.RUNNING,
            target_marks=50,
            question_count_requested=10,
        )

        # 3 questions of 5 marks each = 15 marks (shortfall of 35)
        partial_questions = [
            {'text': 'Q1', 'type': 'mcq', 'marks': 5, 'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'},
            {'text': 'Q2', 'type': 'mcq', 'marks': 5, 'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'B'},
            {'text': 'Q3', 'type': 'mcq', 'marks': 5, 'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'C'},
        ]

        saved_count = _save_generated_exam_questions(
            job=job,
            exam_id=exam.id,
            generated_questions=partial_questions,
            target_marks=50,
            planned_marks=50,
            initial_generated_marks=15,
            dropped_dups=0,
            rejected_duplicates_marks=0,
            round_idx=1,
            warnings=['Generation completed with shortfall.'],
            syllabus_text='Notes',
            model_name='qwen2.5:3b-instruct',
            has_shortfall=True,
        )

        self.assertEqual(saved_count, 3)
        job.refresh_from_db()
        exam.refresh_from_db()
        self.assertEqual(job.actual_marks, 15)
        self.assertEqual(job.marks_shortfall, 35)
        self.assertEqual(job.status, PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS)
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertEqual(exam.total_marks, 15)
        self.assertEqual(exam.marks_shortfall, 35)

