"""
Deterministic blueprint allocation and rebalancing engine for exam paper generation.
"""
from typing import Dict, List, Optional, Tuple, Any

ALL_QUESTION_TYPES = ['mcq', 'true_false', 'fill_blank', 'short_answer', 'long_answer']

# Base default weights across types
BASE_WEIGHTS = {
    'mcq': 0.20,
    'true_false': 0.10,
    'fill_blank': 0.10,
    'short_answer': 0.25,
    'long_answer': 0.35,
}

# Base default marks per question
BASE_MARKS_PER_QUESTION = {
    'mcq': 2,
    'true_false': 2,
    'fill_blank': 2,
    'short_answer': 5,
    'long_answer': 10,
}

PRESET_WEIGHTS = {
    'mixed': {
        'mcq': 0.20,
        'true_false': 0.10,
        'fill_blank': 0.10,
        'short_answer': 0.25,
        'long_answer': 0.35,
    },
    'objective': {
        'mcq': 0.40,
        'true_false': 0.30,
        'fill_blank': 0.30,
        'short_answer': 0.0,
        'long_answer': 0.0,
    },
    'subjective': {
        'mcq': 0.0,
        'true_false': 0.0,
        'fill_blank': 0.0,
        'short_answer': 0.40,
        'long_answer': 0.60,
    },
}


def compute_blueprint_total(blueprint: Dict[str, Any]) -> int:
    """
    Computes sum of (count * marks) for enabled types.
    """
    total = 0
    if not isinstance(blueprint, dict):
        return 0
    for q_type, cfg in blueprint.items():
        if isinstance(cfg, dict) and cfg.get('enabled', True):
            count = int(cfg.get('count', 0) or 0)
            marks = int(cfg.get('marks', cfg.get('marks_per_question', cfg.get('marksPerQuestion', 1))) or 1)
            total += max(0, count) * max(1, marks)
    return total


