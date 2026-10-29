import hashlib
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from admins.models import AdminInstitution
from api.models import Exam, Question, PaperGenerationJob, Subject
from api.paper_engine.cache import compute_request_hash
from api.utils.generation_pipeline import QuestionBankService
from api.utils.validate_paper import audit_question_scope, verify_grounding_evidence, normalize_grounding_text

User = get_user_model()


class GroundedMaterialGenerationTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin_grounding',
            password='Password@123',
            email='admin@ttu.edu',
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name='Test Tech University',
            institution_code='TTU',
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.faculty = User.objects.create_user(
            username='faculty_grounding',
            password='Password@123',
            email='faculty@ttu.edu',
        )
        self.sub_java = Subject.objects.create(
            name='Java Programming',
            code='JAVA101',
            institution=self.institution,
        )
        self.sub_os = Subject.objects.create(
            name='Operating Systems',
            code='OS101',
            institution=self.institution,
        )

        # Seed an active Question in Java
        self.q_java = Question.objects.create(
            institution=self.institution,
            subject=self.sub_java,
            question_type='mcq',
            difficulty='medium',
            text='What is the primary function of the JVM bytecode verifier?',
            status=Question.Status.ACTIVE,
            marks=1.0,
            topic_text='JVM Architecture',
            source='bank_import',
        )

        # Seed an active Question in OS
        self.q_os = Question.objects.create(
            institution=self.institution,
            subject=self.sub_os,
            question_type='mcq',
            difficulty='medium',
            text='Explain deadlock conditions: mutual exclusion, hold and wait.',
            status=Question.Status.ACTIVE,
            marks=1.0,
            topic_text='Deadlocks',
            source='bank_import',
        )

    def test_question_bank_service_never_leaks_other_subjects(self):
        """Verifies QuestionBankService filters strictly by subject and never leaks across subjects."""
        # Query for OS subject by ID
        res_os = QuestionBankService.get_reusable_questions(
            institution_id=self.institution.id,
            subject_id=self.sub_os.id,
            question_type='mcq',
            difficulty='medium',
            needed_count=5,
        )
        self.assertEqual(len(res_os), 1)
        self.assertIn('deadlock', res_os[0]['text'].lower())

        # Query for Java subject by text name
        res_java = QuestionBankService.get_reusable_questions(
            institution_id=self.institution.id,
            subject_name='Java Programming',
            question_type='mcq',
            difficulty='medium',
            needed_count=5,
        )
        self.assertEqual(len(res_java), 1)
        self.assertIn('jvm', res_java[0]['text'].lower())

        # Query with no subject specified -> must return EMPTY to avoid leaks across subjects
        res_none = QuestionBankService.get_reusable_questions(
            institution_id=self.institution.id,
            subject_id=None,
            subject_name=None,
            question_type='mcq',
            difficulty='medium',
            needed_count=5,
        )
        self.assertEqual(len(res_none), 0)

    def test_compute_request_hash_includes_document_blueprint_model(self):
        """Cache request hash must vary when file hash, blueprint, or model changes."""
        base_payload = {
            'title': 'Operating Systems Midterm',
            'total_marks': 50,
            'duration_minutes': 60,
            'topics': ['Deadlocks', 'Memory Management'],
            'question_types': ['MCQ'],
            'difficulty_distribution': {'easy': 30, 'medium': 50, 'hard': 20},
            'subject_name': 'Operating Systems',
            'blueprint': {'mcq': {'count': 10, 'marks': 2.0}},
            'model': 'qwen2.5:3b-instruct',
            'source_document_hash': 'hash_aaa_111',
        }
        hash1 = compute_request_hash(base_payload)

        # Varying document hash
        payload_diff_doc = dict(base_payload, source_document_hash='hash_bbb_222')
        hash_diff_doc = compute_request_hash(payload_diff_doc)
        self.assertNotEqual(hash1, hash_diff_doc)

        # Varying blueprint
        payload_diff_bp = dict(base_payload, blueprint={'mcq': {'count': 25, 'marks': 2.0}})
        hash_diff_bp = compute_request_hash(payload_diff_bp)
        self.assertNotEqual(hash1, hash_diff_bp)

        # Varying model
        payload_diff_model = dict(base_payload, model='llama3.2:3b')
        hash_diff_model = compute_request_hash(payload_diff_model)
        self.assertNotEqual(hash1, hash_diff_model)

    def test_grounding_evidence_verification(self):
        """Tests strict verbatim and normalized matching in syllabus grounding."""
        syllabus = "Process synchronization involves semaphores, mutexes, and critical section problems."
        
        # Exact quote
        self.assertTrue(verify_grounding_evidence("semaphores, mutexes, and critical section", syllabus))
        
        # Normalized with punctuation / ligatures
        self.assertTrue(verify_grounding_evidence("semaphores mutexes and critical section", syllabus))
        
        # Hallucinated evidence from another domain
        self.assertFalse(verify_grounding_evidence("Ethereum smart contracts use EVM bytecode", syllabus))

    def test_scope_audit_detects_foreign_questions(self):
        """audit_question_scope accurately flags questions not supported by the exam's syllabus."""
        syllabus = "Systems Analysis and Design covers requirement gathering, DFDs, and ER diagrams."
        
        q_grounded = Question(
            text="Explain Data Flow Diagrams (DFDs) in requirement analysis.",
            topic_text="DFDs",
            source="ai_material",
            source_evidence="covers requirement gathering, DFDs",
        )
        audit_g = audit_question_scope(q_grounded, syllabus, selected_topics=["DFDs"])
        self.assertTrue(audit_g['in_scope'])

        q_foreign = Question(
            text="Which of the following is NOT a design pattern in Java?",
            topic_text="Design Patterns",
            source="bank_import",
            source_evidence="singleton and factory design patterns",
        )
        audit_f = audit_question_scope(q_foreign, syllabus, selected_topics=["DFDs"])
        self.assertFalse(audit_f['in_scope'])
        self.assertIn("not in the source document", audit_f['reason'])

    def test_save_generated_exam_questions_persists_grounding_metadata(self):
        """_save_generated_exam_questions saves source_document_hash, source_evidence, and source='ai_material'."""
        from api.generate_paper import _save_generated_exam_questions

        syllabus = "Database normalization includes 1NF, 2NF, 3NF, and BCNF definitions."
        doc_hash = hashlib.sha256(syllabus.encode('utf-8')).hexdigest()

        exam = Exam.objects.create(
            institution=self.institution,
            created_by=self.faculty,
            title='DBMS Quiz',
            subject='DBMS',
            duration_minutes=60,
            total_marks=10,
            target_total_marks=10,
            source_syllabus_text=syllabus,
            status=Exam.Status.GENERATING,
        )

        job = PaperGenerationJob.objects.create(
            institution=self.institution,
            faculty=self.faculty,
            exam=exam,
            model='qwen2.5:3b-instruct',
            status=PaperGenerationJob.Status.RUNNING,
            target_marks=10,
        )

        generated = [{
            'type': 'short_answer',
            'difficulty': 'medium',
            'topic': 'Database Normalization',
            'text': 'Define 3NF in relational databases.',
            'marks': 5.0,
            'source': 'ai_material',
            'source_evidence': 'Database normalization includes 1NF, 2NF, 3NF',
            'model_answer': 'A relation is in 3NF if it is in 2NF and has no transitive dependencies.',
            'rubric': [{'criterion': 'Definition of 3NF', 'marks': 5.0}],
            'word_limit': 150,
        }, {
            'type': 'short_answer',
            'difficulty': 'medium',
            'topic': 'Database Normalization',
            'text': 'Define BCNF in relational databases.',
            'marks': 5.0,
            'source': 'ai_material',
            'source_evidence': 'and BCNF definitions',
            'model_answer': 'A relation is in BCNF if for every functional dependency X -> Y, X is a super key.',
            'rubric': [{'criterion': 'Definition of BCNF', 'marks': 5.0}],
            'word_limit': 150,
        }]

        _save_generated_exam_questions(
            job=job,
            exam_id=exam.id,
            generated_questions=generated,
            target_marks=10,
            planned_marks=10,
            initial_generated_marks=10,
            dropped_dups=0,
            rejected_duplicates_marks=0,
            round_idx=1,
            warnings=[],
            syllabus_text=syllabus,
            model_name='qwen2.5:3b-instruct',
        )

        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertEqual(exam.questions.count(), 2)

        for q in exam.questions.all():
            self.assertEqual(q.source, 'ai_material')
            self.assertEqual(q.source_document_hash, doc_hash)
            self.assertTrue(len(q.source_evidence) > 0)
            self.assertIn('Database Normalization', exam.topics)
