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
