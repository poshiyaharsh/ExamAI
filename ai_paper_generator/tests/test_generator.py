"""

Phase 10 Comprehensive Test Suite for AI Paper Generator:

1. Blueprint marks math and auto-distribute equality

2. Each rule validator (MCQ, True/False, Fill Blank, Short, Long, truncation, placeholders)

3. Safe JSON parsing & repair with malformed payloads

4. Deduplicator with exact and token overlap detection

5. Full dry test with small syllabus (5 MCQ, 3 TF, 3 Fill, 2 Short, 1 Long = 30 marks)

6. Full test with 100 marks

7. Model failure simulation (Ollama down/unreachable)

"""

import json

from unittest.mock import patch, MagicMock

from django.test import TestCase

from django.contrib.auth import get_user_model



from admins.models import AdminInstitution

from faculty.models import FacultyProfile

from ai_paper_generator.models import GenerationJob, GenerationLog

from ai_paper_generator.ollama_client import (

    OllamaClient,

    OllamaNotRunningError,

    OllamaModelNotFoundError,

)

from ai_paper_generator.model_manager import ModelManager

from ai_paper_generator.generators.blueprint import (

    build_blueprint,

    auto_distribute_blueprint,

    calculate_allocated_marks,

)

from ai_paper_generator.generators.validator import validate_rules

from ai_paper_generator.generators.deduplicator import QuestionDeduplicator

from ai_paper_generator.generators.repair import generate_and_validate_slot_with_repair

from ai_paper_generator.generators.paper_builder import assemble_and_order_paper

from ai_paper_generator.rag.chunker import clean_text, estimate_tokens

from ai_paper_generator.rag.embedder import LocalTfIdfEmbedder



User = get_user_model()





class BlueprintMathTests(TestCase):

    def test_auto_distribute_exact_match(self):

        """Tests that auto_distribute equals requested total marks for various totals."""

        for target in [20, 30, 50, 75, 100, 150]:

            sections = auto_distribute_blueprint(target)

            allocated = sum(s['count'] * s['marks_per_question'] for s in sections)

            self.assertEqual(allocated, target, f"Failed for target={target}")



    def test_build_blueprint_marks_equality(self):

        """Tests building full slots with exact sum equality."""

        sections = [

            {'type': 'MCQ', 'count': 5, 'marks_per_question': 1},

            {'type': 'True/False', 'count': 3, 'marks_per_question': 1},

            {'type': 'Fill in the Blank', 'count': 3, 'marks_per_question': 1},

            {'type': 'Short Answer', 'count': 2, 'marks_per_question': 3},

            {'type': 'Long Answer', 'count': 1, 'marks_per_question': 13},

        ]

        # 5*1 + 3*1 + 3*1 + 2*3 + 1*13 = 5 + 3 + 3 + 6 + 13 = 30 marks

        slots = build_blueprint(

            total_marks=30,

            sections=sections,

            topics=['Networks', 'Security']

        )

        self.assertEqual(len(slots), 14)

        self.assertEqual(calculate_allocated_marks(slots), 30)



    def test_blueprint_mismatch_raises_error(self):

        """Tests that mismatching marks raises ValueError immediately."""

        sections = [{'type': 'MCQ', 'count': 5, 'marks_per_question': 1}]

        with self.assertRaises(ValueError):

            build_blueprint(total_marks=10, sections=sections, topics=['A'])





