from django.test import TestCase

from backend.services.ollama_service import OllamaService


class OllamaResponseNormalizationTests(TestCase):
	def setUp(self):
		self.questions = [
			{
				'id': 1,
				'question': 'What is a computer?',
				'type': 'MCQ',
				'difficulty': 'Easy',
				'answer': 'A device',
				'marks': 2,
			},
		]

	def assert_questions_found(self, payload):
		normalized = OllamaService._normalize_generated_response(payload)
		self.assertEqual(len(normalized['questions']), 1)
		self.assertEqual(normalized['questions'][0]['question'], 'What is a computer?')

	def test_direct_questions_object(self):
		self.assert_questions_found({'questions': self.questions})

	def test_response_json_string(self):
		import json

		self.assert_questions_found({'response': json.dumps({'questions': self.questions})})

	def test_response_nested_object(self):
		self.assert_questions_found({'response': {'questions': self.questions}})

	def test_paper_wrapper(self):
		self.assert_questions_found({'paper': {'questions': self.questions}})

	def test_data_wrapper(self):
		self.assert_questions_found({'data': {'questions': self.questions}})
