import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Base configuration defaults
OLLAMA_BASE_URL: str = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL: str = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b-instruct').strip()
OLLAMA_FALLBACK_MODELS: List[str] = [
    m.strip()
    for m in os.getenv('OLLAMA_FALLBACK_MODELS', 'llama3.2:3b,phi3:mini').split(',')
    if m.strip()
]
OLLAMA_REQUEST_TIMEOUT: int = int(os.getenv('OLLAMA_REQUEST_TIMEOUT', os.getenv('OLLAMA_TIMEOUT', '240')))
OLLAMA_TIMEOUT: int = OLLAMA_REQUEST_TIMEOUT
OLLAMA_CALL_TIMEOUT: int = int(os.getenv('OLLAMA_CALL_TIMEOUT', '120'))
PAPER_JOB_MAX_SECONDS: int = int(os.getenv('PAPER_JOB_MAX_SECONDS', '2700'))
OLLAMA_JOB_TIMEOUT: int = PAPER_JOB_MAX_SECONDS
OLLAMA_NUM_CTX: int = int(os.getenv('OLLAMA_NUM_CTX', '4096'))
OLLAMA_KEEP_ALIVE: str = os.getenv('OLLAMA_KEEP_ALIVE', '1h').strip()
OLLAMA_TEMPERATURE: float = float(os.getenv('OLLAMA_TEMPERATURE', '0.3'))
OLLAMA_MAX_PARALLEL: int = int(os.getenv('OLLAMA_MAX_PARALLEL', '1'))
OLLAMA_MAX_BATCH_SIZE: int = int(os.getenv('OLLAMA_MAX_BATCH_SIZE', '5'))
OLLAMA_LONG_ANSWER_BATCH_SIZE: int = int(os.getenv('OLLAMA_LONG_ANSWER_BATCH_SIZE', '1'))
OLLAMA_LONG_ANSWER_SINGLE_PASS: bool = os.getenv('OLLAMA_LONG_ANSWER_SINGLE_PASS', 'true').strip().lower() in ('true', '1', 'yes')
OLLAMA_MAX_RETRIES: int = int(os.getenv('OLLAMA_MAX_RETRIES', '2'))
OLLAMA_WARMUP_ON_INIT: bool = os.getenv('OLLAMA_WARMUP_ON_INIT', 'true').strip().lower() in ('true', '1', 'yes')
FACULTY_DEBUG_MODE: bool = os.getenv('FACULTY_DEBUG_MODE', 'false').strip().lower() in ('true', '1', 'yes')
SYLLABUS_CACHE_TTL: int = int(os.getenv('SYLLABUS_CACHE_TTL', '3600'))

# Model Routing Configuration
ENABLE_MODEL_ROUTING: bool = os.getenv('ENABLE_MODEL_ROUTING', 'false').strip().lower() in ('true', '1', 'yes')
OLLAMA_OBJECTIVE_MODEL: str = os.getenv('OLLAMA_OBJECTIVE_MODEL', 'qwen2.5:3b-instruct').strip()
OLLAMA_SUBJECTIVE_MODEL: str = os.getenv('OLLAMA_SUBJECTIVE_MODEL', 'qwen2.5:3b-instruct').strip()

EVAL_PROVIDER_ORDER: List[str] = [
    p.strip().lower()
    for p in os.getenv('EVAL_PROVIDER_ORDER', 'ollama,rules').split(',')
    if p.strip()
]

CLOUD_PROVIDER: str = os.getenv('CLOUD_PROVIDER', 'none').strip().lower()
CLOUD_API_KEY: str = os.getenv('CLOUD_API_KEY', '').strip()
CLOUD_MODEL: str = os.getenv('CLOUD_MODEL', '').strip()

# Canonical alias mapping from frontend/UI keys to installed Ollama tags
TAG_ALIASES = {
    'qwen2.5-3b': 'qwen2.5:3b-instruct',
    'ollama-qwen2.5-3b': 'qwen2.5:3b-instruct',
    'qwen2.5:3b': 'qwen2.5:3b-instruct',
    'qwen2.5:3b-instruct': 'qwen2.5:3b-instruct',
    'llama3.2-3b': 'llama3.2:3b',
    'ollama-llama3.2-3b': 'llama3.2:3b',
    'llama3.2:3b': 'llama3.2:3b',
    'phi3-mini': 'phi3:mini',
    'ollama-phi3-mini': 'phi3:mini',
    'phi3': 'phi3:mini',
    'phi3:mini': 'phi3:mini',
}


def canonicalize_model_tag(tag: Any) -> str:
    """Normalize model tag or UI key to canonical Ollama tag, logging a warning if normalized."""
    if isinstance(tag, (tuple, list)):
        tag = tag[0] if tag else None
    if not tag:
        return OLLAMA_MODEL
    clean = str(tag).strip().lower()
    canonical = TAG_ALIASES.get(clean, TAG_ALIASES.get(clean.replace(':', '-'), clean))
    if canonical != clean and clean not in TAG_ALIASES.values():
        logger.warning("Normalizing model tag '%s' to '%s'", tag, canonical)
    return canonical


def route_model_for_type(question_type: str, user_selected_model: Optional[str] = None) -> str:
    """
    Resolves model tag for a given question type.
    If ENABLE_MODEL_ROUTING is True, routes objective questions to OLLAMA_OBJECTIVE_MODEL
    and subjective questions to OLLAMA_SUBJECTIVE_MODEL.
    Otherwise, respects user_selected_model (falling back to OLLAMA_MODEL).
    """
    if not ENABLE_MODEL_ROUTING and user_selected_model:
        return canonicalize_model_tag(user_selected_model)

    norm_type = str(question_type or '').strip().lower()
    if ENABLE_MODEL_ROUTING:
        if norm_type in {'mcq', 'true_false', 'truefalse', 'fill_blank', 'fillblank'}:
            return canonicalize_model_tag(OLLAMA_OBJECTIVE_MODEL)
        return canonicalize_model_tag(OLLAMA_SUBJECTIVE_MODEL)

    return canonicalize_model_tag(user_selected_model or OLLAMA_MODEL)
