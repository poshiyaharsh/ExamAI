import json
import logging
import re
import threading
import time
from typing import List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .evaluation_config import (
    OLLAMA_BASE_URL,
    OLLAMA_FALLBACK_MODELS,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_TIMEOUT,
    canonicalize_model_tag,
)

logger = logging.getLogger(__name__)

# Single-execution lock to ensure evaluations run one at a time on CPU/RAM
_EVAL_INFERENCE_LOCK = threading.Lock()

# Cache for /api/tags
_TAGS_CACHE: List[str] = []
_TAGS_CACHE_TIME: float = 0.0
_TAGS_CACHE_TTL: float = 60.0  # seconds


def get_installed_ollama_models(base_url: str = OLLAMA_BASE_URL, timeout: int = 5, force_refresh: bool = False) -> List[str]:
    """
    Fetch installed Ollama model tags from GET /api/tags.
    Results are cached in memory for 60 seconds.
    If Ollama is unreachable, logs a warning and returns an empty list without crashing.
    """
    global _TAGS_CACHE, _TAGS_CACHE_TIME
    now = time.time()
    if not force_refresh and _TAGS_CACHE and (now - _TAGS_CACHE_TIME < _TAGS_CACHE_TTL):
        return list(_TAGS_CACHE)

    tags_url = f"{base_url.rstrip('/')}/api/tags"
    req = Request(tags_url, headers={'Accept': 'application/json'}, method='GET')
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            models = [m.get('name', '') for m in data.get('models', []) if m.get('name')]
            _TAGS_CACHE = models
            _TAGS_CACHE_TIME = now
            return list(models)
    except Exception as exc:
        logger.warning("Could not reach Ollama at %s to fetch tags: %s", tags_url, exc)
        return list(_TAGS_CACHE) if _TAGS_CACHE else []


def resolve_ollama_model(
    preferred_model: Optional[str] = None,
    base_url: str = OLLAMA_BASE_URL,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolves the best available Ollama model tag based on installed models in /api/tags:
    1. Canonicalized preferred_model if installed
    2. OLLAMA_MODEL if installed
    3. Each model in OLLAMA_FALLBACK_MODELS if installed
    4. First available installed model
    Returns (resolved_tag, None) on success, or (None, failure_reason) on failure.
    """
    installed = get_installed_ollama_models(base_url=base_url)
    if not installed:
        return None, f"Ollama is unreachable or has no installed models at {base_url}."

    installed_set = set(installed)

    # 1. Preferred model (e.g. from exam or request)
    if preferred_model:
        canonical_pref = canonicalize_model_tag(preferred_model)
        if canonical_pref in installed_set:
            return canonical_pref, None
        # Also check without tag or with tag variations
        for inst in installed:
            if inst.lower() == canonical_pref.lower() or inst.split(':')[0] == canonical_pref.split(':')[0]:
                return inst, None

    # 2. Primary configured OLLAMA_MODEL
    canonical_primary = canonicalize_model_tag(OLLAMA_MODEL)
    if canonical_primary in installed_set:
        return canonical_primary, None
    for inst in installed:
        if inst.lower() == canonical_primary.lower() or inst.split(':')[0] == canonical_primary.split(':')[0]:
            return inst, None

    # 3. Fallback models in priority order
    for fallback in OLLAMA_FALLBACK_MODELS:
        canonical_fallback = canonicalize_model_tag(fallback)
        if canonical_fallback in installed_set:
            return canonical_fallback, None
        for inst in installed:
            if inst.lower() == canonical_fallback.lower() or inst.split(':')[0] == canonical_fallback.split(':')[0]:
                return inst, None

    # 4. Any installed model as last resort
    if installed:
        return installed[0], None

    return None, f"No matching Ollama model found. Installed: {installed}"


def call_ollama_chat(
    model: str,
    messages: list,
    timeout: int = OLLAMA_TIMEOUT,
    num_ctx: int = OLLAMA_NUM_CTX,
    format: str = 'json',
    keep_alive: str = '10m',
    temperature: float = 0.0,
    base_url: str = OLLAMA_BASE_URL,
) -> str:
    """
    Calls POST /api/chat with stream=false, format='json', and keep_alive.
    Uses a thread lock to ensure one evaluation executes at a time.
    """
    chat_url = f"{base_url.rstrip('/')}/api/chat"
    payload_data = {
        'model': model,
        'messages': messages,
        'stream': False,
        'format': format,
        'keep_alive': keep_alive,
        'options': {
            'temperature': temperature,
            'num_ctx': num_ctx,
        },
    }
    payload = json.dumps(payload_data).encode('utf-8')
    req = Request(
        chat_url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    with _EVAL_INFERENCE_LOCK:
        try:
            with urlopen(req, timeout=timeout) as response:
                response_data = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace').strip()
            detail = f': {body}' if body else ''
            raise RuntimeError(f'Ollama returned HTTP {exc.code} for model tag "{model}"{detail}') from exc
        except URLError as exc:
            raise RuntimeError(f'Unable to connect to Ollama for model tag "{model}": {exc.reason}') from exc
        except TimeoutError as exc:
            raise RuntimeError(f'Ollama request timed out after {timeout}s for model tag "{model}".') from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f'Ollama returned an invalid JSON response for model tag "{model}".') from exc

    msg = response_data.get('message', {})
    content = msg.get('content', '') if isinstance(msg, dict) else ''
    if not content or not str(content).strip():
        raise RuntimeError(f'Ollama response for model tag "{model}" did not contain message content.')
    return str(content)


def call_ollama(model: str, prompt: str, timeout: int = 180, temperature: float = 0.4, num_predict: int = 2048) -> str:
    """
    Legacy generate endpoint caller used by paper generation.
    """
    # Auto-resolve or canonicalize tag if needed
    canonical_tag = canonicalize_model_tag(model)
    generate_url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"

    payload_data = {
        'model': canonical_tag,
        'prompt': prompt,
        'stream': False,
        'format': 'json',
        'keep_alive': '10m',
        'options': {
            'temperature': temperature,
            'num_predict': num_predict,
            'num_ctx': 4096,
        },
    }
    payload = json.dumps(payload_data).encode('utf-8')
    request = Request(
        generate_url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    with _EVAL_INFERENCE_LOCK:
        try:
            with urlopen(request, timeout=timeout) as response:
                response_data = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace').strip()
            detail = f': {body}' if body else ''
            raise RuntimeError(f'Ollama returned HTTP {exc.code} for model tag "{canonical_tag}"{detail}') from exc
        except URLError as exc:
            raise RuntimeError(f'Unable to connect to Ollama for model tag "{canonical_tag}": {exc.reason}') from exc
        except TimeoutError as exc:
            raise RuntimeError(f'Ollama request timed out for model tag "{canonical_tag}".') from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f'Ollama returned an invalid JSON response for model tag "{canonical_tag}".') from exc

    result = response_data.get('response')
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError(f'Ollama response for model tag "{canonical_tag}" did not contain generated text.')
    return result


def parse_json_safely(raw: str) -> dict:
    """
    Extracts and parses JSON object defensively from raw text,
    stripping markdown fences or leading/trailing chatter.
    """
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
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError('Output did not contain a valid JSON object.')
