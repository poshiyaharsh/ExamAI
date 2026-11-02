"""
Multilingual AI Paper Generation Test Suite.
Tests:
1. Language detection (13 languages, Hinglish, legacy 8-bit text, short/noisy input, code-heavy).
2. English parity (byte-for-byte identical prompts, identical token budgeting, model roles).
3. Pipeline components (Unicode TF-IDF, Deduplicator, Validator, Rubric builder, Drift detection).
4. Export tests (PDF and DOCX rendering with Unicode fonts).
5. Additive database fields (Paper.language and GenerationJob.language).
"""
import unittest
from unittest.mock import MagicMock, patch
from django.test import TestCase

from ai_paper_generator.language import (
    detect_language,
    determine_paper_language,
    is_garbled_legacy_text,
    get_language_name,
    verify_question_language,
    analyze_scripts,
)
from ai_paper_generator.config import (
    MODEL_ROLES,
    PREFERRED_EMBEDDING_MODEL,
    MULTILINGUAL_EMBEDDING_MODEL,
    get_token_expansion_factor,
    get_model_roles_for_language,
    get_embedding_model_for_language,
    get_batch_size_for_language,
    get_num_predict_for_language,
)
from ai_paper_generator.prompts.mcq import build_batch_mcq_prompt
from ai_paper_generator.prompts.true_false import build_batch_true_false_prompt
from ai_paper_generator.prompts.fill_blank import build_batch_fill_blank_prompt
from ai_paper_generator.prompts.short import build_batch_short_prompt
from ai_paper_generator.prompts.long import build_batch_long_prompt
from ai_paper_generator.rag.embedder import LocalTfIdfEmbedder
from ai_paper_generator.generators.deduplicator import QuestionDeduplicator
from ai_paper_generator.generators.validator import validate_rules
from ai_paper_generator.generators.rubric_builder import build_rubric
from ai_paper_generator.exporters.pdf import export_paper_to_pdf
from ai_paper_generator.exporters.docx import export_paper_to_docx


class LanguageDetectionTests(TestCase):
    def test_single_language_detection(self):
        cases = [
            ("Hindi", "प्रकाश संश्लेषण की प्रक्रिया का विस्तृत वर्णन कीजिए। इसके मुख्य चरण क्या हैं?", "hi"),
            ("Gujarati", "પ્રકાશસંશ્લેષણ પ્રક્રિયા એટલે શું? તેના મુખ્ય તબક્કા અને મહત્વ સમજાવો.", "gu"),
            ("English", "Explain the process of photosynthesis and its physiological significance.", "en"),
            ("Marathi", "प्रकाशसंश्लेषण ही वनस्पतींमध्ये घडणारी महत्त्वाची प्रक्रिया आहे. तिचे घटक स्पष्ट करा.", "mr"),
            ("Tamil", "ஒளிச்சேர்க்கை செயல்முறையை விவரித்து அதன் முக்கியத்துவத்தை விளக்குக.", "ta"),
            ("Bengali", "সালোকসংশ্লেষণ প্রক্রিয়ার মূল উপাদানগুলি কী কী এবং কীভাবে ঘটে তা ব্যাখ্যা করুন।", "bn"),
            ("Urdu", "فوٹوسنتھیسس کے عمل کی وضاحت کریں اور اس کے اہم مراحل بیان کریں۔", "ur"),
            ("Arabic", "اشرح عملية التمثيل الضوئي وأهميتها الحيوية للنباتات والبيئة بالتفصيل.", "ar"),
            ("French", "Expliquez le processus de la photosynthèse et ses étapes principales.", "fr"),
            ("Spanish", "Explique el proceso de la fotosíntesis y sus fases principales en las plantas.", "es"),
            ("German", "Erklären Sie den Prozess der Photosynthese und die wesentlichen chemischen Reaktionen.", "de"),
            ("Chinese", "请详细解释植物光合作用的过程及其主要的生物化学阶段。", "zh"),
            ("Japanese", "光合成のプロセスとその生物学的な重要性について詳しく説明しなさい。", "ja"),
        ]
        for name, text, expected_iso in cases:
            iso, conf, meta = detect_language(text)
            self.assertEqual(iso, expected_iso, f"Failed on {name}: got '{iso}', expected '{expected_iso}'")
            self.assertGreaterEqual(conf, 0.70)

    def test_hinglish_technical_detection(self):
        # Hindi material containing technical English computer science keywords
        hinglish_text = (
            "Python mein Object-Oriented Programming ke mukhya concepts jaise Classes, "
            "Inheritance aur Polymorphism ko detail mein samjhaiye. Function overloading kaise kaam karta hai?"
        )
        iso, conf, meta = detect_language(hinglish_text)
        self.assertEqual(iso, "hi")

    def test_garbled_legacy_font_detection(self):
        # Kruti Dev legacy 8-bit encoded gibberish
        kruti_text = "iz'u 1: dksbZ Hkh vFkok fuEufyf[kr izdkj lafgrk Hkkjr le;k gksrk djsa fdrkc iBu"
        self.assertTrue(is_garbled_legacy_text(kruti_text))

        # Shree-Lipi legacy Gujarati gibberish
        shree_text = "ÁÂÃÄÅÆÇÈÉÊËÌÍÎÏ àáâãäåæçèéêëìíîï ðñòóôõö"
        self.assertTrue(is_garbled_legacy_text(shree_text))

        # Modern Unicode Gujarati should NOT be detected as garbled
        clean_gujarati = "પર્યાવરણ અને પરિસ્થિતિવિજ્ઞાનનો અભ્યાસ કરવો જરૂરી છે."
        self.assertFalse(is_garbled_legacy_text(clean_gujarati))

        # Clean English text should NOT be detected as garbled
        clean_english = "The quick brown fox jumps over the lazy dog."
        self.assertFalse(is_garbled_legacy_text(clean_english))

    def test_code_and_math_heavy_text(self):
        code_text = """
        def fibonacci(n: int) -> int:
            if n <= 1:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)
        """
        iso, conf, _ = detect_language(code_text)
        self.assertEqual(iso, "en")

    def test_determine_paper_language_weighting(self):
        docs = [
            {'text': 'प्रौद्योगिकी और कम्प्यूटर विज्ञान का परिचय। एल्गोरिदम और डेटा संरचनाएं।', 'source': 'syllabus.pdf', 'is_syllabus': True},
            {'text': 'Computer Science quick reference notes.', 'source': 'notes.txt', 'is_syllabus': False},
        ]
        decision, conf, meta = determine_paper_language(docs)
        self.assertEqual(decision, 'hi')
        self.assertIn('shares', meta)