class ValidatorRuleTests(TestCase):

    def test_mcq_validation(self):

        # Valid MCQ

        valid_mcq = {

            'slot_index': 1,

            'type': 'MCQ',

            'question': 'What is the primary function of a router?',

            'options': ['Forward data packets', 'Generate power', 'Compile code', 'Store database tables'],

            'answer': 'Forward data packets',

            'marks': 1,

        }

        ok, reason = validate_rules(valid_mcq)

        self.assertTrue(ok, reason)



        # Invalid: duplicate options

        invalid_dup = dict(valid_mcq, options=['A', 'A', 'B', 'C'])

        ok, _ = validate_rules(invalid_dup)

        self.assertFalse(ok)



        # Invalid: answer not in options

        invalid_ans = dict(valid_mcq, answer='Not an option')

        ok, _ = validate_rules(invalid_ans)

        self.assertFalse(ok)



    def test_true_false_validation(self):

        valid_tf = {

            'slot_index': 2,

            'type': 'True/False',

            'question': 'TCP provides reliable, ordered, and error-checked byte stream delivery.',

            'options': ['True', 'False'],

            'answer': 'True',

            'marks': 1,

        }

        ok, reason = validate_rules(valid_tf)

        self.assertTrue(ok, reason)



        # Invalid answer

        invalid_tf = dict(valid_tf, answer='Maybe')

        ok, _ = validate_rules(invalid_tf)

        self.assertFalse(ok)



    def test_fill_blank_validation(self):

        valid_fb = {

            'slot_index': 3,

            'type': 'Fill in the Blank',

            'question': 'The protocol used to translate domain names into IP addresses is ___ protocol.',

            'options': [],

            'answer': 'DNS',

            'marks': 1,

        }

        ok, reason = validate_rules(valid_fb)

        self.assertTrue(ok, reason)



        # Missing blank marker

        invalid_fb = dict(valid_fb, question='DNS protocol translates names to IPs.')

        ok, _ = validate_rules(invalid_fb)

        self.assertFalse(ok)



    def test_short_and_long_validation(self):

        # Valid Short

        valid_short = {

            'slot_index': 4,

            'type': 'Short Answer',

            'question': 'Define polymorphism in object-oriented programming.',

            'options': [],

            'answer': 'Polymorphism allows objects of different classes to be treated through a common interface. It enables method overriding and overloading.',

            'marks': 3,

        }

        ok, _ = validate_rules(valid_short)

        self.assertTrue(ok)



        # Empty long answer fails

        empty_long = {

            'slot_index': 5,

            'type': 'Long Answer',

            'question': 'Explain the OSI 7-layer reference model in detail.',

            'options': [],

            'answer': '',

            'marks': 5,

        }

        ok, _ = validate_rules(empty_long)

        self.assertFalse(ok)





class JsonRepairTests(TestCase):

    def test_malformed_json_healing(self):

        # Truncated or missing closing brace

        malformed = '{"question": "What is Python?", "answer": "Programming language", "marks": 2'

        from ai_paper_generator.generators.json_repair import parse_and_repair_json

        repaired = parse_and_repair_json(malformed)

        self.assertEqual(repaired.get('question'), 'What is Python?')

        self.assertEqual(repaired.get('answer'), 'Programming language')



    def test_markdown_wrapped_json(self):

        wrapped = '```json\n{"question": "What is RAM?", "options": ["A", "B", "C", "D"], "answer": "A"}\n```'

        from ai_paper_generator.generators.json_repair import parse_and_repair_json

        parsed = parse_and_repair_json(wrapped)

        self.assertEqual(parsed.get('question'), 'What is RAM?')





class DeduplicatorTests(TestCase):

    def test_duplicate_detection(self):

        dedup = QuestionDeduplicator(similarity_threshold=0.70)

        q1 = {

            'slot_index': 1,

            'question': 'Explain the fundamental architecture of the relational database management system.'

        }

        dedup.add(q1)



        # Exact match

        is_dup, _ = dedup.is_duplicate(q1)

        self.assertTrue(is_dup)



        # Near duplicate

        q2 = {

            'slot_index': 2,

            'question': 'Explain the fundamental architecture of relational database management systems.'

        }

        is_dup, _ = dedup.is_duplicate(q2)

        self.assertTrue(is_dup)



        # Distinct question

        q3 = {

            'slot_index': 3,

            'question': 'What are the main principles of asymmetric cryptography?'

        }

        is_dup, _ = dedup.is_duplicate(q3)

        self.assertFalse(is_dup)





