"""
Model Manager:
Detects all installed Ollama models dynamically via http://localhost:11434/api/tags.
Assigns roles intelligently according to Phase 3 configuration:
- mcq_generator:  qwen3:4b
- fast_generator: granite3.3:2b  (True/False, Fill in the Blank)
- answer_writer:  llama3.2:3b    (Short and Long answers)
- validator:      phi3:mini
- fallback:       gemma3:4b      (only after 2 failed tries)
- embedding:      nomic-embed-text

Rules:
1. Never hardcode the check of what is installed. Reads /api/tags dynamically.
2. If a model is missing, falls back to the next model in FALLBACK_CHAIN and writes to model_errors.log.
3. smollm2:135m is strictly disallowed for question/answer generation.
4. Returns ollama_running: false cleanly if Ollama is not reachable.
"""
import logging
from typing import Any, Dict, List, Optional
from .config import (
    MODEL_ROLES,
    FALLBACK_CHAIN,
    DISALLOWED_GENERATION_MODELS,
    DEFAULT_GENERATOR_MODEL,
    DEFAULT_VALIDATOR_MODEL,
    DEFAULT_FALLBACK_MODEL,
    PREFERRED_EMBEDDING_MODEL,
)
from .ollama_client import OllamaClient, OllamaNotRunningError
from .logging_setup import log_event

logger = logging.getLogger(__name__)