def allocate_blueprint_to_target(
    target_marks: int,
    enabled_types: Optional[List[str]] = None,
    preset: Optional[str] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    Deterministically allocates integer question counts and marks per question
    such that sum(count * marks) == target_marks exactly.
    Returns (blueprint, notes).
    """
    if target_marks < 1:
        raise ValueError("Target total marks must be at least 1.")

    notes: List[str] = []

    # Determine types
    if preset in PRESET_WEIGHTS:
        weights_map = PRESET_WEIGHTS[preset]
        selected_types = [t for t in ALL_QUESTION_TYPES if weights_map.get(t, 0.0) > 0]
    else:
        if enabled_types:
            selected_types = [t for t in enabled_types if t in ALL_QUESTION_TYPES]
        else:
            selected_types = list(ALL_QUESTION_TYPES)
        weights_map = BASE_WEIGHTS

    if not selected_types:
        selected_types = ['mcq']
        notes.append("No valid question types enabled; defaulted to MCQ.")

    # Filter out types whose minimum marks exceed target_marks
    viable_types = []
    for t in selected_types:
        base_m = BASE_MARKS_PER_QUESTION[t]
        if base_m <= target_marks or (t in {'mcq', 'true_false', 'fill_blank'} and target_marks >= 1):
            viable_types.append(t)

    if not viable_types:
        # Target is smaller than even the smallest selected type's default marks
        viable_types = ['mcq']
        notes.append(f"Target of {target_marks} marks is too small for selected types. Selected MCQ with 1 mark.")

    if len(viable_types) < len(selected_types):
        omitted = [t for t in selected_types if t not in viable_types]
        notes.append(f"Target marks ({target_marks}) too low to include: {', '.join(omitted)}.")

    # Initialize marks per question
    type_marks: Dict[str, int] = {}
    for t in viable_types:
        if target_marks == 1 and t in {'mcq', 'true_false', 'fill_blank'}:
            type_marks[t] = 1
        elif target_marks < BASE_MARKS_PER_QUESTION[t]:
            type_marks[t] = 1
        else:
            type_marks[t] = BASE_MARKS_PER_QUESTION[t]

    # If target is odd, we need an odd sum.
    # Check if any viable type has odd marks (short_answer=5, or 1-mark objective).
    # If all viable types currently have even marks (e.g. 2, 2, 2, 10), adjust an objective type to 1 mark.
    if target_marks % 2 == 1:
        has_odd = any(type_marks[t] % 2 == 1 for t in viable_types)
        if not has_odd:
            # Drop MCQ or another objective type to 1 mark
            for obj in ['mcq', 'fill_blank', 'true_false']:
                if obj in viable_types:
                    type_marks[obj] = 1
                    notes.append(f"Adjusted {obj.replace('_', ' ').upper()} to 1 mark per question to accommodate odd target ({target_marks}).")
                    break

    # Build weights normalized for viable types
    sub_weights = {t: weights_map.get(t, 0.2) for t in viable_types}
    w_sum = sum(sub_weights.values()) or 1.0
    norm_weights = {t: w / w_sum for t, w in sub_weights.items()}

    # Guarantee at least 1 question per viable type if budget allows
    counts: Dict[str, int] = {t: 0 for t in viable_types}
    min_budget = sum(type_marks[t] for t in viable_types)

    # If target < min_budget, we cannot give 1 question to every viable type.
    # Prune types from the heaviest (longest) downwards until target >= min_budget.
    while min_budget > target_marks and len(viable_types) > 1:
        # remove the type with highest type_marks or lowest weight
        rem_type = max(viable_types, key=lambda t: (type_marks[t], -norm_weights.get(t, 0)))
        viable_types.remove(rem_type)
        del type_marks[rem_type]
        notes.append(f"Target {target_marks} is too small to include {rem_type.replace('_', ' ')}; omitted to maintain valid blueprint.")
        # re-normalize
        sub_weights = {t: weights_map.get(t, 0.2) for t in viable_types}
        w_sum = sum(sub_weights.values()) or 1.0
        norm_weights = {t: w / w_sum for t, w in sub_weights.items()}
        min_budget = sum(type_marks[t] for t in viable_types)

    # Now give 1 question to each remaining viable type
    for t in viable_types:
        counts[t] = 1

    remaining_marks = target_marks - sum(counts[t] * type_marks[t] for t in viable_types)

    # Distribute remaining marks according to weights
    if remaining_marks > 0:
        # Sort types by descending weight
        sorted_types = sorted(viable_types, key=lambda t: norm_weights.get(t, 0), reverse=True)
        # Attempt to allocate to each type based on its target share
        for t in sorted_types:
            m_per_q = type_marks[t]
            ideal_extra_marks = remaining_marks * norm_weights[t]
            ideal_extra_q = int(ideal_extra_marks // m_per_q)
            if ideal_extra_q > 0:
                counts[t] += ideal_extra_q
                remaining_marks -= ideal_extra_q * m_per_q

        # Greedy allocation for any leftover remainder
        # Try from types with largest mark that fits into remaining_marks, down to 1
        while remaining_marks > 0:
            allocated_any = False
            for t in sorted(viable_types, key=lambda t: type_marks[t], reverse=True):
                m_per_q = type_marks[t]
                if m_per_q <= remaining_marks:
                    counts[t] += 1
                    remaining_marks -= m_per_q
                    allocated_any = True
                    break
            if not allocated_any:
                # If leftover remainder cannot be matched by existing type_marks
                # (e.g. remaining 1 mark, but all types have >= 2 marks),
                # adjust an objective type to 1 mark or add 1 mark
                obj_found = False
                for obj in ['mcq', 'fill_blank', 'true_false']:
                    if obj in viable_types:
                        # Convert its marks to 1 and adjust count
                        old_m = type_marks[obj]
                        if old_m > 1:
                            type_marks[obj] = 1
                            counts[obj] = counts[obj] * old_m + remaining_marks
                            remaining_marks = 0
                            notes.append(f"Adjusted {obj.replace('_', ' ').upper()} to 1 mark to fit exact target.")
                            obj_found = True
                            break
                if not obj_found:
                    # As a last fallback, add remainder to the first type by adjusting its count
                    counts[viable_types[0]] += 1
                    remaining_marks = 0
                break

    # Construct complete blueprint structure for all 5 question types
    result_blueprint: Dict[str, Dict[str, Any]] = {}
    for t in ALL_QUESTION_TYPES:
        if t in viable_types:
            result_blueprint[t] = {
                'enabled': True,
                'count': counts[t],
                'marks': type_marks[t],
                'marks_per_question': type_marks[t],
                'marksPerQuestion': type_marks[t],
            }
        else:
            result_blueprint[t] = {
                'enabled': False,
                'count': 0,
                'marks': BASE_MARKS_PER_QUESTION[t],
                'marks_per_question': BASE_MARKS_PER_QUESTION[t],
                'marksPerQuestion': BASE_MARKS_PER_QUESTION[t],
            }

    # Final assertion
    actual_sum = compute_blueprint_total(result_blueprint)
    if actual_sum != target_marks:
        # Micro correction on primary enabled type
        diff = target_marks - actual_sum
        primary = viable_types[0]
        # adjust marks or count directly
        if diff % result_blueprint[primary]['marks'] == 0:
            result_blueprint[primary]['count'] += diff // result_blueprint[primary]['marks']
        else:
            result_blueprint[primary]['marks'] = 1
            result_blueprint[primary]['count'] = target_marks - sum(
                result_blueprint[k]['count'] * result_blueprint[k]['marks']
                for k in viable_types if k != primary
            )

    return result_blueprint, notes


def rebalance_blueprint_to_target(
    current_blueprint: Dict[str, Any],
    new_target_marks: int,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    Scales existing question type counts proportionally to new_target_marks
    while preserving currently enabled/disabled types and individual marks per question.
    """
    if new_target_marks < 1:
        raise ValueError("New target total marks must be at least 1.")

    enabled_types = [
        t for t in ALL_QUESTION_TYPES
        if isinstance(current_blueprint.get(t), dict) and current_blueprint[t].get('enabled', False)
    ]
    if not enabled_types:
        return allocate_blueprint_to_target(new_target_marks)

    current_total = compute_blueprint_total(current_blueprint)
    if current_total == new_target_marks:
        return current_blueprint, []

    # If current_total is 0, allocate fresh
    if current_total == 0:
        return allocate_blueprint_to_target(new_target_marks, enabled_types=enabled_types)

    # Use allocate_blueprint_to_target with existing enabled types
    return allocate_blueprint_to_target(new_target_marks, enabled_types=enabled_types)


def balance_blueprint_smallest_change(
    current_blueprint: Dict[str, Any],
    target_marks: int,
) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Finds and applies the smallest discrete question count adjustment to current_blueprint
    to bring compute_blueprint_total(blueprint) == target_marks.
    Returns (balanced_blueprint, explanation).
    """
    import copy
    bp = copy.deepcopy(current_blueprint)
    current_total = compute_blueprint_total(bp)
    diff = target_marks - current_total
    if diff == 0:
        return bp, "Blueprint already matches target marks."

    enabled_types = [
        t for t in ALL_QUESTION_TYPES
        if isinstance(bp.get(t), dict) and bp[t].get('enabled', False) and bp[t].get('marks', 0) > 0
    ]
    if not enabled_types:
        fresh, _ = allocate_blueprint_to_target(target_marks)
        return fresh, f"Configured blueprint for {target_marks} target marks."

    # Try single-type count adjustments first
    for t in enabled_types:
        m = bp[t]['marks']
        count = bp[t]['count']
        if diff > 0:
            if diff % m == 0:
                delta = diff // m
                cand = copy.deepcopy(bp)
                cand[t]['count'] += delta
                return cand, f"Add {delta} {t.replace('_', ' ')} question{'s' if delta > 1 else ''} (+{diff} marks)"
        else:
            abs_diff = -diff
            if abs_diff % m == 0:
                delta = abs_diff // m
                if count - delta >= 1:
                    cand = copy.deepcopy(bp)
                    cand[t]['count'] -= delta
                    return cand, f"Remove {delta} {t.replace('_', ' ')} question{'s' if delta > 1 else ''} (-{abs_diff} marks)"

    # If no single type divides evenly, rebalance with allocate_blueprint_to_target
    rebalanced, _ = rebalance_blueprint_to_target(bp, target_marks)
    return rebalanced, f"Rebalanced question counts across enabled types to equal {target_marks} marks."