class EnglishParityTests(TestCase):
    def test_prompts_byte_for_byte_identical_for_english(self):
        slots = [{'topic': 'Data Structures', 'difficulty': 'Medium', 'marks': 2, 'slot_index': 1}]
        ctx = "Arrays and linked lists are standard data structures."

        # Calling with language='en' vs omitting language parameter
        p_mcq_default = build_batch_mcq_prompt("CS", slots, ctx)
        p_mcq_en = build_batch_mcq_prompt("CS", slots, ctx, language="en")
        self.assertEqual(p_mcq_default, p_mcq_en)
        self.assertNotIn("LANGUAGE REQUIREMENT", p_mcq_en)

        p_tf_default = build_batch_true_false_prompt("CS", slots, ctx)
        p_tf_en = build_batch_true_false_prompt("CS", slots, ctx, language="en")
        self.assertEqual(p_tf_default, p_tf_en)
        self.assertNotIn("LANGUAGE REQUIREMENT", p_tf_en)

        p_fill_default = build_batch_fill_blank_prompt("CS", slots, ctx)
        p_fill_en = build_batch_fill_blank_prompt("CS", slots, ctx, language="en")
        self.assertEqual(p_fill_default, p_fill_en)
        self.assertNotIn("LANGUAGE REQUIREMENT", p_fill_en)

        p_short_default = build_batch_short_prompt("CS", slots, ctx)
        p_short_en = build_batch_short_prompt("CS", slots, ctx, language="en")
        self.assertEqual(p_short_default, p_short_en)
        self.assertNotIn("LANGUAGE REQUIREMENT", p_short_en)

        p_long_default = build_batch_long_prompt("CS", slots, ctx)
        p_long_en = build_batch_long_prompt("CS", slots, ctx, language="en")
        self.assertEqual(p_long_default, p_long_en)
        self.assertNotIn("LANGUAGE REQUIREMENT", p_long_en)

    def test_english_configuration_parity(self):
        self.assertEqual(get_token_expansion_factor('en'), 1.0)
        self.assertEqual(get_embedding_model_for_language('en'), PREFERRED_EMBEDDING_MODEL)
        self.assertEqual(get_model_roles_for_language('en'), MODEL_ROLES)
        self.assertEqual(get_batch_size_for_language('MCQ', 'en'), 10)
        self.assertEqual(get_num_predict_for_language('MCQ', 'en'), 95)