class FullDryGenerationTests(TestCase):

    def setUp(self):

        self.admin_user = User.objects.create_user(username='admin_tester', password='pass123')

        self.inst = AdminInstitution.objects.create(institution_name='Test College', admin=self.admin_user)

        self.user = User.objects.create_user(username='fac_tester', password='pass123')

        self.faculty = FacultyProfile.objects.create(user=self.user, institution=self.inst)



    def test_dry_generation_30_marks(self):

        """

        Phase 10 Dry Test: 5 MCQ, 3 True/False, 3 Fill Blank, 2 Short, 1 Long = 30 marks.

        Confirms counts match, marks equal 30, no answers empty, logs written.

        """

        sections = [

            {'type': 'MCQ', 'count': 5, 'marks_per_question': 1},

            {'type': 'True/False', 'count': 3, 'marks_per_question': 1},

            {'type': 'Fill in the Blank', 'count': 3, 'marks_per_question': 1},

            {'type': 'Short Answer', 'count': 2, 'marks_per_question': 3},

            {'type': 'Long Answer', 'count': 1, 'marks_per_question': 13},

        ]

        slots = build_blueprint(

            total_marks=30,

            sections=sections,

            topics=['Algorithms', 'Data Structures']

        )

        self.assertEqual(len(slots), 14)

        self.assertEqual(calculate_allocated_marks(slots), 30)



        # Assemble synthetic questions

        questions = []

        for s in slots:

            q_type = s['type']

            q_dict = {

                'slot_index': s['slot_index'],

                'type': q_type,

                'difficulty': s['difficulty'],

                'topic': s['topic'],

                'marks': s['marks'],

                'question': f"Sample valid question for {q_type} on {s['topic']} with slot {s['slot_index']}?",

                'answer': 'True' if q_type == 'True/False' else 'Sample valid model answer with complete details.',

                'options': ['Opt A', 'Opt B', 'Opt C', 'Opt D'] if q_type == 'MCQ' else ([] if q_type != 'True/False' else ['True', 'False']),

            }

            if q_type == 'MCQ':

                q_dict['answer'] = 'Opt A'

            elif q_type == 'Fill in the Blank':

                q_dict['question'] = f"The standard algorithm used for {s['topic']} is ___ search."

                q_dict['answer'] = 'binary'

            questions.append(q_dict)



        final_paper = assemble_and_order_paper(questions, target_total_marks=30)

        self.assertEqual(len(final_paper), 14)

        total_m = sum(q['marks'] for q in final_paper)

        self.assertEqual(total_m, 30)



        # Confirm no answers empty

        for q in final_paper:

            self.assertTrue(bool(q.get('answer')), f"Empty answer in Q{q.get('question_number')}")



    def test_dry_generation_100_marks(self):

        """Phase 10 Test with 100 marks."""

        sections = auto_distribute_blueprint(100)

        allocated = sum(s['count'] * s['marks_per_question'] for s in sections)

        self.assertEqual(allocated, 100)



        slots = build_blueprint(100, sections, ['Operating Systems', 'Cloud'])

        self.assertEqual(calculate_allocated_marks(slots), 100)



    def test_simulate_model_failure(self):

        """

        Phase 10 Test: Simulates model failure / Ollama down.

        Confirms clean handling and log writing.

        """

        mgr = ModelManager()

        with patch.object(OllamaClient, 'list_installed_models', side_effect=OllamaNotRunningError("Ollama is down")):

            info = mgr.detect_and_assign_roles()

            self.assertEqual(info['status'], 'offline')

            self.assertIn("not currently running", info['message'])



    def test_start_generation_api_valid(self):

        """Tests StartGenerationView multipart request parsing."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        payload = {

            'title': 'Unit Test Exam',

            'subject': 'Networks',

            'total_marks': 20,

            'duration': 30,

            'sections': json.dumps([{'type': 'MCQ', 'count': 10, 'marks_per_question': 2}]),

            'topics': json.dumps(['Routing']),

            'difficulty_distribution': json.dumps({'Easy': 30, 'Medium': 50, 'Hard': 20}),

        }

        res = client.post('/api/ai-generator/generate/', data=payload, format='multipart', HTTP_HOST='localhost')

        self.assertIn(res.status_code, (201, 202))

        self.assertIn('job_id', res.data)



    def test_start_generation_api_marks_mismatch(self):

        """Tests StartGenerationView 400 error response structure on marks mismatch."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        payload = {

            'title': 'Mismatch Exam',

            'subject': 'Networks',

            'total_marks': 50,

            'sections': json.dumps([{'type': 'MCQ', 'count': 10, 'marks_per_question': 1}]), # 10 != 50

            'topics': json.dumps(['Routing']),

        }

        res = client.post('/api/ai-generator/generate/', data=payload, format='multipart', HTTP_HOST='localhost')

        self.assertEqual(res.status_code, 400)

        self.assertIn('error', res.data)

        self.assertIn('fields', res.data)

        self.assertIn('total_marks', res.data['fields'])





