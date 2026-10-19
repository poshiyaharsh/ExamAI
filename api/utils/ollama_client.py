import json
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union
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


def call_ollama(
    model: str,
    prompt: str,
    timeout: Optional[int] = None,
    temperature: Optional[float] = None,
    num_predict: int = 2048,
    num_ctx: Optional[int] = None,
    format_schema: Optional[Union[dict, str]] = None,
    keep_alive: Optional[str] = None,
) -> str:
    """
    Calls Ollama generate endpoint with structured JSON schema support,
    dynamic options, and guarded concurrency.
    """
    from .evaluation_config import (
        OLLAMA_KEEP_ALIVE,
        OLLAMA_NUM_CTX,
        OLLAMA_TEMPERATURE,
        OLLAMA_TIMEOUT,
        FACULTY_DEBUG_MODE,
    )

    canonical_tag = canonicalize_model_tag(model)
    generate_url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"

    eff_temp = temperature if temperature is not None else OLLAMA_TEMPERATURE
    eff_keep_alive = keep_alive or OLLAMA_KEEP_ALIVE

    # Right-size dynamic context: min(4096, max(1024, prompt + predict + margin))
    prompt_token_est = max(256, len(prompt) // 4)
    eff_num_ctx = num_ctx or min(4096, max(1024, prompt_token_est + num_predict + 256))

    # Dynamic timeout based on expected output tokens
    eff_timeout = timeout or max(OLLAMA_TIMEOUT, int(num_predict * 0.15) + 60)

    # Format parameter: structured schema dict or 'json'
    eff_format = format_schema if format_schema is not None else 'json'

    payload_data = {
        'model': canonical_tag,
        'prompt': prompt,
        'stream': False,
        'format': eff_format,
        'keep_alive': eff_keep_alive,
        'options': {
            'temperature': eff_temp,
            'num_predict': num_predict,
            'num_ctx': eff_num_ctx,
        },
    }
    payload = json.dumps(payload_data).encode('utf-8')
    request = Request(
        generate_url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    t_start = time.time()
    with _EVAL_INFERENCE_LOCK:
        try:
            with urlopen(request, timeout=eff_timeout) as response:
                response_data = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace').strip()
            detail = f': {body}' if body else ''
            raise RuntimeError(f'Ollama returned HTTP {exc.code} for model tag "{canonical_tag}"{detail}') from exc
        except URLError as exc:
            raise RuntimeError(f'Unable to connect to Ollama for model tag "{canonical_tag}": {exc.reason}') from exc
        except TimeoutError as exc:
            raise RuntimeError(f'Ollama request timed out after {eff_timeout}s for model tag "{canonical_tag}".') from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f'Ollama returned an invalid JSON response for model tag "{canonical_tag}".') from exc

    duration = time.time() - t_start
    result = response_data.get('response', '')
    done_reason = response_data.get('done_reason', 'stop')
    eval_count = response_data.get('eval_count', 0)

    if done_reason == 'length':
        logger.warning(
            "Ollama output was truncated by token limit for model=%s (eval_count=%s, limit=%s)",
            canonical_tag, eval_count, num_predict
        )

    if FACULTY_DEBUG_MODE:
        snippet = (result[:300] if result else '').replace('\n', ' ')
        logger.info(
            "Ollama call model=%s tokens=%s duration=%.2fs done_reason=%s snippet=%.300s",
            canonical_tag, eval_count, duration, done_reason, snippet
        )
    else:
        logger.info(
            "Ollama call completed model=%s tokens=%s duration=%.2fs done_reason=%s",
            canonical_tag, eval_count, duration, done_reason
        )

    if not isinstance(result, str) or not result.strip():
        raise RuntimeError(f'Ollama response for model tag "{canonical_tag}" did not contain generated text.')
    return result


def warmup_ollama_model(model_tag: Optional[str] = None, base_url: str = OLLAMA_BASE_URL) -> bool:
    """
    Sends a minimal 1-token query to warm up and keep the model loaded in GPU VRAM for 30 minutes.
    """
    canonical_tag = canonicalize_model_tag(model_tag)
    generate_url = f"{base_url.rstrip('/')}/api/generate"
    payload = json.dumps({
        'model': canonical_tag,
        'prompt': 'ping',
        'stream': False,
        'keep_alive': '30m',
        'options': {'num_predict': 1, 'num_ctx': 512}
    }).encode('utf-8')
    req = Request(generate_url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.debug("Ollama warmup ping failed for %s: %s", canonical_tag, exc)
        return False


def parse_json_safely(raw: str) -> dict:
    """
    Extracts and parses JSON object or array defensively from raw text.
    Uses clean regex candidate extraction followed by json_repair.
    Never uses eval.
    """
    cleaned = str(raw or '').strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned).strip()

    # 1. Direct parse attempt
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {'questions': parsed}
    except Exception:
        pass

    # 2. Extract balanced JSON substring via regex
    candidates = []
    obj_match = re.search(r'(\{[\s\S]*\})', cleaned)
    if obj_match:
        candidates.append(obj_match.group(1))

    arr_match = re.search(r'(\[[\s\S]*\])', cleaned)
    if arr_match:
        candidates.append(arr_match.group(1))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {'questions': parsed}
        except Exception:
            continue

    # 3. Tolerant parsing with json_repair
    try:
        import json_repair
        repaired = json_repair.repair_json(cleaned, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
        if isinstance(repaired, list):
            return {'questions': repaired}
    except Exception:
        pass

    for candidate in candidates:
        try:
            import json_repair
            repaired = json_repair.repair_json(candidate, return_objects=True)
            if isinstance(repaired, dict):
                return repaired
            if isinstance(repaired, list):
                return {'questions': repaired}
        except Exception:
            pass

    raise ValueError('Output did not contain a valid JSON object.')