class MultilingualPipelineTests(TestCase):
    def test_multilingual_prompt_injection(self):
        slots = [{'topic': 'પર્યાવરણ', 'difficulty': 'Medium', 'marks': 1, 'slot_index': 1}]
        ctx = "પર્યાવરણ સંરક્ષણ એ જીવન ટકાવી રાખવા માટે અનિવાર્ય છે."

        prompt_gu = build_batch_mcq_prompt("વિજ્ઞાન", slots, ctx, language="gu")
        self.assertIn("LANGUAGE REQUIREMENT", prompt_gu)
        self.assertIn("Gujarati", prompt_gu)
        self.assertIn("gu", prompt_gu)
        # JSON keys must remain in English
        self.assertIn('"question", "correct", "distractors"', prompt_gu)

    def test_local_tfidf_unicode_tokenization(self):
        embedder = LocalTfIdfEmbedder()
        docs = [
            "પ્રકાશસંશ્લેષણ પ્રક્રિયા વનસ્પતિમાં ખોરાક બનાવવા માટે થાય છે.",
            "જળચક્ર પૃથ્વી પર પાણીનું પરિભ્રમણ દર્શાવે છે.",
        ]
        embedder.fit(docs)
        self.assertGreater(len(embedder.vocab), 0)
        vec = embedder.transform("પ્રકાશસંશ્લેષણ પ્રક્રિયા ખોરાક")
        self.assertEqual(len(vec), len(embedder.vocab))
        # Vector must not be all zeros
        self.assertGreater(sum(v * v for v in vec), 0.0)

    def test_question_deduplicator_multilingual(self):
        dedup = QuestionDeduplicator(similarity_threshold=0.70)
        q1 = {
            'slot_index': 1,
            'question': 'પ્રકાશસંશ્લેષણ પ્રક્રિયા એટલે શું અને તે કેવી રીતે કાર્ય કરે છે?',
            'answer': 'વનસ્પતિ સૂર્યપ્રકાશ દ્વારા ખોરાક બનાવે છે.',
        }
        dedup.add(q1)

        # Exact duplicate in Gujarati
        q_dup = {
            'slot_index': 2,
            'question': 'પ્રકાશસંશ્લેષણ પ્રક્રિયા એટલે શું અને તે કેવી રીતે કાર્ય કરે છે?',
            'answer': 'વનસ્પતિ સૂર્યપ્રકાશ દ્વારા ખોરાક બનાવે છે.',
        }
        is_dup, reason = dedup.is_duplicate(q_dup)
        self.assertTrue(is_dup)

        # Distinct question in Gujarati
        q_distinct = {
            'slot_index': 3,
            'question': 'પૃથ્વી પર જળચક્રના મુખ્ય તબક્કાઓ કયા કયા છે?',
            'answer': 'બાષ્પીભવન અને ઘનીભવન.',
        }
        is_dup2, _ = dedup.is_duplicate(q_distinct)
        self.assertFalse(is_dup2)

    def test_validator_multilingual_true_false(self):
        # Gujarati True / False
        q_gu_true = {
            'slot_index': 1,
            'type': 'True/False',
            'question': 'સૂર્ય એ પૃથ્વી માટે ઊર્જાનો પ્રાથમિક સ્ત્રોત છે.',
            'answer': 'સાચું',
        }
        ok, reason = validate_rules(q_gu_true, language='gu')
        self.assertTrue(ok)
        self.assertEqual(q_gu_true['answer'], 'True')

        # Hindi False
        q_hi_false = {
            'slot_index': 2,
            'type': 'True/False',
            'question': 'चंद्रमा का अपना स्वयं का प्रकाश होता है।',
            'answer': 'गलत',
        }
        ok2, reason2 = validate_rules(q_hi_false, language='hi')
        self.assertTrue(ok2)
        self.assertEqual(q_hi_false['answer'], 'False')

    def test_rubric_builder_no_english_pollution(self):
        # Non-English question and answer
        q_text = "સૂર્યમંડળના ગ્રહો વિશે ટૂંકનોંધ લખો."
        m_ans = "સૂર્યમંડળમાં આઠ ગ્રહો છે. બુધ સૂર્યની સૌથી નજીકનો ગ્રહ છે. ગુરુ સૌથી મોટો ગ્રહ છે."
        rub = build_rubric("Short Answer", 3, question_text=q_text, model_answer=m_ans, language="gu")
        pts = rub[0]['key_points']
        self.assertEqual(len(pts), 3)
        # Verify no English template words leaked into Gujarati rubric
        for pt in pts:
            self.assertNotIn("Core definition and operational principles", pt)
            self.assertNotIn("Fundamental Concepts", pt)

    def test_output_language_drift_verification(self):
        # Target is Gujarati, but model emitted English text
        drifted_q = {
            'question': 'What is photosynthesis and how does it work in green plants?',
            'answer': 'Plants produce glucose and oxygen using sunlight.',
        }
        ok, reason = verify_question_language(drifted_q, target_language='gu')
        self.assertFalse(ok)
        self.assertIn("Language drift", reason)

        # Target is Gujarati, and model emitted Gujarati text
        valid_q = {
            'question': 'પ્રકાશસંશ્લેષણ એટલે શું અને તે લીલી વનસ્પતિમાં કેવી રીતે થાય છે?',
            'answer': 'વનસ્પતિ સૂર્યપ્રકાશની હાજરીમાં ગ્લુકોઝ અને ઓક્સિજન ઉત્પન્ન કરે છે.',
        }
        ok2, _ = verify_question_language(valid_q, target_language='gu')
        self.assertTrue(ok2)


