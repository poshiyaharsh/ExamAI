import json
import logging
import socket
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)


MODEL_MAP = {
    'ollama-qwen2.5-3b': 'qwen2.5:3b-instruct',
    'ollama-llama3.2-3b': 'llama3.2:3b',
    'ollama-phi3-mini': 'phi3:mini',
}


class OllamaServiceError(RuntimeError):
    pass


class OllamaConnectionError(OllamaServiceError):
    pass


class OllamaTimeoutError(OllamaServiceError):
    pass


class OllamaModelNotInstalledError(OllamaServiceError):
    pass


class OllamaInvalidResponseError(OllamaServiceError):
    pass


class OllamaService:
    def __init__(self, base_url='http://localhost:11434', timeout=180):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def _request(self, path, *, payload=None, timeout=None):
        request = urllib.request.Request(
            f'{self.base_url}{path}',
            data=json.dumps(payload).encode('utf-8') if payload is not None else None,
            headers={'Content-Type': 'application/json'} if payload is not None else {},
            method='POST' if payload is not None else 'GET',
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                raw = response.read().decode('utf-8').strip()
                if not raw:
                    return {}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise OllamaInvalidResponseError('Ollama returned invalid JSON.') from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='ignore').strip()
            message = body
            if body:
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    message = parsed.get('error') or parsed.get('message') or body
            lowered = message.lower()
            if exc.code == 404 and ('model' in lowered or 'not found' in lowered):
                raise OllamaModelNotInstalledError(message or 'The selected Ollama model is not installed.') from exc
            raise OllamaServiceError(message or f'HTTP {exc.code}') from exc
        except (socket.timeout, TimeoutError) as exc:
            raise OllamaTimeoutError('Ollama generation timed out. Please try again.') from exc
        except urllib.error.URLError as exc:
            raise OllamaConnectionError('Ollama is not running. Please start Ollama and try again.') from exc

    def list_models(self, timeout=None):
        response = self._request('/api/tags', timeout=timeout)
        models = response.get('models', []) if isinstance(response, dict) else []
        return [item.get('name') for item in models if isinstance(item, dict) and item.get('name')]

    def get_status(self, ui_model='ollama-qwen2.5-3b', timeout=5):
        try:
            models = self.list_models(timeout=timeout)
            backend_model = self.model_for(ui_model)
            return {
                'connected': True,
                'model_installed': backend_model in models,
                'models': models,
                'message': 'Ollama: Connected' if backend_model in models else f'{backend_model} is not installed. Run: ollama pull {backend_model}',
            }
        except OllamaServiceError:
            return {
                'connected': False,
                'model_installed': False,
                'models': [],
                'message': 'Ollama: Not Running',
            }

    def model_for(self, ui_model):
        return MODEL_MAP.get(ui_model, '')

    @staticmethod
    def _strip_json_wrapper(content):
        cleaned = content.strip()
        if cleaned.startswith('```'):
            first_line, separator, remainder = cleaned.partition('\n')
            if first_line.strip().lower() in {'```', '```json'}:
                cleaned = remainder
                if cleaned.rstrip().endswith('```'):
                    cleaned = cleaned.rstrip()[:-3]
        return cleaned.strip()

    @classmethod
    def _parse_generated_json(cls, content):
        if isinstance(content, (dict, list)):
            return content
        if not isinstance(content, str) or not content.strip():
            raise OllamaInvalidResponseError('Ollama returned an empty response.')

        cleaned = cls._strip_json_wrapper(content)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            object_start = cleaned.find('{')
            if object_start < 0:
                logger.warning('[Ollama] Parsed JSON successfully: false; no JSON object found')
                raise OllamaInvalidResponseError('Ollama returned invalid JSON.')
            try:
                parsed, _ = decoder.raw_decode(cleaned[object_start:])
            except json.JSONDecodeError as exc:
                logger.warning('[Ollama] Parsed JSON successfully: false; JSON decode failed')
                raise OllamaInvalidResponseError('Ollama returned invalid JSON.') from exc

        if not isinstance(parsed, (dict, list)):
            logger.warning('[Ollama] Parsed JSON successfully: false; parsed value was not an object or list')
            raise OllamaInvalidResponseError('Ollama returned invalid JSON.')
        return parsed

    @classmethod
    def _question_like(cls, value):
        if not isinstance(value, dict):
            return False
        return any(key in value and str(value[key] or '').strip() for key in ('question', 'question_text', 'text'))

    @classmethod
    def _find_question_lists(cls, value, path='$', depth=0):
        if depth > 4:
            return []

        candidates = []
        if isinstance(value, dict):
            for key in ('questions', 'exam_questions', 'paper_questions', 'items'):
                candidate = value.get(key)
                if isinstance(candidate, list) and candidate and any(cls._question_like(item) for item in candidate):
                    candidates.append((f'{path}.{key}', candidate))
            for key, child in value.items():
                if key not in {'questions', 'exam_questions', 'paper_questions', 'items'} and isinstance(child, (dict, list)):
                    candidates.extend(cls._find_question_lists(child, f'{path}.{key}', depth + 1))
        elif isinstance(value, list):
            if value and any(cls._question_like(item) for item in value):
                candidates.append((path, value))
            else:
                for index, child in enumerate(value):
                    if isinstance(child, (dict, list)):
                        candidates.extend(cls._find_question_lists(child, f'{path}[{index}]', depth + 1))
        return candidates

    @classmethod
    def _extract_questions(cls, data):
        candidates = cls._find_question_lists(data)
        logger.warning(
            '[Ollama] Candidate question paths: %s',
            [path for path, _ in candidates],
        )
        if not candidates:
            return None
        return candidates[0][1]

    @classmethod
    def _normalize_generated_response(cls, response):
        if not isinstance(response, (dict, list)):
            raise OllamaInvalidResponseError('Ollama returned an invalid response.')

        generated = response
        if isinstance(response, dict) and 'response' in response:
            generated = cls._parse_generated_json(response['response'])
        elif isinstance(response, dict) and not isinstance(response.get('questions'), list):
            for key in ('paper', 'data', 'generated_paper', 'output'):
                candidate = response.get(key)
                if isinstance(candidate, (dict, list, str)):
                    generated = cls._parse_generated_json(candidate)
                    break

        if isinstance(generated, dict) and 'response' in generated:
            generated = cls._parse_generated_json(generated['response'])

        questions = cls._extract_questions(generated)
        logger.warning(
            '[Ollama] Top-level parsed type: %s; Top-level keys: %s; Final question count: %s',
            type(generated).__name__,
            sorted(generated.keys()) if isinstance(generated, dict) else [],
            len(questions) if questions else 0,
        )
        if not questions:
            raise OllamaInvalidResponseError('Ollama did not return a non-empty questions array.')
        if isinstance(generated, list):
            generated = {'questions': generated}
        elif not isinstance(generated.get('questions'), list):
            generated = dict(generated)
            generated['questions'] = questions
        return generated

    def generate(self, ui_model, prompt):
        model = self.model_for(ui_model)
        if not model:
            raise OllamaServiceError('The selected Ollama model is not installed.')

        logger.warning('[Ollama] Request started; Model: %s', model)
        available_models = self.list_models(timeout=15)
        if model not in available_models:
            raise OllamaModelNotInstalledError('The selected Ollama model is not installed.')

        response = self._request(
            '/api/generate',
            payload={
                'model': model,
                'prompt': prompt,
                'stream': False,
                'format': 'json',
            },
        )
        logger.warning('[Ollama] HTTP status: 200; Response received')
        if not isinstance(response, dict):
            raise OllamaInvalidResponseError('Ollama returned an invalid response.')

        logger.warning(
            '[Ollama] Response keys: %s; Response field exists: %s',
            sorted(response.keys()),
            'response' in response,
        )

        if response.get('error'):
            raise OllamaServiceError(str(response['error']))

        content = response.get('response')
        logger.warning(
            '[Ollama] Generated response length: %s',
            len(content) if isinstance(content, str) else 0,
        )
        return self._normalize_generated_response(response)

    def generate_paper(self, ui_model, prompt):
        return self.generate(ui_model, prompt)