class ModelManager:
    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()

    def get_installed_models(self) -> List[str]:
        """Queries Ollama dynamically for all installed models."""
        return self.client.list_installed_models()

    def resolve_role_model(
        self,
        preferred: str,
        installed: List[str],
        role_name: str
    ) -> str:
        """
        Resolves the model for a given role against installed models.
        Falls back to FALLBACK_CHAIN if preferred is not installed.
        """
        valid_installed = [
            m for m in installed
            if not any(d.lower() in m.lower() for d in DISALLOWED_GENERATION_MODELS)
        ]

        # 1. Exact or prefix match
        match = next((m for m in valid_installed if preferred.lower() in m.lower()), None)
        if match:
            return match

        # 2. Walk through FALLBACK_CHAIN
        for fb in FALLBACK_CHAIN:
            fb_match = next((m for m in valid_installed if fb.lower() in m.lower()), None)
            if fb_match:
                log_event(
                    'MODEL_ERROR',
                    f"Preferred model '{preferred}' for role '{role_name}' is not installed. "
                    f"Falling back to '{fb_match}'.",
                    level=logging.WARNING,
                    model_name=preferred
                )
                return fb_match

        # 3. Fallback to any valid installed model
        if valid_installed:
            chosen = valid_installed[0]
            log_event(
                'MODEL_ERROR',
                f"Neither preferred '{preferred}' nor fallback chain models are available for '{role_name}'. "
                f"Using available model '{chosen}'.",
                level=logging.WARNING,
                model_name=preferred
            )
            return chosen

        return preferred

    def detect_and_assign_roles(
        self,
        custom_overrides: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Scans installed models and determines roles.
        Allows UI 'Advanced' section overrides while ensuring valid fallbacks.
        """
        custom_overrides = custom_overrides or {}
        try:
            installed = self.get_installed_models()
            ollama_running = True
        except (OllamaNotRunningError, Exception) as exc:
            log_event('MODEL_ERROR', f"Ollama is unreachable: {str(exc)}", level=logging.WARNING)
            return {
                'status': 'offline',
                'ollama_running': False,
                'installed_models': [],
                'roles': MODEL_ROLES,
                'mcq_generator': MODEL_ROLES['mcq_generator'],
                'fast_generator': MODEL_ROLES['fast_generator'],
                'answer_writer': MODEL_ROLES['answer_writer'],
                'validator': MODEL_ROLES['validator'],
                'fallback': MODEL_ROLES['fallback'],
                'generator': MODEL_ROLES['mcq_generator'],
                'embedding_model': None,
                'embedding_source': 'local_fallback',
                'message': 'Ollama is not currently running. Please start Ollama on port 11434.',
            }

        if not installed:
            msg = "No models found in Ollama. Please run: ollama pull qwen3:4b"
            log_event('MODEL_ERROR', msg, level=logging.WARNING)
            return {
                'status': 'no_models',
                'ollama_running': True,
                'installed_models': [],
                'roles': MODEL_ROLES,
                'mcq_generator': MODEL_ROLES['mcq_generator'],
                'fast_generator': MODEL_ROLES['fast_generator'],
                'answer_writer': MODEL_ROLES['answer_writer'],
                'validator': MODEL_ROLES['validator'],
                'fallback': MODEL_ROLES['fallback'],
                'generator': MODEL_ROLES['mcq_generator'],
                'embedding_model': None,
                'embedding_source': 'local_fallback',
                'message': msg,
            }

        # Resolve each role
        mcq_gen = custom_overrides.get('mcq_generator') or self.resolve_role_model(
            MODEL_ROLES['mcq_generator'], installed, 'mcq_generator'
        )
        fast_gen = custom_overrides.get('fast_generator') or self.resolve_role_model(
            MODEL_ROLES['fast_generator'], installed, 'fast_generator'
        )
        ans_writer = custom_overrides.get('answer_writer') or self.resolve_role_model(
            MODEL_ROLES['answer_writer'], installed, 'answer_writer'
        )
        validator = custom_overrides.get('validator') or self.resolve_role_model(
            MODEL_ROLES['validator'], installed, 'validator'
        )
        fallback = custom_overrides.get('fallback') or self.resolve_role_model(
            MODEL_ROLES['fallback'], installed, 'fallback'
        )

        emb_pref = custom_overrides.get('embedding') or MODEL_ROLES['embedding']
        emb_match = next((m for m in installed if emb_pref.lower() in m.lower()), None)
        embedding_model = emb_match or None
        embedding_source = 'ollama' if emb_match else 'local_fallback'

        resolved_roles = {
            'mcq_generator': mcq_gen,
            'fast_generator': fast_gen,
            'answer_writer': ans_writer,
            'validator': validator,
            'fallback': fallback,
            'generator': mcq_gen,
            'embedding': embedding_model or 'local_fallback',
        }

        return {
            'status': 'ready',
            'ollama_running': True,
            'installed_models': installed,
            'roles': resolved_roles,
            'mcq_generator': mcq_gen,
            'fast_generator': fast_gen,
            'answer_writer': ans_writer,
            'validator': validator,
            'fallback': fallback,
            'generator': mcq_gen,
            'embedding_model': embedding_model,
            'embedding_source': embedding_source,
            'fallback_chain': FALLBACK_CHAIN,
            'message': 'All AI models initialized and verified.',
        }

    def get_available_models_metadata(self) -> Dict[str, Any]:
        """
        Rich metadata payload for GET /api/faculty/ai-models/ endpoint.
        Returns HTTP 200 format with ollama_online=True/False.
        """
        try:
            raw_models = self.client.list_installed_models_with_details()
            installed_names = [m.get('name') for m in raw_models if m.get('name')]
            ollama_online = True
        except Exception:
            raw_models = []
            installed_names = []
            ollama_online = False

        role_info = self.detect_and_assign_roles()

        formatted_models = []
        for m in raw_models:
            name = m.get('name', '')
            details = m.get('details', {})
            param_size = details.get('parameter_size', '')
            quant = details.get('quantization_level', '')
            size_mb = round((m.get('size', 0) / (1024 * 1024)), 1)

            # Determine role badge
            role_badge = None
            if name == role_info.get('mcq_generator'):
                role_badge = 'MCQ Generator'
            elif name == role_info.get('fast_generator'):
                role_badge = 'Fast Generator (T/F, Fill)'
            elif name == role_info.get('answer_writer'):
                role_badge = 'Answer Writer (Short, Long)'
            elif name == role_info.get('validator'):
                role_badge = 'Validator'
            elif name == role_info.get('fallback'):
                role_badge = 'Fallback Repair'

            formatted_models.append({
                'id': name,
                'name': name,
                'label': f"{name} ({param_size or f'{size_mb}MB'})",
                'size_mb': size_mb,
                'parameter_size': param_size,
                'quantization': quant,
                'role': role_badge,
                'is_recommended': name in [
                    role_info.get('mcq_generator'),
                    role_info.get('fast_generator'),
                    role_info.get('answer_writer')
                ],
            })

        return {
            'ollama_online': ollama_online,
            'ollama_running': ollama_online,
            'models': formatted_models,
            'primary_model': role_info.get('mcq_generator', DEFAULT_GENERATOR_MODEL),
            'assigned_roles': {
                'generator': role_info.get('mcq_generator'),
                'validator': role_info.get('validator'),
                'fallback': role_info.get('fallback'),
                'mcq_generator': role_info.get('mcq_generator'),
                'fast_generator': role_info.get('fast_generator'),
                'answer_writer': role_info.get('answer_writer'),
                'embedding': role_info.get('embedding_model'),
            },
            'model_roles': role_info.get('roles', MODEL_ROLES),
            'fallback_chain': FALLBACK_CHAIN,
            'message': 'Ollama online' if ollama_online else 'Ollama is offline. Start Ollama at http://localhost:11434',
        }