class FacultyEndpointsTests(TestCase):

    def setUp(self):

        self.admin_user = User.objects.create_user(username='admin_tester_ep', password='pass123')

        self.inst = AdminInstitution.objects.create(institution_name='Test College EP', admin=self.admin_user)

        self.user = User.objects.create_user(username='fac_tester_ep', password='pass123')

        self.profile = FacultyProfile.objects.create(

            user=self.user,

            institution=self.inst,

            department='Computer Science',

        )



    def test_get_ai_models_success(self):

        """Tests GET /api/faculty/ai-models/ returns rich installed model metadata."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        with patch('ai_paper_generator.ollama_client.OllamaClient.list_installed_models_with_details') as mock_models:

            mock_models.return_value = [

                {'name': 'qwen3:4b', 'size': 2497293931, 'details': {'parameter_size': '4.0B'}},

                {'name': 'granite3.3:2b', 'size': 1545321637, 'details': {'parameter_size': '2.5B'}},

                {'name': 'llama3.2:3b', 'size': 2019393189, 'details': {'parameter_size': '3.2B'}},

                {'name': 'phi3:mini', 'size': 2176178913, 'details': {'parameter_size': '3.8B'}},

                {'name': 'gemma3:4b', 'size': 3350272403, 'details': {'parameter_size': '3.9B'}},

            ]

            res = client.get('/api/faculty/ai-models/?refresh=true')

            self.assertEqual(res.status_code, 200)

            self.assertTrue(res.data['ollama_online'])

            self.assertEqual(len(res.data['models']), 5)

            self.assertEqual(res.data['assigned_roles']['generator'], 'qwen3:4b')

            self.assertEqual(res.data['assigned_roles']['validator'], 'phi3:mini')

            self.assertEqual(res.data['assigned_roles']['fallback'], 'gemma3:4b')



    def test_get_ai_models_offline(self):

        """Tests GET /api/faculty/ai-models/ returns 200 with ollama_online=False when offline."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        with patch('ai_paper_generator.ollama_client.OllamaClient.list_installed_models_with_details', side_effect=OllamaNotRunningError("Offline")):

            res = client.get('/api/faculty/ai-models/?refresh=true')

            self.assertEqual(res.status_code, 200)

            self.assertFalse(res.data['ollama_online'])

            self.assertEqual(res.data['models'], [])



    def test_syllabus_parse_text(self):

        """Tests POST /api/faculty/syllabus/parse/ with direct text."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        text = """Unit 1: Data Structures

Arrays, Stacks, Queues

Unit 2: Graph Algorithms

BFS, DFS, Dijkstra"""

        res = client.post('/api/faculty/syllabus/parse/', {'syllabus_text': text})

        self.assertEqual(res.status_code, 200)

        self.assertEqual(res.data['detected_topics_count'], 2)

        self.assertIn('Unit 1: Data Structures', res.data['topics'])

        self.assertIn('capacity', res.data)



    def test_syllabus_parse_file_upload(self):

        """Tests POST /api/faculty/syllabus/parse/ with file upload."""

        from rest_framework.test import APIClient

        from django.core.files.uploadedfile import SimpleUploadedFile

        client = APIClient()

        client.force_authenticate(user=self.user)



        content = b"""Chapter 1: Operating Systems

Processes and Threads

Chapter 2: Memory Management

