"""
Centralized Configuration for AI Paper Generator Module.
All settings, timeouts, model roles, and constants in one place.
Follows Phase 3 & Phase 4 specifications for under-10-minute generation.
"""
import os
from pathlib import Path
from django.conf import settings

BASE_DIR = Path(__file__).resolve().parent

# --- Ollama Connection Settings ---
OLLAMA_URL = getattr(settings, 'OLLAMA_BASE_URL', os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')).rstrip('/')
OLLAMA_BASE_URL = OLLAMA_URL

# Request timeout: MUST NEVER TIME OUT (set to None so generation is never cut off)
OLLAMA_REQUEST_TIMEOUT = None

# Single model loaded at a time to prevent VRAM swapping on 4 GB RTX 2050
OLLAMA_MAX_LOADED_MODELS = 1

# --- Model Role Assignments (Configurable & Dynamic) ---
# Phase 3 Required Roles:
MODEL_ROLES = {
    "mcq_generator":  "qwen3:4b",
    "fast_generator": "granite3.3:2b",   # True/False, Fill in the Blank
    "answer_writer":  "llama3.2:3b",     # Short and Long answers
    "validator":      "phi3:mini",
    "fallback":       "gemma3:4b",       # only for rare repairs
    "embedding":      "nomic-embed-text",
}

# Fallback sequence when a preferred model is unavailable
FALLBACK_CHAIN = ["qwen3:4b", "granite3.3:2b", "llama3.2:3b"]

# Models disallowed for question/answer generation
DISALLOWED_GENERATION_MODELS = ["smollm2:135m"]

# Backward compatibility defaults
DEFAULT_GENERATOR_MODEL = MODEL_ROLES["mcq_generator"]
DEFAULT_VALIDATOR_MODEL = MODEL_ROLES["validator"]
DEFAULT_FALLBACK_MODEL = MODEL_ROLES["fallback"]
PREFERRED_EMBEDDING_MODEL = MODEL_ROLES["embedding"]
MULTILINGUAL_EMBEDDING_MODEL = "bge-m3"
FALLBACK_LOCAL_EMBEDDER = 'sentence-transformers/all-MiniLM-L6-v2'

# --- Context & Memory Tuning for 4GB RTX 2050 (100% GPU) ---
NUM_CTX_BY_MODEL = {
    "granite3.3:2b": 4096,
    "llama3.2:3b": 2048,
    "qwen3:4b": 2048,
    "phi3:mini": 2048,
    "gemma3:4b": 2048,
}
DEFAULT_NUM_CTX = 2048
DEFAULT_SEED = 42
OLLAMA_KEEP_ALIVE = "30m"

# --- Temperatures per Section 5.10 ---
TEMPERATURE_BY_TYPE = {
    'MCQ': 0.3,
    'True/False': 0.2,
    'Fill in the Blank': 0.2,
    'Short Answer': 0.3,
    'Long Answer': 0.3,
    'Validator': 0.1,
}
DEFAULT_TEMPERATURE = 0.25

# --- Output Tokens & Batch Sizes per Section 2.1 & 5.10 ---
BASE_TOKENS_BY_TYPE = {
    'MCQ': 90,
    'True/False': 45,
    'Fill in the Blank': 45,
    'Short Answer': 145,
    'Long Answer': 370,
    'Validator': 25,
}

# Backward-compatible num predict map
NUM_PREDICT_BY_TYPE = {
    'MCQ': 95,
    'True/False': 50,
    'Fill in the Blank': 50,
    'Short Answer': 150,
    'Long Answer': 380,
}

# Batch sizes by type (Section 2.3 & 5.10)
BATCH_SIZE_BY_TYPE = {
    'MCQ': 10,
    'True/False': 15,
    'Fill in the Blank': 15,
    'Short Answer': 5,
    'Long Answer': 2,        # 1 to 2
    'Validator': 5,
}

# Time budget governor settings (Section 2.5)
TIME_BUDGET_SEC = 540        # 9 minutes (540 seconds)
TARGET_50_MARKS_SEC = 270    # 4.5 minutes

MAX_SLOT_RETRY_ATTEMPTS = 2  # At most 2 retries with main model, then 1 with fallback

# --- Multilingual Token Expansion & Model Routing ---
TOKEN_EXPANSION_FACTORS = {
    'en': 1.0,
    # Indic scripts (multi-byte UTF-8, subword token fragmentation)
    'hi': 2.8,
    'gu': 3.2,
    'mr': 2.8,
    'ta': 3.5,
    'bn': 3.0,
    'ur': 2.5,
    # Arabic / Semitic
    'ar': 2.2,
    # CJK
    'zh': 1.8,
    'ja': 2.0,
    # European Latin
    'fr': 1.15,
    'es': 1.15,
    'de': 1.25,
}
DEFAULT_TOKEN_EXPANSION_FACTOR = 1.0


def get_token_expansion_factor(language: str = 'en') -> float:
    """Returns token expansion factor for language; English is strictly 1.0."""
    if not language or language == 'en':
        return 1.0
    return TOKEN_EXPANSION_FACTORS.get(language, 1.8)


def get_num_predict_for_language(question_type: str, language: str = 'en') -> int:
    """Scales num_predict to prevent output truncation in non-Latin scripts."""
    base = NUM_PREDICT_BY_TYPE.get(question_type, 100)
    if not language or language == 'en':
        return base
    factor = get_token_expansion_factor(language)
    return int(base * factor)


def get_batch_size_for_language(question_type: str, language: str = 'en') -> int:
    """Safely adjusts batch size for Indic/Arabic to prevent VRAM swapping on RTX 2050."""
    base = BATCH_SIZE_BY_TYPE.get(question_type, 5)
    if not language or language == 'en':
        return base
    factor = get_token_expansion_factor(language)
    if factor >= 2.0:
        return max(1, base // 2)
    return base


def get_embedding_model_for_language(language: str = 'en') -> str:
    """Returns bge-m3 for non-English, preserving nomic-embed-text for English."""
    if language and language != 'en':
        return MULTILINGUAL_EMBEDDING_MODEL
    return PREFERRED_EMBEDDING_MODEL


def get_model_roles_for_language(language: str = 'en') -> dict:
    """
    Selects optimal installed models by language.
    For English: keeps existing MODEL_ROLES 100% byte-for-byte identical.
    For Indic & Arabic: gemma3:4b (proved 10/10 in empirical probe).
    For CJK & European: qwen3:4b and gemma3:4b.
    """
    if not language or language == 'en':
        return MODEL_ROLES

    # Indic languages and Arabic
    if language in ('hi', 'gu', 'mr', 'ta', 'bn', 'ur', 'ar'):
        return {
            "mcq_generator":  "gemma3:4b",
            "fast_generator": "gemma3:4b",
            "answer_writer":  "gemma3:4b",
            "validator":      "gemma3:4b",
            "fallback":       "qwen3:4b",
            "embedding":      MULTILINGUAL_EMBEDDING_MODEL,
        }

    # CJK and European languages
    if language in ('zh', 'ja', 'fr', 'es', 'de'):
        return {
            "mcq_generator":  "qwen3:4b",
            "fast_generator": "qwen3:4b",
            "answer_writer":  "qwen3:4b",
            "validator":      "gemma3:4b",
            "fallback":       "gemma3:4b",
            "embedding":      MULTILINGUAL_EMBEDDING_MODEL,
        }

    # Default fallback for other languages
    return {
        "mcq_generator":  "gemma3:4b",
        "fast_generator": "gemma3:4b",
        "answer_writer":  "gemma3:4b",
        "validator":      "gemma3:4b",
        "fallback":       "qwen3:4b",
        "embedding":      MULTILINGUAL_EMBEDDING_MODEL,
    }


# --- RAG Settings (Phase 4.5 & Phase 5) ---
CHUNK_SIZE_TOKENS = 650      # 500-800 tokens
CHUNK_OVERLAP_TOKENS = 100
TOP_K_RETRIEVAL = 3          # Phase 4.5: top-k of 3 chunks of about 400 tokens each

# Storage path for local vector indices (separated per job)
RAG_STORAGE_DIR = BASE_DIR / 'rag' / 'storage'
RAG_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# --- Logging Directory & Rotation (Phase 8) ---
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE_GENERATION = LOGS_DIR / 'generation.log'
LOG_FILE_MODEL_ERRORS = LOGS_DIR / 'model_errors.log'
LOG_FILE_VALIDATION = LOGS_DIR / 'validation.log'
LOG_FILE_RAG = LOGS_DIR / 'rag.log'
LOG_FILE_TIMING = LOGS_DIR / 'timing.log'

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 5

# --- Supported Question Types ---
QUESTION_TYPES = [
    'MCQ',
    'True/False',
    'Fill in the Blank',
    'Short Answer',
    'Long Answer',
]

DIFFICULTY_LEVELS = ['Easy', 'Medium', 'Hard']
