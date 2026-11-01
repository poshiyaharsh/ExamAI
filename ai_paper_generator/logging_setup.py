"""
Logging Setup with Rotating File Handlers (5MB, 5 backups).
Provides dedicated loggers for:
- generation.log
- model_errors.log
- validation.log
- rag.log
- timing.log
Also integrates database logging into GenerationLog table.
"""
import logging
from logging.handlers import RotatingFileHandler
from .config import (
    LOG_FILE_GENERATION,
    LOG_FILE_MODEL_ERRORS,
    LOG_FILE_VALIDATION,
    LOG_FILE_RAG,
    LOG_FILE_TIMING,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)

FORMATTER = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] [job=%(job_id)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

TIMING_FORMATTER = logging.Formatter(
    '[%(asctime)s] [TIMING] [job=%(job_id)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class JobContextFilter(logging.Filter):
    """Ensures job_id is always present in log records."""
    def filter(self, record):
        if not hasattr(record, 'job_id'):
            record.job_id = getattr(record, 'job_id', 'N/A')
        return True


def _create_rotating_logger(name, file_path, formatter=FORMATTER):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Avoid duplicate handlers on reload
    if not logger.handlers:
        handler = RotatingFileHandler(
            file_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        handler.setFormatter(formatter)
        handler.addFilter(JobContextFilter())
        logger.addHandler(handler)

    return logger


gen_logger = _create_rotating_logger('ai_paper_generator.generation', LOG_FILE_GENERATION)
model_error_logger = _create_rotating_logger('ai_paper_generator.model_errors', LOG_FILE_MODEL_ERRORS)
val_logger = _create_rotating_logger('ai_paper_generator.validation', LOG_FILE_VALIDATION)
rag_logger = _create_rotating_logger('ai_paper_generator.rag', LOG_FILE_RAG)
timing_logger = _create_rotating_logger('ai_paper_generator.timing', LOG_FILE_TIMING, formatter=TIMING_FORMATTER)


def setup_generation_loggers():
    """Initializes the loggers and ensures log files exist."""
    for path in [LOG_FILE_GENERATION, LOG_FILE_MODEL_ERRORS, LOG_FILE_VALIDATION, LOG_FILE_RAG, LOG_FILE_TIMING]:
        if not path.exists():
            path.touch()


def log_timing(stage: str, duration_seconds: float, job_id=None, details=None):
    """Logs the execution timing of every pipeline stage into timing.log."""
    extra = {'job_id': job_id or 'SYSTEM'}
    msg = f"Stage '{stage}' completed in {duration_seconds:.2f}s."
    if details:
        msg += f" Details: {details}"
    timing_logger.info(msg, extra=extra)


def log_timing_metric(
    job_id=None,
    model: str = "",
    stage: str = "",
    batch_size: int = 1,
    prompt_tokens: int = 0,
    output_tokens: int = 0,
    tps: float = 0.0,
    load_time_sec: float = 0.0,
    total_time_sec: float = 0.0,
    done_reason: str = ""
):
    """
    Step 1.1 metric logger: logs model, stage, batch size, prompt tokens, output tokens,
    tokens per second, and load time into timing.log directly from Ollama response fields.
    """
    extra = {'job_id': job_id or 'SYSTEM'}
    msg = (
        f"model={model} | stage={stage} | batch_size={batch_size} | "
        f"prompt_tokens={prompt_tokens} | output_tokens={output_tokens} | "
        f"tps={tps:.1f} tok/s | load_time={load_time_sec:.2f}s | "
        f"total_time={total_time_sec:.2f}s | done_reason={done_reason}"
    )
    timing_logger.info(msg, extra=extra)


def log_event(category, message, job_id=None, level=logging.INFO, slot_number=None, model_name='', details=None, faculty=None, institution=None):
    """
    Unified logging function that writes to both rotating log files and GenerationLog DB model.
    """
    extra = {'job_id': job_id or 'SYSTEM'}
    cat = category.upper()

    # Normalize string log level to logging int constant
    if isinstance(level, str):
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARN': logging.WARNING,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
        }
        level = level_map.get(level.upper(), logging.INFO)

    # File logging
    if cat == 'GENERATION':
        gen_logger.log(level, message, extra=extra)
    elif cat in ('MODEL_ERROR', 'MODEL_CRASH', 'TIMEOUT'):
        model_error_logger.log(level, f"[{model_name or 'N/A'}] {message}", extra=extra)
    elif cat in ('VALIDATION', 'RULE_FAIL', 'AI_CHECK_FAIL'):
        val_logger.log(level, f"[Slot {slot_number or 'N/A'}] {message}", extra=extra)
    elif cat in ('RAG', 'RETRIEVAL', 'EXTRACTION'):
        rag_logger.log(level, message, extra=extra)
    elif cat == 'TIMING':
        timing_logger.log(level, message, extra=extra)
    else:
        gen_logger.log(level, message, extra=extra)

    # Database logging (async-safe / non-blocking)
    try:
        from .models import GenerationLog
        db_level = 'INFO'
        if level >= logging.ERROR:
            db_level = 'ERROR'
        elif level >= logging.WARNING:
            db_level = 'WARNING'
        elif level <= logging.DEBUG:
            db_level = 'DEBUG'

        GenerationLog.objects.create(
            job_id=job_id if (job_id and isinstance(job_id, int)) else None,
            faculty=faculty,
            institution=institution,
            level=db_level,
            stage=cat,
            model_name=model_name or '',
            slot_number=slot_number,
            message=message[:2000],
            details=details or {}
        )
    except Exception:
        # Never crash main generation thread because of a logging error
        pass