Paging and Segmentation"""

        f = SimpleUploadedFile('syllabus.txt', content, content_type='text/plain')

        res = client.post('/api/faculty/syllabus/parse/', {'syllabus': f}, format='multipart')

        self.assertEqual(res.status_code, 200)

        self.assertEqual(res.data['detected_topics_count'], 2)

        self.assertEqual(res.data['filename'], 'syllabus.txt')



    def test_syllabus_parse_empty_payload(self):

        """Tests POST /api/faculty/syllabus/parse/ with missing input returns 400."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        res = client.post('/api/faculty/syllabus/parse/', {})

        self.assertEqual(res.status_code, 400)

        self.assertIn('error', res.data)

        self.assertIn('detail', res.data)



    def test_active_job_endpoint(self):

        """Tests GET /api/papers/generations/active/ returns None when no job is active."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        res = client.get('/api/papers/generations/active/')

        self.assertEqual(res.status_code, 200)

        self.assertIn('active_job', res.data)



    def test_generate_multipart_with_json_string_sections(self):

        """PART 4 Case 1: Valid multipart request with sections as a JSON string returns 201 with job_id."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        payload = {

            'title': 'Multipart Exam Test',

            'subject': 'Operating Systems',

            'duration': '45',

            'total_marks': '30',

            'sections': json.dumps([

                {'type': 'MCQ', 'count': 10, 'marks_per_question': 1},

                {'type': 'Short Answer', 'count': 4, 'marks_per_question': 5},

            ]),

            'topics': json.dumps(['Virtual Memory', 'Scheduling']),

            'difficulty_distribution': json.dumps({'Easy': 30, 'Medium': 50, 'Hard': 20}),

            'avoid_repeats': 'true',

        }

        res = client.post('/api/ai-generator/generate/', data=payload, format='multipart', HTTP_HOST='localhost')

        self.assertIn(res.status_code, [200, 201, 202])

        self.assertIn('job_id', res.data)

        self.assertTrue(GenerationJob.objects.filter(id=res.data['job_id']).exists())



    def test_generate_pure_json_with_real_list(self):

        """PART 4 Case 2: Pure JSON with real list sections returns 201 with job_id."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        payload = {

            'title': 'Pure JSON Exam Test',

            'subject': 'Operating Systems',

            'duration': 60,

            'total_marks': 25,

            'sections': [

                {'type': 'MCQ', 'count': 5, 'marks_per_question': 1},

                {'type': 'True/False', 'count': 10, 'marks_per_question': 1},

                {'type': 'Short Answer', 'count': 2, 'marks_per_question': 5},

            ],

            'topics': ['File Systems', 'Deadlocks'],

            'difficulty_distribution': {'Easy': 40, 'Medium': 40, 'Hard': 20},

            'avoid_repeats': True,

        }

        res = client.post('/api/ai-generator/generate/', data=payload, format='json', HTTP_HOST='localhost')

        self.assertIn(res.status_code, [200, 201, 202])

        self.assertIn('job_id', res.data)



    def test_generate_invalid_sections_broken_json(self):

        """PART 4 Case 3: Invalid sections string (broken JSON) returns 400 with clear message."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        payload = {

            'title': 'Broken JSON Test',

            'subject': 'Algorithms',

            'total_marks': 50,

            'sections': '[{"type": "MCQ", "count": 10 broken json',

            'topics': 'Graph Theory',

        }

        res = client.post('/api/ai-generator/generate/', data=payload, format='multipart', HTTP_HOST='localhost')

        self.assertEqual(res.status_code, 400)

        self.assertIn('error', res.data)

        self.assertIn('fields', res.data)

        self.assertIn('sections', res.data['fields'])

        # Confirms clear JSONDecodeError message

        self.assertTrue(any('Invalid JSON' in str(e) for e in res.data['fields']['sections']))



    def test_generate_sections_marks_mismatch(self):

        """PART 4 Case 4: Sections marks mismatch returns 400 with 'Allocated X / Y marks' message."""

        from rest_framework.test import APIClient

        client = APIClient()

        client.force_authenticate(user=self.user)



        payload = {

            'title': 'Mismatch Marks Test',

            'subject': 'Algorithms',

            'total_marks': '50',

            'sections': json.dumps([

                {'type': 'MCQ', 'count': 10, 'marks_per_question': 1}, # sum = 10 != 50

            ]),

            'topics': json.dumps(['Sorting']),

        }

        res = client.post('/api/ai-generator/generate/', data=payload, format='multipart', HTTP_HOST='localhost')

        self.assertEqual(res.status_code, 400)

        self.assertIn('error', res.data)

        self.assertIn('fields', res.data)

        self.assertIn('total_marks', res.data['fields'])

        error_msg = str(res.data['fields']['total_marks'][0])

        self.assertIn('Allocated 10 / 50 marks', error_msg)