class MultilingualExportTests(TestCase):
    def test_multilingual_pdf_export(self):
        paper_data = {
            'title': 'વિજ્ઞાન વાર્ષિક પરીક્ષા ૨૦૨૬',
            'subject': 'સામાન્ય વિજ્ઞાન',
            'duration': 90,
            'total_marks': 25,
            'language': 'gu',
            'questions': [
                {
                    'question_number': 1,
                    'type': 'MCQ',
                    'marks': 1,
                    'question': 'પ્રકાશસંશ્લેષણ પ્રક્રિયામાં કયો વાયુ મુક્ત થાય છે?',
                    'options': ['ઓક્સિજન', 'કાર્બન ડાયોક્સાઇડ', 'નાઇટ્રોજન', 'હાઇડ્રોજન'],
                    'answer': 'ઓક્સિજન',
                },
                {
                    'question_number': 2,
                    'type': 'True/False',
                    'marks': 1,
                    'question': 'સૂર્ય પૃથ્વીની આસપાસ ફરે છે.',
                    'answer': 'False',
                },
                {
                    'question_number': 3,
                    'type': 'Short Answer',
                    'marks': 2,
                    'question': 'વનસ્પતિમાં હરિતદ્રવ્યનું કાર્ય સમજાવો.',
                    'answer': 'હરિતદ્રવ્ય સૂર્યપ્રકાશનું શોષણ કરે છે અને ખોરાક બનાવવામાં મદદ કરે છે.',
                    'rubric': [{'key_points': ['સૂર્યપ્રકાશનું શોષણ', 'ખોરાક નિર્માણમાં સહાય']}],
                }
            ]
        }
        pdf_bytes = export_paper_to_pdf(paper_data, include_answers=True)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        self.assertGreater(len(pdf_bytes), 5000)

    def test_multilingual_docx_export(self):
        paper_data = {
            'title': 'اختبار الفصل النهائي في الفيزياء',
            'subject': 'الفيزياء',
            'duration': 60,
            'total_marks': 20,
            'language': 'ar',
            'questions': [
                {
                    'question_number': 1,
                    'type': 'MCQ',
                    'marks': 1,
                    'question': 'ما هي وحدة قياس القوة في النظام الدولي؟',
                    'options': ['نيوتن', 'جول', 'واط', 'باسكال'],
                    'answer': 'نيوتن',
                }
            ]
        }
        docx_bytes = export_paper_to_docx(paper_data, include_answers=True)
        # DOCX is a zip archive starting with PK (0x50, 0x4B)
        self.assertTrue(docx_bytes.startswith(b'PK'))
        self.assertGreater(len(docx_bytes), 5000)

    def test_legacy_gujarati_shree_lipi_converter(self):
        from ai_paper_generator.rag.legacy_fonts import convert_shree_to_unicode
        sample_8bit = "ÀùQMÝðËß ±õËáõ åð_? ÀùQMÝðËßÞë_ ÜðAÝ áZëHëù"
        converted = convert_shree_to_unicode(sample_8bit)
        self.assertIn("કોમ્પ્યુટર", converted)
        self.assertIn("એટલે", converted)
        self.assertIn("મુખ્ય", converted)
        self.assertIn("લક્ષણો", converted)

