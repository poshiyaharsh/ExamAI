"""
Time Governor (Section 2.5 & 2.7).
Enforces 540s (9 minutes) total generation budget for 100-mark paper and 270s for 50-mark paper.
Features:
1. Measures tokens per second in real-time.
2. Projects completion time from blueprint, factoring in multilingual token expansion.
3. Applies ordered graceful degradation:
   (a) skip AI validator for Short answers
   (b) reduce Long and Short word targets (floor: 25 words/mark)
   (c) switch remaining batches to granite3.3:2b (English/Latin only; never for Indic/Arabic)
   (d) switch Long answers to granite3.3:2b (English/Latin only; never for Indic/Arabic)
4. Speed calibration benchmark function.
5. Never drops question counts or marks.
"""
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..config import (
    TIME_BUDGET_SEC,
    BASE_TOKENS_BY_TYPE,
    MODEL_ROLES,
    LOGS_DIR,
    get_token_expansion_factor
)
from ..logging_setup import log_event, log_timing

logger = logging.getLogger(__name__)

CALIBRATION_FILE = LOGS_DIR / "speed_calibration.json"


class TimeGovernor:
    def __init__(
        self,
        job_id: int,
        total_marks: int,
        blueprint: List[Dict[str, Any]],
        start_time: Optional[float] = None,
        language: str = "en"
    ):
        self.job_id = job_id
        self.total_marks = total_marks
        self.blueprint = blueprint
        self.start_time = start_time or time.time()
        self.budget_sec = TIME_BUDGET_SEC if total_marks >= 70 else 270.0
        self.language = language or "en"

        # Degradation state flags
        self.skip_short_ai_val = False
        self.words_per_mark_short = 35
        self.words_per_mark_long = 55
        self.use_fast_for_subjective = False
        self.use_fast_for_long = False

        # Calibrated or observed TPS
        self.observed_tps: Dict[str, float] = self._load_calibration()
        self.decisions_log: List[str] = []

    def _load_calibration(self) -> Dict[str, float]:
        """Loads cached model TPS calibration or sets defaults."""
        defaults = {
            "granite3.3:2b": 23.0,
            "llama3.2:3b": 16.0,
            "qwen3:4b": 18.0,
            "phi3:mini": 15.0,
            "gemma3:4b": 12.0,
        }
        if CALIBRATION_FILE.exists():
            try:
                with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception:
                pass
        return defaults

    def record_stage_metrics(self, model: str, tps: float):
        """Updates observed speed for a model."""
        if tps > 2.0:
            self.observed_tps[model] = tps

    def estimate_remaining_tokens(self, remaining_slots: List[Dict[str, Any]]) -> int:
        """Calculates expected token count for all remaining slots, scaled by language factor."""
        total = 0
        for s in remaining_slots:
            q_type = s.get('type')
            marks = s.get('marks', 1)
            if q_type == 'MCQ':
                total += BASE_TOKENS_BY_TYPE.get('MCQ', 90)
            elif q_type in ('True/False', 'Fill in the Blank'):
                total += BASE_TOKENS_BY_TYPE.get(q_type, 45)
            elif q_type == 'Short Answer':
                total += self.words_per_mark_short * marks + 40
            elif q_type == 'Long Answer':
                total += self.words_per_mark_long * marks + 40
            else:
                total += 100

        factor = get_token_expansion_factor(self.language)
        return int(total * factor)

    def evaluate_and_govern(
        self,
        remaining_slots: List[Dict[str, Any]],
        current_model: str,
        current_stage: str
    ) -> Dict[str, Any]:
        """
        Projects completion time and applies graceful degradation if over budget.
        Returns governor instructions and estimated seconds remaining.
        Guarantees Indic/Arabic jobs never degrade to granite3.3:2b.
        """
        elapsed = time.time() - self.start_time
        remaining_budget = max(5.0, self.budget_sec - elapsed)

        remaining_tokens = self.estimate_remaining_tokens(remaining_slots)
        avg_tps = self.observed_tps.get(current_model, 18.0)
        projected_generation_time = remaining_tokens / max(5.0, avg_tps)
        projected_total = elapsed + projected_generation_time

        # If projection exceeds budget, trigger degradation steps in order
        if projected_total > self.budget_sec:
            overage = projected_total - self.budget_sec

            # Level 1: Skip AI validator for Short answers
            if not self.skip_short_ai_val:
                self.skip_short_ai_val = True
                dec = f"Governor: Projected {projected_total:.1f}s > {self.budget_sec}s. Step (a): Skipped AI validator for Short answers."
                self._log_decision(dec)

            # Level 2: Reduce word targets (floor 25 words/mark)
            if overage > 30 and (self.words_per_mark_short > 25 or self.words_per_mark_long > 25):
                self.words_per_mark_short = max(25, self.words_per_mark_short - 5)
                self.words_per_mark_long = max(25, self.words_per_mark_long - 10)
                dec = f"Governor: Step (b): Reduced word targets to Short={self.words_per_mark_short}w/m, Long={self.words_per_mark_long}w/m."
                self._log_decision(dec)

            # Level 3: Route remaining subjective batches to faster granite3.3:2b (ONLY for English/Latin)
            # Never degrade Indic or Arabic to granite3.3:2b as it causes language corruption
            is_indic_or_arabic = self.language in ('hi', 'gu', 'mr', 'ta', 'bn', 'ur', 'ar')
            if overage > 60 and not self.use_fast_for_subjective and not is_indic_or_arabic:
                self.use_fast_for_subjective = True
                dec = f"Governor: Step (c): Routed remaining Short Answer batches to granite3.3:2b."
                self._log_decision(dec)

            # Level 4: Route Long answers to granite3.3:2b (ONLY for English/Latin)
            if overage > 100 and not self.use_fast_for_long and not is_indic_or_arabic:
                self.use_fast_for_long = True
                dec = f"Governor: Step (d): Routed Long Answer generation to granite3.3:2b."
                self._log_decision(dec)

            # Recalculate with new targets
            remaining_tokens = self.estimate_remaining_tokens(remaining_slots)
            projected_generation_time = remaining_tokens / max(5.0, avg_tps)

        sec_left = max(0, int(projected_generation_time))
        return {
            'estimated_seconds_remaining': sec_left,
            'skip_short_ai_val': self.skip_short_ai_val,
            'words_per_mark_short': self.words_per_mark_short,
            'words_per_mark_long': self.words_per_mark_long,
            'use_fast_for_subjective': self.use_fast_for_subjective,
            'use_fast_for_long': self.use_fast_for_long,
        }

    def _log_decision(self, message: str):
        self.decisions_log.append(message)
        log_event('GENERATION', message, job_id=self.job_id)
        log_timing('Governor Intervention', 0.0, job_id=self.job_id, details=message)


def calibrate_speed(client) -> Dict[str, float]:
    """
    Step 2.7: Runs a tiny benchmark per role model (tokens per second),
    persists result to speed_calibration.json, and returns tps map.
    """
    models_to_test = [
        ("granite3.3:2b", 50),
        ("llama3.2:3b", 50),
        ("qwen3:4b", 50),
    ]
    results = {}
    for m, tokens in models_to_test:
        try:
            t0 = time.time()
            prompt = "Output JSON: {\"status\": \"ok\", \"count\": 5}"
            raw = client.generate(
                model=m,
                prompt=prompt,
                num_predict=tokens,
                temperature=0.2,
                stage="calibration"
            )
            elapsed = time.time() - t0
            tps = tokens / max(0.5, elapsed)
            results[m] = round(tps, 1)
        except Exception as e:
            logger.warning(f"Failed to calibrate {m}: {e}")
            results[m] = 15.0

    try:
        with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    except Exception:
        pass

    return results
