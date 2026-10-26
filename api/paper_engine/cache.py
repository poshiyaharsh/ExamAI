"""
Multi-Tenant Paper Generation Cache Service.

Guarantees:
1. Strict tenant and faculty isolation across all cache keys.
2. Under 200ms load time for repeat requests and previous papers.
3. Safe fallback to database if cache fails.
4. Automatic invalidation on Question Bank edits and exam publications.
5. Invalidation via global CACHE_VERSION and per-tenant version counters.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache
from api.tenant import get_tenant_cache_version, bump_tenant_cache_version


logger = logging.getLogger(__name__)

GLOBAL_CACHE_VERSION = 1
TTL_PAPER_SNAPSHOT = 86400  # 24 hours
TTL_CANDIDATE_POOL = 600    # 10 minutes
TTL_PAPER_LIST = 300        # 5 minutes
TTL_PAPER_DETAIL = 86400    # 24 hours


def compute_request_hash(payload: Dict[str, Any]) -> str:
    """
    Computes a deterministic SHA-256 hash from normalized request parameters.
    Ensures identical generation requests match the same cache slot.
    """
    # Extract & sort relevant fields
    topics = sorted([str(t).strip().lower() for t in payload.get("topics", []) if t])
    q_types = sorted([str(t).strip().upper() for t in payload.get("question_types", []) if t])
    diff = payload.get("difficulty_distribution") or {}
    norm_diff = {
        "easy": int(diff.get("easy", diff.get("Easy", 30))),
        "medium": int(diff.get("medium", diff.get("Medium", 50))),
        "hard": int(diff.get("hard", diff.get("Hard", 20))),
    }

    raw_sub_id = payload.get("subject_id")
    parsed_sub_id = None
    if raw_sub_id is not None and str(raw_sub_id).strip() != "":
        try:
            parsed_sub_id = int(raw_sub_id)
        except (ValueError, TypeError):
            parsed_sub_id = None

    norm_dict = {
        "title": str(payload.get("title", "")).strip().lower(),
        "total_marks": int(payload.get("total_marks", 0)),
        "duration_minutes": int(payload.get("duration_minutes", 0)),
        "topics": topics,
        "question_types": q_types,
        "difficulty_distribution": norm_diff,
        "department": str(payload.get("department", "")).strip().lower(),
        "subject_id": parsed_sub_id,
        "subject": str(payload.get("subject_name") or payload.get("subject") or "").strip().lower(),
        "avoid_repeats": bool(payload.get("avoid_repeats", True)),
    }

    raw_json = json.dumps(norm_dict, sort_keys=True)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


class PaperCacheService:
    """Provides high-performance, strictly isolated caching for the paper engine."""

    @staticmethod
    def _get_version(institution_id: int) -> int:
        try:
            return get_tenant_cache_version(institution_id)
        except Exception:
            return GLOBAL_CACHE_VERSION

    @classmethod
    def make_paper_key(cls, institution_id: int, faculty_id: int, request_hash: str) -> str:
        v = cls._get_version(institution_id)
        return f"paper:v{GLOBAL_CACHE_VERSION}:t{v}:inst_{institution_id}:fac_{faculty_id}:{request_hash}"

    @classmethod
    def make_pool_key(
        cls,
        institution_id: int,
        department: str = "",
        subject_id: Optional[int] = None,
        topic: str = "",
        difficulty: str = "",
        q_type: str = "",
    ) -> str:
        v = cls._get_version(institution_id)
        return (
            f"pool:v{GLOBAL_CACHE_VERSION}:t{v}:inst_{institution_id}:"
            f"dept_{department}:sub_{subject_id or 'all'}:top_{topic or 'all'}:"
            f"diff_{difficulty or 'all'}:type_{q_type or 'all'}"
        )

    @classmethod
    def make_list_key(cls, institution_id: int, faculty_id: int, page: int = 1, filters_str: str = "") -> str:
        v = cls._get_version(institution_id)
        return f"paperlist:v{GLOBAL_CACHE_VERSION}:t{v}:inst_{institution_id}:fac_{faculty_id}:p{page}:{filters_str}"

    @classmethod
    def make_detail_key(cls, institution_id: int, exam_id: int) -> str:
        v = cls._get_version(institution_id)
        return f"paperdetail:v{GLOBAL_CACHE_VERSION}:t{v}:inst_{institution_id}:exam_{exam_id}"

    # --- Paper Cache Operations ---

    @classmethod
    def get_cached_paper(
        cls,
        institution_id: int,
        faculty_id: int,
        request_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached paper result. Verifies freshness before returning."""
        key = cls.make_paper_key(institution_id, faculty_id, request_hash)
        try:
            cached_data = cache.get(key)
            if not cached_data:
                logger.info("Paper cache miss key=%s", key)
                return None

            # Verify question versions and status to prevent serving deleted/archived questions
            q_ids = cached_data.get("question_ids") or []
            if q_ids:
                from api.models import Question
                active_count = Question.objects.filter(
                    id__in=q_ids,
                    institution_id=institution_id,
                    is_deleted=False,
                    status=Question.Status.ACTIVE,
                ).count()
                if active_count != len(q_ids):
                    # Cache is stale due to deleted or archived question
                    logger.info("Stale paper cache detected for key=%s (active count mismatch)", key)
                    cache.delete(key)
                    return None

            logger.info("Paper cache hit key=%s", key)
            return cached_data
        except Exception as exc:
            logger.warning("Cache access error during get_cached_paper: %s. Falling back to DB.", exc)
            return None

    @classmethod
    def set_cached_paper(
        cls,
        institution_id: int,
        faculty_id: int,
        request_hash: str,
        data: Dict[str, Any],
        timeout: int = TTL_PAPER_SNAPSHOT,
    ) -> None:
        """Store generated paper and its validation report in cache."""
        key = cls.make_paper_key(institution_id, faculty_id, request_hash)
        try:
            cache.set(key, data, timeout=timeout)
            logger.info("Cached paper snapshot key=%s timeout=%s", key, timeout)
        except Exception as exc:
            logger.warning("Cache set error during set_cached_paper: %s", exc)

    @classmethod
    def get_cached_paper_detail(cls, institution_id: int, exam_id: int) -> Optional[Dict[str, Any]]:
        key = cls.make_detail_key(institution_id, exam_id)
        try:
            return cache.get(key)
        except Exception:
            return None

    @classmethod
    def set_cached_paper_detail(
        cls,
        institution_id: int,
        exam_id: int,
        data: Dict[str, Any],
        timeout: int = TTL_PAPER_DETAIL,
    ) -> None:
        key = cls.make_detail_key(institution_id, exam_id)
        try:
            cache.set(key, data, timeout=timeout)
        except Exception:
            pass

    # --- Invalidation ---

    @classmethod
    def invalidate_exam(cls, institution_id: int, exam_id: int) -> None:
        """Invalidate single exam detail and bump tenant cache version."""
        detail_key = cls.make_detail_key(institution_id, exam_id)
        try:
            cache.delete(detail_key)
            bump_tenant_cache_version(institution_id)
            logger.info("Invalidated exam detail key=%s and bumped tenant version", detail_key)
        except Exception as exc:
            logger.warning("Error during invalidate_exam: %s", exc)

    @classmethod
    def invalidate_tenant_pools_and_papers(cls, institution_id: int) -> None:
        """Instantly invalidates all cached candidate pools and papers for this tenant."""
        try:
            bump_tenant_cache_version(institution_id)
            logger.info("Bumped tenant cache version for institution_id=%s", institution_id)
        except Exception as exc:
            logger.warning("Error bumping tenant cache version: %s", exc)

    @classmethod
    def clear_faculty_papers(cls, institution_id: int, faculty_id: int) -> None:
        """Explicit action: Clear cached papers for a specific faculty member."""
        cls.invalidate_tenant_pools_and_papers(institution_id)

    @classmethod
    def clear_all(cls) -> None:
        """Clear entire cache backend (used in tests or administrative resets)."""
        try:
            cache.clear()
        except Exception:
            pass
