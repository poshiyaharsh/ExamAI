"""
Single source of truth for Ollama models registry, normalization, resolution,
and metadata querying.
"""
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import requests
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .evaluation_config import (
    OLLAMA_BASE_URL,
    OLLAMA_FALLBACK_MODELS,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_REQUEST_TIMEOUT,
    canonicalize_model_tag,
)

logger = logging.getLogger(__name__)

# Thread-safe in-memory cache for /api/tags
_TAGS_CACHE_LOCK = threading.Lock()
_TAGS_CACHE: List[str] = []
_TAGS_CACHE_DETAILS: List[Dict[str, Any]] = []
_TAGS_CACHE_TIME: float = 0.0
_TAGS_CACHE_TTL: float = 60.0  # seconds

# Legacy to canonical tag map
LEGACY_MODEL_MAP: Dict[str, str] = {
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

# Display labels for installed models
FRIENDLY_LABELS: Dict[str, str] = {
    'qwen2.5:3b-instruct': 'Qwen 2.5 3B Instruct (Primary / Recommended)',
    'llama3.2:3b': 'Llama 3.2 3B (Fallback 1)',
    'phi3:mini': 'Phi-3 Mini (Fallback 2)',
}


class OllamaModelNotFoundError(ValueError, RuntimeError):
    def __init__(self, model_tag: str, installed: Optional[List[str]] = None):
        self.model_tag = model_tag
        self.installed = installed or []
        msg = f"Model '{model_tag}' is not installed in Ollama."
        if self.installed:
            msg += f" Installed: {self.installed}"
        super().__init__(msg)


class OllamaConnectionError(RuntimeError):
    pass


def get_installed_models_with_reason(
    base_url: str = OLLAMA_BASE_URL,
    timeout: int = 5,
    force_refresh: bool = False,
) -> Tuple[List[str], Optional[str]]:
    """
    Calls GET {OLLAMA_BASE_URL}/api/tags, cached for 60 seconds.
    Returns (installed_tags, error_reason).
    If Ollama is unreachable, returns ([], error_message) and never crashes.
    """
    global _TAGS_CACHE, _TAGS_CACHE_DETAILS, _TAGS_CACHE_TIME
    now = time.time()
    with _TAGS_CACHE_LOCK:
        if not force_refresh and _TAGS_CACHE and (now - _TAGS_CACHE_TIME < _TAGS_CACHE_TTL):
            return list(_TAGS_CACHE), None

    tags_url = f"{base_url.rstrip('/')}/api/tags"
    try:
        resp = requests.get(tags_url, headers={'Accept': 'application/json'}, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            raw_models = data.get('models', [])
            model_tags = [m.get('name', '') for m in raw_models if m.get('name')]
            with _TAGS_CACHE_LOCK:
                _TAGS_CACHE = model_tags
                _TAGS_CACHE_DETAILS = raw_models
                _TAGS_CACHE_TIME = now
            return list(model_tags), None
        reason = f"Ollama returned HTTP status {resp.status_code}"
    except Exception as exc:
        reason = f"Could not reach Ollama at {tags_url}: {exc}"
        logger.warning(reason)

    if force_refresh:
        return [], reason

    with _TAGS_CACHE_LOCK:
        cached = list(_TAGS_CACHE) if _TAGS_CACHE else []
    return cached, reason


def get_installed_models(
    base_url: str = OLLAMA_BASE_URL,
    timeout: int = 5,
    force_refresh: bool = False,
) -> List[str]:
    """
    Calls GET {OLLAMA_BASE_URL}/api/tags, cached for 60 seconds.
    Returns exact tags. If Ollama is unreachable, returns empty list (never crashes).
    """
    models, _ = get_installed_models_with_reason(base_url=base_url, timeout=timeout, force_refresh=force_refresh)
    return models


def get_installed_models_details(
    base_url: str = OLLAMA_BASE_URL,
    timeout: int = 5,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """Returns the full raw models list from /api/tags."""
    get_installed_models(base_url=base_url, timeout=timeout, force_refresh=force_refresh)
    with _TAGS_CACHE_LOCK:
        return list(_TAGS_CACHE_DETAILS)


def normalize_model_name(name: Optional[str], installed: Optional[List[str]] = None) -> str:
    """
    Accepts legacy identifiers and maps them to real installed tags:
      "qwen2.5-3b" -> "qwen2.5:3b-instruct"
      "llama3.2-3b" -> "llama3.2:3b"
      "phi3-mini" -> "phi3:mini"
    Also handles generic "name-size" patterns to match installed tags.
    Logs a warning whenever normalization happens.
    """
    if not name:
        return OLLAMA_MODEL

    clean = str(name).strip()
    clean_lower = clean.lower()

    # Exact known mapping
    if clean_lower in LEGACY_MODEL_MAP:
        target = LEGACY_MODEL_MAP[clean_lower]
        if target != clean:
            logger.warning("Normalizing legacy model '%s' to canonical '%s'", name, target)
        return target

    # Strip 'ollama-' prefix if present
    stripped = clean_lower.replace('ollama-', '')
    if stripped in LEGACY_MODEL_MAP:
        target = LEGACY_MODEL_MAP[stripped]
        logger.warning("Normalizing model '%s' with prefix to canonical '%s'", name, target)
        return target

    # Generic pattern matching against installed tags
    if installed is None:
        installed = get_installed_models()

    if clean in installed:
        return clean

    for inst in installed:
        if inst.lower() == clean_lower:
            return inst

    # Generic regex for "name-size" e.g. "qwen2.5-3b", "llama3.2-3b", "mistral-7b"
    parts = [p for p in re.split(r'[-_:]', stripped) if p]
    if len(parts) >= 2 and installed:
        lead, size = parts[0], parts[1]
        for inst in installed:
            inst_lower = inst.lower()
            if lead in inst_lower and size in inst_lower:
                logger.warning("Fuzzy matched model '%s' to installed tag '%s'", name, inst)
                return inst

    if len(parts) == 2 and not any(':' in p for p in parts):
        cand = f"{parts[0]}:{parts[1]}"
        logger.warning("Mapped generic model '%s' to '%s'", name, cand)
        return cand

    return clean


def resolve_model(
    requested: Optional[str] = None,
    base_url: str = OLLAMA_BASE_URL,
    force_refresh: bool = False,
    strict: bool = False,
) -> str:
    """
    Resolves requested model:
    1. Returns requested (normalized) if installed.
    2. Else default OLLAMA_MODEL if installed.
    3. Else first fallback in OLLAMA_FALLBACK_MODELS that is installed.
    4. Else raises friendly OllamaModelNotFoundError listing installed models.
    """
    installed = get_installed_models(base_url=base_url, force_refresh=force_refresh)
    if not installed:
        raise OllamaConnectionError(f"Ollama is unreachable or has no models installed at {base_url}.")

    installed_set = set(installed)

    if requested:
        norm = normalize_model_name(requested, installed=installed)
        if norm in installed_set:
            return norm
        for inst in installed:
            if inst.lower() == norm.lower():
                return inst
        if strict:
            raise OllamaModelNotFoundError(requested, installed=installed)

    # Check default model
    norm_default = normalize_model_name(OLLAMA_MODEL, installed=installed)
    if norm_default in installed_set:
        return norm_default

    # Check fallback models
    for fb in OLLAMA_FALLBACK_MODELS:
        norm_fb = normalize_model_name(fb, installed=installed)
        if norm_fb in installed_set:
            logger.info("Resolved to fallback model '%s' (requested: '%s')", norm_fb, requested)
            return norm_fb

    raise OllamaModelNotFoundError(requested or OLLAMA_MODEL, installed=installed)


def format_bytes_to_readable(size_bytes: int) -> str:
    """Formats bytes into human readable string (e.g. 1.9 GB)."""
    if not size_bytes or size_bytes <= 0:
        return ""
    gb = size_bytes / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.1f} GB"
    mb = size_bytes / (1024 ** 2)
    return f"{mb:.0f} MB"


def get_available_models_metadata(base_url: str = OLLAMA_BASE_URL) -> List[Dict[str, Any]]:
    """
    Returns installed models formatted with friendly label, size, parameter_size,
    and a recommended flag.
    """
    raw_details = get_installed_models_details(base_url=base_url)
    installed_tags = get_installed_models(base_url=base_url)
    if not installed_tags and raw_details:
        installed_tags = [m.get('name') for m in raw_details if m.get('name')]

    results = []
    seen = set()

    # Priority order: primary first, then fallbacks, then others
    preferred_order = [OLLAMA_MODEL] + OLLAMA_FALLBACK_MODELS

    def _sort_key(tag: str) -> int:
        for idx, pref in enumerate(preferred_order):
            if tag.lower() == pref.lower() or normalize_model_name(pref) == tag:
                return idx
        return 99

    sorted_tags = sorted(installed_tags, key=_sort_key)

    details_by_name = {m.get('name'): m for m in raw_details if m.get('name')}

    for tag in sorted_tags:
        if tag in seen:
            continue
        seen.add(tag)
        detail = details_by_name.get(tag, {})
        size_bytes = detail.get('size', 0)
        readable_size = format_bytes_to_readable(size_bytes)
        details_obj = detail.get('details', {})
        param_size = details_obj.get('parameter_size', '')

        # Label logic
        label = FRIENDLY_LABELS.get(tag)
        if not label:
            display_name = tag.split(':')[0].capitalize()
            label = f"{display_name} ({readable_size or param_size or 'Local'})"

        is_recommended = (tag == OLLAMA_MODEL or tag == 'qwen2.5:3b-instruct')

        results.append({
            'name': tag,
            'label': label,
            'size': readable_size,
            'parameter_size': param_size,
            'recommended': is_recommended,
            'is_recommended': is_recommended,
            'is_installed': True,
        })

    return results
