import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OLLAMA_GENERATE_URL = 'http://localhost:11434/api/generate'
logger = logging.getLogger(__name__)
_request_payload_logged = False


def call_ollama(model: str, prompt: str, timeout=180, temperature=0.4, num_predict=4096) -> str:
    global _request_payload_logged
    logger.info('Calling Ollama model tag=%s url=%s', model, OLLAMA_GENERATE_URL)
    payload_data = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'format': 'json',
        'options': {'temperature': temperature, 'num_predict': num_predict},
    }
    if not _request_payload_logged:
        logger.warning('Ollama request payload: %s', payload_data)
        _request_payload_logged = True
    payload = json.dumps(payload_data).encode('utf-8')
    request = Request(
        OLLAMA_GENERATE_URL,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            response_data = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace').strip()
        detail = f': {body}' if body else ''
        raise RuntimeError(f'Ollama returned HTTP {exc.code} for model tag "{model}"{detail}') from exc
    except URLError as exc:
        raise RuntimeError(f'Unable to connect to Ollama for model tag "{model}": {exc.reason}') from exc
    except TimeoutError as exc:
        raise RuntimeError(f'Ollama request timed out for model tag "{model}".') from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'Ollama returned an invalid JSON response for model tag "{model}".') from exc

    result = response_data.get('response')
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError(f'Ollama response for model tag "{model}" did not contain generated text.')
    return result


def parse_json_safely(raw: str) -> dict:
    cleaned = str(raw or '').strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned).strip()

    candidates = [cleaned]
    match = re.search(r'\{.*\}', cleaned, flags=re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError('Ollama output did not contain a valid JSON object.')
