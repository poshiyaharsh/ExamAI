import json
import logging
import os
import socket
import urllib.error
import urllib.parse
import urllib.request


logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """A safe, user-displayable provider failure that never includes an API key."""

    def __init__(self, provider, reason, code='provider_unavailable'):
        self.provider = provider
        self.reason = reason
        self.code = code
        super().__init__(reason)


class AIProviderManager:
    """Loads AI configuration from the environment and fails over between providers."""

    PROVIDERS = ('openai', 'gemini', 'anthropic')
    UI_PROVIDER_MAP = {
        'GPT-4': 'openai',
        'GPT-3.5': 'openai',
        'Gemini Pro': 'gemini',
        'Claude 3': 'anthropic',
    }

    def __init__(self):
        self.config = {
            'openai': {
                'label': 'OpenAI',
                'key': os.getenv('OPENAI_API_KEY', '').strip(),
                'model': os.getenv('OPENAI_MODEL', '').strip(),
            },
            'gemini': {
                'label': 'Google Gemini',
                'key': os.getenv('GEMINI_API_KEY', '').strip(),
                'model': os.getenv('GEMINI_MODEL', '').strip(),
            },
            'anthropic': {
                'label': 'Anthropic Claude',
                'key': os.getenv('ANTHROPIC_API_KEY', '').strip(),
                'model': os.getenv('ANTHROPIC_MODEL', '').strip(),
            },
        }
        self._gemini_model = None
        self._available = {}
        self._reasons = {}
        self._codes = {}
        try:
            self.timeout = max(1, int(os.getenv('AI_PROVIDER_TIMEOUT_SECONDS', '60')))
        except ValueError:
            self.timeout = 60
            logger.warning('AI_PROVIDER_TIMEOUT_SECONDS is invalid; using the default timeout.')
        self.validate_startup()

    def _request(self, url, *, headers=None, payload=None, timeout=None):
        timeout = timeout or self.timeout
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8') if payload is not None else None,
            headers={**(headers or {}), **({'Content-Type': 'application/json'} if payload is not None else {})},
            method='POST' if payload is not None else 'GET',
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='ignore')
            raise RuntimeError(body or f'HTTP {exc.code}') from exc
        except (socket.timeout, TimeoutError) as exc:
            raise TimeoutError('provider request timed out') from exc
        except urllib.error.URLError as exc:
            raise ConnectionError('provider could not be reached') from exc

    @staticmethod
    def _error_details(error):
        message = str(error).lower()
        if 'insufficient_quota' in message or 'quota' in message:
            return 'insufficient_quota', 'quota is unavailable'
        if 'invalid_api_key' in message or 'invalid api key' in message or 'authentication' in message:
            return 'invalid_api_key', 'API key is invalid'
        if 'model_not_found' in message or 'model not found' in message or 'not found' in message:
            return 'model_not_found', 'configured model is not available'
        if 'permission_denied' in message or 'permission denied' in message or 'forbidden' in message:
            return 'permission_denied', 'provider denied access to the configured model'
        if 'rate_limit' in message or 'rate limit' in message or '429' in message:
            return 'rate_limit_exceeded', 'rate limit reached'
        if 'timeout' in message or 'timed out' in message:
            return 'timeout', 'provider request timed out'
        if 'invalid argument' in message or 'invalid request' in message or '400' in message:
            return 'invalid_request', 'provider rejected the generation request'
        if isinstance(error, ConnectionError):
            return 'network_error', 'provider could not be reached'
        return 'provider_unavailable', 'provider request failed'

    @classmethod
    def _safe_reason(cls, error):
        return cls._error_details(error)[1]

    def _discover_gemini_model(self):
        config = self.config['gemini']
        url = 'https://generativelanguage.googleapis.com/v1beta/models?key=' + urllib.parse.quote(config['key'])
        response = self._request(url)
        models = response.get('models', [])
        compatible = [
            item.get('name', '').removeprefix('models/')
            for item in models
            if 'generateContent' in item.get('supportedGenerationMethods', []) and item.get('name')
        ]
        if not compatible:
            raise ProviderError('gemini', 'no Gemini model supports generateContent', 'model_not_found')

        configured = config['model'].removeprefix('models/')
        self._gemini_model = configured if configured in compatible else compatible[0]
        if configured and configured != self._gemini_model:
            logger.warning('Configured Gemini model is unavailable; using discovered model %s.', self._gemini_model)
        return self._gemini_model

    def _validate_openai(self):
        config = self.config['openai']
        if not config['model']:
            return False, 'OPENAI_MODEL is not configured'
        try:
            self._request(
                'https://api.openai.com/v1/models/' + urllib.parse.quote(config['model']),
                headers={'Authorization': f"Bearer {config['key']}"},
            )
            return True, None
        except Exception as exc:
            return False, self._safe_reason(exc)

    def _validate_anthropic(self):
        config = self.config['anthropic']
        if not config['model']:
            return False, 'ANTHROPIC_MODEL is not configured'
        try:
            response = self._request(
                'https://api.anthropic.com/v1/models?limit=100',
                headers={'x-api-key': config['key'], 'anthropic-version': '2023-06-01'},
            )
            model_ids = {item.get('id') for item in response.get('data', [])}
            return (config['model'] in model_ids, None if config['model'] in model_ids else 'configured model is not available')
        except Exception as exc:
            return False, self._safe_reason(exc)

    def validate_startup(self):
        for provider in self.PROVIDERS:
            config = self.config[provider]
            if not config['key']:
                self._available[provider] = False
                self._reasons[provider] = 'no API key configured'
                self._codes[provider] = 'provider_unavailable'
                logger.info('%s is unavailable: no API key configured.', config['label'])
                continue
            try:
                if provider == 'openai':
                    available, reason = self._validate_openai()
                elif provider == 'gemini':
                    self._discover_gemini_model()
                    available, reason = True, None
                else:
                    available, reason = self._validate_anthropic()
            except Exception as exc:
                available, reason = False, self._safe_reason(exc)
            self._available[provider] = available
            self._reasons[provider] = reason
            self._codes[provider] = None if available else self._error_details(RuntimeError(reason))[0]
            if available:
                model = self.model_for(provider)
                logger.info('%s is available with model %s.', config['label'], model)
            else:
                logger.warning('%s is unavailable: %s.', config['label'], reason)
        logger.info('Available AI providers: %s', ', '.join(self.available_providers()) or 'none')

    def available_providers(self):
        return [provider for provider in self.PROVIDERS if self._available.get(provider)]

    def model_for(self, provider):
        return self._gemini_model if provider == 'gemini' else self.config[provider]['model']

    def provider_order(self, ui_model):
        preferred = self.UI_PROVIDER_MAP.get(ui_model)
        ordered = []
        for provider in (preferred, *self.PROVIDERS):
            if provider and provider not in ordered:
                ordered.append(provider)
        return ordered

    def _call_openai(self, prompt, model):
        response = self._request(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f"Bearer {self.config['openai']['key']}"},
            payload={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You generate strict JSON exam papers.'},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.2,
                'response_format': {'type': 'json_object'},
            },
        )
        choices = response.get('choices', [])
        return choices[0].get('message', {}).get('content') if choices else None

    def _call_gemini(self, prompt, model):
        url = 'https://generativelanguage.googleapis.com/v1beta/models/' + urllib.parse.quote(model) + ':generateContent?key=' + urllib.parse.quote(self.config['gemini']['key'])
        response = self._request(url, payload={
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'responseMimeType': 'application/json'},
        })
        candidates = response.get('candidates', [])
        parts = candidates[0].get('content', {}).get('parts', []) if candidates else []
        return ''.join(part.get('text', '') for part in parts)

    def _call_anthropic(self, prompt, model):
        response = self._request(
            'https://api.anthropic.com/v1/messages',
            headers={'x-api-key': self.config['anthropic']['key'], 'anthropic-version': '2023-06-01'},
            payload={'model': model, 'max_tokens': 4096, 'messages': [{'role': 'user', 'content': prompt}]},
        )
        return ''.join(part.get('text', '') for part in response.get('content', []))

    def generate(self, ui_model, prompt):
        failures = []
        seen = set()
        for provider in self.provider_order(ui_model):
            if provider in seen:
                continue
            seen.add(provider)
            if not self._available.get(provider):
                failures.append({
                    'provider': self.config[provider]['label'],
                    'error_code': self._codes.get(provider) or 'provider_unavailable',
                    'reason': self._reasons.get(provider) or 'provider is unavailable',
                })
                continue
            model = self.model_for(provider)
            try:
                call = getattr(self, f'_call_{provider}')
                content = call(prompt, model)
                if not isinstance(content, str) or not content.strip():
                    raise ProviderError(provider, 'empty response')
                cleaned = content.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
                return json.loads(cleaned), provider, model, failures
            except Exception as exc:
                code, reason = (exc.code, exc.reason) if isinstance(exc, ProviderError) else self._error_details(exc)
                failures.append({'provider': self.config[provider]['label'], 'error_code': code, 'reason': reason})
                self._available[provider] = False
                self._reasons[provider] = reason
                self._codes[provider] = code
                logger.exception('%s failed for paper generation: %s', self.config[provider]['label'], reason)
        raise ProviderError('all', json.dumps(failures))


_provider_manager = None


def get_ai_provider_manager():
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = AIProviderManager()
    return _provider_manager
