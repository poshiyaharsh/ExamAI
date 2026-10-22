import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from superadmin.audit import GENESIS_HASH, compute_audit_hash
from superadmin.models import AIModel, SuperAdminAuditLog

logger = logging.getLogger(__name__)


def record_ai_audit(
    actor_username: str,
    action: str,
    target_entity: str = 'AIModel',
    target_id: str = '',
    description: str = '',
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
):
    """Writes an immutable, cryptographically chained audit log entry for AI operations."""
    try:
        last_entry = SuperAdminAuditLog.objects.order_by('-id').first()
        prev_hash = last_entry.entry_hash if (last_entry and last_entry.entry_hash) else GENESIS_HASH
        entry_hash = compute_audit_hash(
            prev_hash=prev_hash,
            actor_username=actor_username or 'system',
            action=action,
            target_entity=target_entity,
            target_id=str(target_id),
            description=description,
            ip_address='127.0.0.1',
            before_state=before_state or {},
            after_state=after_state or {},
        )
        return SuperAdminAuditLog.objects.create(
            actor_username=actor_username or 'system',
            action=action,
            target_entity=target_entity,
            target_id=str(target_id),
            description=description,
            before_state=before_state or {},
            after_state=after_state or {},
            ip_address='127.0.0.1',
            user_agent='ExamAI-AIService',
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
    except Exception as exc:
        logger.error('Failed to write AI audit log: %s', exc)
        return None


OLLAMA_BASE_URL = getattr(settings, 'OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')

MODEL_NAME_REGEX = re.compile(r'^[a-zA-Z0-9_\-\.\/]+(:[a-zA-Z0-9_\-\.]+)?$')

# Curated catalog of free open-source models available on the official Ollama library
FREE_ONLINE_MODELS_CATALOG = [
    {
        'name': 'llama3.2:1b',
        'display_name': 'Llama 3.2 1B (Ultra-fast)',
        'parameter_size': '1.2B',
        'family': 'llama',
        'size_approx': '1.3 GB',
        'min_ram_gb': 4,
        'description': 'Lightweight Meta model optimized for rapid question generation on modest hardware.',
    },
    {
        'name': 'llama3.2:3b',
        'display_name': 'Llama 3.2 3B (Balanced)',
        'parameter_size': '3.2B',
        'family': 'llama',
        'size_approx': '2.0 GB',
        'min_ram_gb': 6,
        'description': 'Modern lightweight Meta model, excellent general reasoning and structured JSON output.',
    },
    {
        'name': 'phi3:mini',
        'display_name': 'Microsoft Phi-3 Mini 3.8B',
        'parameter_size': '3.8B',
        'family': 'phi3',
        'size_approx': '2.2 GB',
        'min_ram_gb': 6,
        'description': 'Compact model trained on textbook-quality synthetic data, great for academic tests.',
    },
    {
        'name': 'qwen2.5:3b-instruct',
        'display_name': 'Qwen 2.5 3B Instruct',
        'parameter_size': '3.1B',
        'family': 'qwen2',
        'size_approx': '1.9 GB',
        'min_ram_gb': 6,
        'description': 'Alibaba Qwen 2.5 series with high multi-subject proficiency and coding accuracy.',
    },
    {
        'name': 'deepseek-r1:1.5b',
        'display_name': 'DeepSeek R1 1.5B (Reasoning)',
        'parameter_size': '1.5B',
        'family': 'qwen2',
        'size_approx': '1.1 GB',
        'min_ram_gb': 4,
        'description': 'Distilled reasoning model trained with reinforcement learning for STEM questions.',
    },
    {
        'name': 'mistral:latest',
        'display_name': 'Mistral 7B',
        'parameter_size': '7.2B',
        'family': 'mistral',
        'size_approx': '4.1 GB',
        'min_ram_gb': 12,
        'description': 'Full 7B instruction-tuned model, superior comprehension for complex exam generation.',
    },
    {
        'name': 'smollm2:135m',
        'display_name': 'SmolLM2 135M (Testing)',
        'parameter_size': '135M',
        'family': 'smollm',
        'size_approx': '270 MB',
        'min_ram_gb': 2,
        'description': 'Ultra-tiny test model, downloads in seconds for verifying Ollama setup.',
    },
]


def validate_model_tag(tag: str) -> bool:
    """Validate model tag against safe format regex."""
    if not tag or len(tag) > 120:
        return False
    return bool(MODEL_NAME_REGEX.match(tag.strip()))


def get_ollama_status_and_sync() -> Dict[str, Any]:
    """
    Queries Ollama /api/tags and /api/ps.
    Synchronizes local models with AIModel database registry.
    Returns aggregated status, alerts, and model records.
    """
    ollama_online = False
    installed_tags_data: List[Dict[str, Any]] = []
    running_models: List[Dict[str, Any]] = []
    err_message = ''

    # 1. Fetch /api/tags
    try:
        req = urllib.request.Request(
            f'{OLLAMA_BASE_URL}/api/tags',
            headers={'Accept': 'application/json', 'User-Agent': 'ExamAI-SuperAdmin/1.0'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            installed_tags_data = data.get('models', [])
            ollama_online = True
    except Exception as exc:
        err_message = f'Cannot connect to Ollama at {OLLAMA_BASE_URL}: {str(exc)}'
        logger.warning(err_message)

    # 2. Fetch /api/ps (running instances)
    if ollama_online:
        try:
            req_ps = urllib.request.Request(
                f'{OLLAMA_BASE_URL}/api/ps',
                headers={'Accept': 'application/json', 'User-Agent': 'ExamAI-SuperAdmin/1.0'},
            )
            with urllib.request.urlopen(req_ps, timeout=4) as resp:
                data_ps = json.loads(resp.read().decode('utf-8'))
                running_models = data_ps.get('models', [])
        except Exception:
            running_models = []

    # 3. Synchronize with database
    installed_names = set()
    if ollama_online:
        for m in installed_tags_data:
            tag = m.get('name') or m.get('model')
            if not tag:
                continue
            installed_names.add(tag)
            details = m.get('details', {}) or {}
            size = m.get('size', 0)
            family = details.get('family', '')
            param_size = details.get('parameter_size', '')
            quant_level = details.get('quantization_level', '')
            ctx_len = details.get('context_length') or 4096

            # Get or create record
            ai_obj, created = AIModel.objects.get_or_create(
                name=tag,
                defaults={
                    'display_name': tag.replace(':', ' ').title(),
                    'family': family,
                    'parameter_size': param_size,
                    'quantization_level': quant_level,
                    'size_bytes': size,
                    'context_window': ctx_len,
                    'status': 'ready',
                    'pull_progress_percent': 100,
                },
            )
            if not created and ai_obj.status in ('pulling', 'offline'):
                ai_obj.status = 'ready'
                ai_obj.pull_progress_percent = 100
                ai_obj.size_bytes = size
                ai_obj.family = family or ai_obj.family
                ai_obj.parameter_size = param_size or ai_obj.parameter_size
                ai_obj.quantization_level = quant_level or ai_obj.quantization_level
                ai_obj.save(update_fields=['status', 'pull_progress_percent', 'size_bytes', 'family', 'parameter_size', 'quantization_level', 'updated_at'])

        # Ensure at least one default model exists if there are enabled models
        has_default = AIModel.objects.filter(is_default=True, is_enabled=True).exists()
        if not has_default:
            first_enabled = AIModel.objects.filter(is_enabled=True, status='ready').first()
            if first_enabled:
                first_enabled.is_default = True
                first_enabled.save(update_fields=['is_default', 'updated_at'])

        # Mark models in DB not present in Ollama as offline
        AIModel.objects.exclude(name__in=installed_names).filter(status='ready').update(status='offline')

    # Query all models from DB
    models_qs = AIModel.objects.all().order_by('-is_default', '-is_enabled', 'name')
    running_names = {r.get('name') for r in running_models}

    serialized_models = []
    total_disk_bytes = 0
    for m in models_qs:
        total_disk_bytes += m.size_bytes
        serialized_models.append({
            'id': m.id,
            'name': m.name,
            'display_name': m.display_name or m.name,
            'family': m.family,
            'parameter_size': m.parameter_size,
            'quantization_level': m.quantization_level,
            'size_bytes': m.size_bytes,
            'size_mb': round(m.size_bytes / (1024 * 1024), 1) if m.size_bytes else 0,
            'context_window': m.context_window,
            'is_enabled': m.is_enabled,
            'is_default': m.is_default,
            'status': m.status,
            'is_active_in_vram': m.name in running_names,
            'pull_progress_percent': m.pull_progress_percent,
            'pull_status_message': m.pull_status_message,
            'last_tested_at': m.last_tested_at.isoformat() if m.last_tested_at else None,
            'last_test_latency_ms': m.last_test_latency_ms,
            'last_test_success': m.last_test_success,
            'last_test_error': m.last_test_error,
            'notes': m.notes,
            'created_at': m.created_at.isoformat(),
        })

    # Capacity alerts
    capacity_alerts = []
    if not ollama_online:
        capacity_alerts.append({
            'severity': 'critical',
            'title': 'Ollama Service Unreachable',
            'message': f'Cannot reach Ollama at {OLLAMA_BASE_URL}. Start Ollama service on your local machine.',
        })
    elif len(serialized_models) == 0:
        capacity_alerts.append({
            'severity': 'warning',
            'title': 'No Models Installed',
            'message': 'No Ollama models found. Pull a model from the free catalog below to enable question generation.',
        })
    elif not any(m['is_enabled'] for m in serialized_models):
        capacity_alerts.append({
            'severity': 'warning',
            'title': 'All Models Disabled',
            'message': 'All models are currently disabled. Paper generation will fail until at least one model is enabled.',
        })

    return {
        'ollama_online': ollama_online,
        'ollama_base_url': OLLAMA_BASE_URL,
        'error_message': err_message,
        'models': serialized_models,
        'running_models_count': len(running_models),
        'total_models_count': len(serialized_models),
        'enabled_models_count': sum(1 for m in serialized_models if m['is_enabled']),
        'total_disk_gb': round(total_disk_bytes / (1024 * 1024 * 1024), 2),
        'capacity_alerts': capacity_alerts,
        'catalog': FREE_ONLINE_MODELS_CATALOG,
    }


def pull_model_stream_worker(model_id: int, model_name: str, actor_username: str):
    """
    Background worker thread to stream model download from Ollama API.
    Updates progress percentage and status message in AIModel record.
    """
    connection.close()  # Reset MySQL connection for new thread
    logger.info('Starting background pull for model %s (id=%s) by %s', model_name, model_id, actor_username)

    try:
        url = f'{OLLAMA_BASE_URL}/api/pull'
        payload = json.dumps({'name': model_name, 'stream': True}).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=payload,
            headers={'Content-Type': 'application/json', 'User-Agent': 'ExamAI-SuperAdmin/1.0'},
            method='POST',
        )

        with urllib.request.urlopen(req, timeout=1800) as resp:
            for line in resp:
                if not line:
                    continue
                try:
                    data = json.loads(line.decode('utf-8'))
                    status_text = data.get('status', '')
                    completed = data.get('completed', 0)
                    total = data.get('total', 0)

                    percent = 0
                    if total > 0:
                        percent = min(99, int((completed / total) * 100))

                    # Update DB periodically
                    AIModel.objects.filter(id=model_id).update(
                        pull_progress_percent=percent,
                        pull_status_message=f'{status_text} ({percent}%)' if percent > 0 else status_text,
                        updated_at=timezone.now(),
                    )
                except Exception:
                    pass

        # Pull complete: query model details from /api/tags
        time.sleep(1)
        details_url = f'{OLLAMA_BASE_URL}/api/tags'
        with urllib.request.urlopen(details_url, timeout=10) as tags_resp:
            tags_data = json.loads(tags_resp.read().decode('utf-8'))
            for m in tags_data.get('models', []):
                tag = m.get('name') or m.get('model')
                if tag == model_name or tag.split(':')[0] == model_name.split(':')[0]:
                    details = m.get('details', {}) or {}
                    AIModel.objects.filter(id=model_id).update(
                        status='ready',
                        pull_progress_percent=100,
                        pull_status_message='Installed and ready',
                        size_bytes=m.get('size', 0),
                        family=details.get('family', ''),
                        parameter_size=details.get('parameter_size', ''),
                        quantization_level=details.get('quantization_level', ''),
                        context_window=details.get('context_length') or 4096,
                        updated_at=timezone.now(),
                    )
                    break
            else:
                AIModel.objects.filter(id=model_id).update(
                    status='ready',
                    pull_progress_percent=100,
                    pull_status_message='Installed and ready',
                    updated_at=timezone.now(),
                )

        record_ai_audit(
            actor_username=actor_username,
            action='ai_model.pull_complete',
            target_entity='AIModel',
            target_id=str(model_id),
            description=f'Successfully pulled Ollama model {model_name}',
            after_state={'model_name': model_name, 'status': 'ready'},
        )
        logger.info('Finished background pull for model %s', model_name)

    except Exception as exc:
        err_msg = str(exc)
        logger.error('Background pull failed for model %s: %s', model_name, err_msg)
        AIModel.objects.filter(id=model_id).update(
            status='failed',
            pull_status_message=f'Download failed: {err_msg[:200]}',
            updated_at=timezone.now(),
        )
        record_ai_audit(
            actor_username=actor_username,
            action='ai_model.pull_failed',
            target_entity='AIModel',
            target_id=str(model_id),
            description=f'Failed to pull Ollama model {model_name}: {err_msg[:200]}',
            after_state={'model_name': model_name, 'status': 'failed', 'error': err_msg[:200]},
        )
    finally:
        connection.close()


def initiate_model_pull(model_name: str, actor_username: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validates model tag, creates database record in pulling state,
    and initiates daemon thread to stream pull from Ollama.
    """
    clean_name = model_name.strip()
    if not validate_model_tag(clean_name):
        return False, 'Invalid model name format. Use letters, numbers, hyphens, and optional tag (e.g. llama3.2:3b).', None

    # Check if already exists and ready
    existing = AIModel.objects.filter(name=clean_name).first()
    if existing and existing.status == 'ready':
        return False, f'Model "{clean_name}" is already installed and ready.', None
    if existing and existing.status == 'pulling':
        return False, f'Model "{clean_name}" is already being downloaded ({existing.pull_progress_percent}%).', None

    if not existing:
        existing = AIModel.objects.create(
            name=clean_name,
            display_name=clean_name.replace(':', ' ').title(),
            status='pulling',
            pull_progress_percent=0,
            pull_status_message='Initiating download...',
            is_enabled=True,
        )
    else:
        existing.status = 'pulling'
        existing.pull_progress_percent = 0
        existing.pull_status_message = 'Initiating download...'
        existing.save(update_fields=['status', 'pull_progress_percent', 'pull_status_message', 'updated_at'])

    record_ai_audit(
        actor_username=actor_username,
        action='ai_model.pull_initiated',
        target_entity='AIModel',
        target_id=str(existing.id),
        description=f'Initiated background download of Ollama model {clean_name}',
        after_state={'model_name': clean_name, 'status': 'pulling'},
    )

    thread = threading.Thread(
        target=pull_model_stream_worker,
        args=(existing.id, clean_name, actor_username),
        daemon=True,
        name=f'ollama-pull-{clean_name}',
    )
    thread.start()

    return True, f'Download initiated for "{clean_name}". Progress will update live.', {
        'id': existing.id,
        'name': existing.name,
        'status': existing.status,
    }


def toggle_ai_model_status(model_id: int, is_enabled: bool, actor_username: str) -> Tuple[bool, str]:
    """Toggle enabled/disabled status of a model."""
    try:
        model = AIModel.objects.get(id=model_id)
    except AIModel.DoesNotExist:
        return False, 'Model not found.'

    if not is_enabled and model.is_default:
        # Check if another enabled model is available to be default
        other = AIModel.objects.filter(is_enabled=True).exclude(id=model.id).first()
        if not other:
            return False, 'Cannot disable the default model when no other enabled models exist.'
        other.is_default = True
        other.save(update_fields=['is_default', 'updated_at'])
        model.is_default = False

    before = {'is_enabled': model.is_enabled, 'is_default': model.is_default}
    model.is_enabled = is_enabled
    model.save(update_fields=['is_enabled', 'is_default', 'updated_at'])

    record_ai_audit(
        actor_username=actor_username,
        action='ai_model.toggle_status',
        target_entity='AIModel',
        target_id=str(model.id),
        description=f'Changed model "{model.name}" enabled status to {is_enabled}',
        before_state=before,
        after_state={'is_enabled': model.is_enabled, 'is_default': model.is_default},
    )

    return True, f'Model "{model.name}" {"enabled" if is_enabled else "disabled"} successfully.'


def set_default_ai_model(model_id: int, actor_username: str) -> Tuple[bool, str]:
    """Sets a model as system default for paper generation."""
    try:
        model = AIModel.objects.get(id=model_id)
    except AIModel.DoesNotExist:
        return False, 'Model not found.'

    with transaction.atomic():
        AIModel.objects.exclude(id=model.id).update(is_default=False)
        model.is_default = True
        model.is_enabled = True  # Default model must always be enabled
        model.save(update_fields=['is_default', 'is_enabled', 'updated_at'])

    record_ai_audit(
        actor_username=actor_username,
        action='ai_model.set_default',
        target_entity='AIModel',
        target_id=str(model.id),
        description=f'Set model "{model.name}" as primary default for paper generation',
        after_state={'model_name': model.name, 'is_default': True},
    )

    return True, f'Model "{model.name}" set as platform default.'


def remove_ollama_model(model_id: int, actor_username: str) -> Tuple[bool, str]:
    """
    Safely deletes model from Ollama disk and AIModel database registry.
    Requires step-up re-authentication at view layer.
    """
    try:
        model = AIModel.objects.get(id=model_id)
    except AIModel.DoesNotExist:
        return False, 'Model not found.'

    if model.is_default:
        # Check if another model can become default
        replacement = AIModel.objects.filter(is_enabled=True).exclude(id=model.id).first()
        if replacement:
            replacement.is_default = True
            replacement.save(update_fields=['is_default', 'updated_at'])
        else:
            return False, 'Cannot remove the default model without another enabled model available.'

    model_name = model.name

    # 1. Delete from Ollama via HTTP DELETE /api/delete
    try:
        req = urllib.request.Request(
            f'{OLLAMA_BASE_URL}/api/delete',
            data=json.dumps({'name': model_name}).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'User-Agent': 'ExamAI-SuperAdmin/1.0'},
            method='DELETE',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            pass
    except Exception as exc:
        logger.warning('Ollama delete API returned error for %s: %s (proceeding with DB deletion)', model_name, exc)

    # 2. Delete from DB
    model.delete()

    record_ai_audit(
        actor_username=actor_username,
        action='ai_model.delete',
        target_entity='AIModel',
        target_id=str(model_id),
        description=f'Permanently removed model "{model_name}" from Ollama and platform registry',
        before_state={'model_name': model_name},
    )

    return True, f'Model "{model_name}" successfully removed.'


def test_ai_model_connectivity(model_id: int, actor_username: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Sends a test ping to Ollama with the selected model to verify operational health and measure latency.
    """
    try:
        model = AIModel.objects.get(id=model_id)
    except AIModel.DoesNotExist:
        return False, 'Model not found.', {}

    start_time = time.perf_counter()
    success = False
    error_str = ''
    latency_ms = 0
    response_text = ''

    try:
        payload = json.dumps({
            'model': model.name,
            'prompt': 'Respond only with the exact word: OPERATIONAL',
            'stream': False,
            'options': {'temperature': 0.0, 'num_predict': 10},
        }).encode('utf-8')

        req = urllib.request.Request(
            f'{OLLAMA_BASE_URL}/api/generate',
            data=payload,
            headers={'Content-Type': 'application/json', 'User-Agent': 'ExamAI-SuperAdmin/1.0'},
            method='POST',
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            response_text = data.get('response', '').strip()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            success = True

    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        error_str = str(exc)

    # Save benchmark results
    model.last_tested_at = timezone.now()
    model.last_test_latency_ms = latency_ms
    model.last_test_success = success
    model.last_test_error = error_str[:255] if error_str else ''
    model.save(update_fields=['last_tested_at', 'last_test_latency_ms', 'last_test_success', 'last_test_error', 'updated_at'])

    result = {
        'model_name': model.name,
        'success': success,
        'latency_ms': latency_ms,
        'response_text': response_text,
        'error': error_str,
    }

    if success:
        return True, f'Model "{model.name}" is healthy (latency: {latency_ms}ms).', result
    else:
        return False, f'Test failed for "{model.name}": {error_str}', result
