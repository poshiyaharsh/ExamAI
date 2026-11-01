"""
Ollama Client for local inference.
Calls local Ollama instance (http://localhost:11434).
Zero-timeout policy: request timeout is None so generation is never cut off.
Supports streaming, think: False for qwen3, strip <think>...</think>, and logging calls > 120s.
"""
import re
import json
import time
import logging
import requests
from typing import Any, Dict, List, Optional
from .config import (
    OLLAMA_BASE_URL,
    OLLAMA_REQUEST_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    DEFAULT_NUM_CTX,
    NUM_CTX_BY_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_SEED,
)
from .logging_setup import log_event, log_timing_metric

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Base exception for Ollama interactions."""
    pass


class OllamaNotRunningError(OllamaError):
    """Raised when Ollama server is unreachable."""
    pass


class OllamaModelNotFoundError(OllamaError):
    """Raised when requested model is not installed."""
    pass


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an error or unparseable output."""
    pass


class OllamaTruncationError(OllamaError):
    """Raised when Ollama generation cuts off due to num_predict length limit."""
    def __init__(self, message, partial_response="", num_predict=0):
        super().__init__(message)
        self.partial_response = partial_response
        self.num_predict = num_predict


def strip_thinking(text: str) -> str:
    """Strips <think>...</think> reasoning blocks from text if present."""
    if not text:
        return ""
    # Remove complete <think>...</think> blocks
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.DOTALL)
    # Remove dangling opening <think> tag if model was truncated inside thinking
    if '<think>' in cleaned and '</think>' not in cleaned:
        cleaned = cleaned.split('<think>')[0]
    return cleaned.strip()


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
        })

    def check_health(self) -> bool:
        """Returns True if Ollama service is reachable."""
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_installed_models_with_details(self) -> List[Dict[str, Any]]:
        """Returns list of raw model objects from Ollama /api/tags."""
        url = f"{self.base_url}/api/tags"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                raise OllamaNotRunningError(f"Ollama returned HTTP {resp.status_code}")
            data = resp.json()
            return data.get('models', [])
        except requests.exceptions.ConnectionError as exc:
            msg = "Ollama is not running. Please start Ollama (http://localhost:11434) and try again."
            log_event('MODEL_ERROR', msg, level=logging.ERROR)
            raise OllamaNotRunningError(msg) from exc
        except Exception as exc:
            msg = f"Failed to list Ollama models: {str(exc)}"
            log_event('MODEL_ERROR', msg, level=logging.ERROR)
            raise OllamaError(msg) from exc

    def list_installed_models(self) -> List[str]:
        """Returns list of installed model names from Ollama."""
        models_data = self.list_installed_models_with_details()
        return [m.get('name') for m in models_data if m.get('name')]

    def generate(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = True,
        format: Optional[Any] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        num_ctx: Optional[int] = None,
        num_predict: int = 500,
        seed: int = DEFAULT_SEED,
        job_id: Optional[int] = None,
        stage: str = "generation",
        batch_size: int = 1,
    ) -> str:
        """
        Executes generation on local Ollama via streaming with timeout=None (never times out).
        Streams response chunks to keep connection alive.
        Sends think: False for thinking models (e.g. qwen3:4b).
        Logs timing metrics (prompt tokens, output tokens, tps, load time, done reason) into timing.log.
        Guards against length truncation: raises OllamaTruncationError if done_reason == 'length'.
        """
        url = f"{self.base_url}/api/generate"
        if num_ctx is None:
            num_ctx = NUM_CTX_BY_MODEL.get(model, DEFAULT_NUM_CTX)

        payload = {
            'model': model,
            'prompt': prompt,
            'stream': True,
            'keep_alive': OLLAMA_KEEP_ALIVE,
            'options': {
                'temperature': temperature,
                'num_ctx': num_ctx,
                'num_predict': num_predict,
                'seed': seed,
            }
        }
        if system_prompt:
            payload['system'] = system_prompt

        # Schema format or raw 'json'
        if format is not None:
            payload['format'] = format
        elif json_mode:
            payload['format'] = 'json'

        # Explicitly turn off thinking mode for qwen3/deepseek to achieve 10x faster generation
        if 'qwen3' in model.lower() or 'r1' in model.lower():
            payload['think'] = False

        start_time = time.time()
        try:
            resp = self.session.post(
                url,
                json=payload,
                stream=True,
                timeout=OLLAMA_REQUEST_TIMEOUT  # None = no timeout limit
            )
            if resp.status_code == 404:
                err_msg = f"Model '{model}' is not installed in Ollama. Please run: ollama pull {model}"
                log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR, model_name=model)
                raise OllamaModelNotFoundError(err_msg)

            # Fallback if custom schema format is rejected by Ollama version
            if resp.status_code == 400 and format is not None and format != 'json':
                log_event('MODEL_ERROR', f"Ollama rejected format schema, falling back to format='json' for {model}", job_id=job_id, level=logging.WARNING, model_name=model)
                payload['format'] = 'json'
                resp = self.session.post(url, json=payload, stream=True, timeout=OLLAMA_REQUEST_TIMEOUT)

            if resp.status_code != 200:
                err_msg = f"Ollama HTTP {resp.status_code}: {resp.text}"
                log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR, model_name=model)
                raise OllamaResponseError(err_msg)

            # Stream chunks to prevent connection drop and accumulate response & metrics
            response_chunks = []
            done_chunk = {}
            for line in resp.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        if chunk.get('response'):
                            response_chunks.append(chunk['response'])
                        if chunk.get('done'):
                            done_chunk = chunk
                            break
                    except Exception:
                        continue

            duration = time.time() - start_time
            if duration > 120.0:
                log_event(
                    'MODEL_ERROR',
                    f"Slow Ollama call: Model '{model}' took {duration:.2f}s (>120s limit).",
                    job_id=job_id,
                    level=logging.WARNING,
                    model_name=model
                )

            # Extract metrics from done_chunk
            eval_count = done_chunk.get('eval_count', len(response_chunks))
            eval_duration = done_chunk.get('eval_duration', 0)
            prompt_eval_count = done_chunk.get('prompt_eval_count', 0)
            load_duration = done_chunk.get('load_duration', 0)
            total_duration = done_chunk.get('total_duration', 0)
            done_reason = done_chunk.get('done_reason', '')

            tps = (eval_count / (eval_duration / 1e9)) if eval_duration > 0 else 0.0
            load_time_sec = load_duration / 1e9
            total_time_sec = (total_duration / 1e9) if total_duration > 0 else duration

            # Log to timing.log (Step 1.1)
            log_timing_metric(
                job_id=job_id,
                model=model,
                stage=stage,
                batch_size=batch_size,
                prompt_tokens=prompt_eval_count,
                output_tokens=eval_count,
                tps=tps,
                load_time_sec=load_time_sec,
                total_time_sec=total_time_sec,
                done_reason=done_reason
            )

            full_response = "".join(response_chunks)
            cleaned_response = strip_thinking(full_response)

            # Truncation guard (Step 3.5): If cut off by length, signal truncation error
            if done_reason == 'length':
                raise OllamaTruncationError(
                    f"Model '{model}' truncated output due to num_predict={num_predict}",
                    partial_response=cleaned_response,
                    num_predict=num_predict
                )

            return cleaned_response

        except requests.exceptions.ConnectionError as exc:
            err_msg = f"Connection to Ollama failed while calling model '{model}'."
            log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR, model_name=model)
            raise OllamaNotRunningError(err_msg) from exc
        except (OllamaModelNotFoundError, OllamaResponseError, OllamaTruncationError):
            raise
        except Exception as exc:
            err_msg = f"Unexpected error during Ollama generation ({model}): {str(exc)}"
            log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR, model_name=model)
            raise OllamaError(err_msg) from exc

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        json_mode: bool = True,
        temperature: float = DEFAULT_TEMPERATURE,
        num_ctx: int = DEFAULT_NUM_CTX,
        num_predict: int = 500,
        job_id: Optional[int] = None,
    ) -> str:
        """
        Executes chat interaction on local Ollama via streaming with timeout=None.
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            'model': model,
            'messages': messages,
            'stream': True,
            'keep_alive': OLLAMA_KEEP_ALIVE,
            'options': {
                'temperature': temperature,
                'num_ctx': num_ctx,
                'num_predict': num_predict,
            }
        }
        if json_mode:
            payload['format'] = 'json'

        if 'qwen3' in model.lower() or 'r1' in model.lower():
            payload['think'] = False

        start_time = time.time()
        try:
            resp = self.session.post(url, json=payload, stream=True, timeout=OLLAMA_REQUEST_TIMEOUT)
            if resp.status_code == 404:
                err_msg = f"Model '{model}' is not installed in Ollama."
                log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR, model_name=model)
                raise OllamaModelNotFoundError(err_msg)
            if resp.status_code != 200:
                err_msg = f"Ollama chat HTTP {resp.status_code}: {resp.text}"
                log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR, model_name=model)
                raise OllamaResponseError(err_msg)

            chunks = []
            for line in resp.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        content = chunk.get('message', {}).get('content', '')
                        if content:
                            chunks.append(content)
                        if chunk.get('done'):
                            break
                    except Exception:
                        continue

            duration = time.time() - start_time
            if duration > 120.0:
                log_event('MODEL_ERROR', f"Slow chat call: '{model}' took {duration:.2f}s.", job_id=job_id, level=logging.WARNING, model_name=model)

            full_content = "".join(chunks)
            return strip_thinking(full_content)
        except requests.exceptions.ConnectionError as exc:
            err_msg = f"Connection to Ollama failed during chat with model '{model}'."
            log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR, model_name=model)
            raise OllamaNotRunningError(err_msg) from exc
        except Exception as exc:
            err_msg = f"Ollama chat error ({model}): {str(exc)}"
            log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR, model_name=model)
            raise OllamaError(err_msg) from exc

    def get_embeddings(self, model: str, prompt: str) -> Optional[List[float]]:
        """
        Fetches vector embeddings from Ollama. Returns None if model not available.
        """
        url = f"{self.base_url}/api/embeddings"
        payload = {
            'model': model,
            'prompt': prompt,
            'keep_alive': OLLAMA_KEEP_ALIVE,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('embedding')
            return None
        except Exception:
            return None
