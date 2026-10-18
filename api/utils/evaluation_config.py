import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

# Base configuration defaults
OLLAMA_BASE_URL: str = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL: str = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b-instruct').strip()
OLLAMA_FALLBACK_MODELS: List[str] = [
    m.strip()
    for m in os.getenv('OLLAMA_FALLBACK_MODELS', 'llama3.2:3b,phi3:mini').split(',')
    if m.strip()
]
OLLAMA_TIMEOUT: int = int(os.getenv('OLLAMA_TIMEOUT', '180'))
OLLAMA_NUM_CTX: int = int(os.getenv('OLLAMA_NUM_CTX', '4096'))
OLLAMA_KEEP_ALIVE: str = os.getenv('OLLAMA_KEEP_ALIVE', '5m').strip()
OLLAMA_TEMPERATURE: float = float(os.getenv('OLLAMA_TEMPERATURE', '0.2'))
OLLAMA_MAX_PARALLEL: int = int(os.getenv('OLLAMA_MAX_PARALLEL', '1'))
OLLAMA_MAX_BATCH_SIZE: int = int(os.getenv('OLLAMA_MAX_BATCH_SIZE', '4'))
OLLAMA_LONG_ANSWER_BATCH_SIZE: int = int(os.getenv('OLLAMA_LONG_ANSWER_BATCH_SIZE', '1'))
OLLAMA_MAX_RETRIES: int = int(os.getenv('OLLAMA_MAX_RETRIES', '2'))
FACULTY_DEBUG_MODE: bool = os.getenv('FACULTY_DEBUG_MODE', 'false').strip().lower() in ('true', '1', 'yes')
SYLLABUS_CACHE_TTL: int = int(os.getenv('SYLLABUS_CACHE_TTL', '3600'))

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


def canonicalize_model_tag(tag: Optional[str]) -> str:
    """Normalize model tag or UI key to canonical Ollama tag."""
    if not tag:
        return OLLAMA_MODEL
    clean = str(tag).strip().lower()
    return TAG_ALIASES.get(clean, TAG_ALIASES.get(clean.replace(':', '-'), clean))
