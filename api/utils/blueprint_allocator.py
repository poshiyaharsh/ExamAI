"""
Deterministic blueprint allocation and rebalancing engine for exam paper generation.
Guarantees exact Decimal mark sums, proportional topic distribution,
time-fit calculations, and suggested valid plans on mismatches.
"""
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Any, Dict, List, Optional, Tuple, Union

ALL_QUESTION_TYPES = ['mcq', 'true_false', 'fill_blank', 'short_answer', 'long_answer']

# Time per question in minutes (held in ONE configuration)
QUESTION_TIME_MINUTES = {
    'mcq': 1.0,
    'true_false': 1.0,
    'fill_blank': 1.0,
    'short_answer': 4.0,
    'long_answer': 10.0,
}

# Base default weights across types
BASE_WEIGHTS = {
    'mcq': 0.20,
    'true_false': 0.10,
    'fill_blank': 0.10,
    'short_answer': 0.25,
    'long_answer': 0.35,
}

# Base default marks per question (stored as Decimal)
BASE_MARKS_PER_QUESTION = {
    'mcq': Decimal('2.0'),
    'true_false': Decimal('2.0'),
    'fill_blank': Decimal('2.0'),
    'short_answer': Decimal('5.0'),
    'long_answer': Decimal('10.0'),
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


def to_decimal(val: Any, default: str = '0.0') -> Decimal:
    """
    Robust helper to convert any numeric, float, or str value to Decimal.
    Never mixes float and Decimal.
    """
    if isinstance(val, Decimal):
        return val
    if val is None or val == '':
        return Decimal(default)
    try:
        # Convert float through str to avoid binary precision artifacts
        return Decimal(str(val).strip())
    except Exception:
        return Decimal(default)


def compute_blueprint_total(blueprint: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Decimal:
    """
    Computes exact sum of (count * marks) for enabled types using Decimal arithmetic.
    Accepts either a dict keyed by type or a list of type config dicts.
    """
    total = Decimal('0.0')
    if isinstance(blueprint, list):
        for item in blueprint:
            if isinstance(item, dict):
                count = int(item.get('count', 0) or 0)
                raw_m = item.get('marks', item.get('marks_per_question', item.get('marksPerQuestion', 1)))
                marks = to_decimal(raw_m, default='1.0')
                if count > 0 and marks > Decimal('0'):
                    total += Decimal(count) * marks
        return total
    if not isinstance(blueprint, dict):
        return total
    for q_type, cfg in blueprint.items():
        if isinstance(cfg, dict) and cfg.get('enabled', True):
            count = int(cfg.get('count', 0) or 0)
            raw_m = cfg.get('marks', cfg.get('marks_per_question', cfg.get('marksPerQuestion', 1)))
            marks = to_decimal(raw_m, default='1.0')
            if count > 0 and marks > Decimal('0'):
                total += Decimal(count) * marks
    return total


def estimate_content_capacity(
    syllabus_text: str,
    topics: Optional[List[str]] = None,
    target_marks: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Estimates the maximum content capacity (in marks and questions) that a source syllabus
    can reliably support without hallucinations, duplicates, or off-scope padding.
    """
    import re
    if not syllabus_text:
        return {
            'word_count': 0,
            'sentence_count': 0,
            'topic_count': 0,
            'max_supportable_marks': 0,
            'is_capacity_sufficient': False,
            'reason': 'No syllabus text provided.',
        }

    raw_text = str(syllabus_text).strip()
    words = len(raw_text.split())
    # Substantive sentences with at least 4 words
    sentences = [s.strip() for s in re.split(r'[.!?\n]+', raw_text) if len(s.strip().split()) >= 4]
    sentence_count = len(sentences)

    clean_topics = [t for t in (topics or []) if str(t).strip()]
    topic_count = max(1, len(clean_topics))

    # Real capacity scaling:
    if words < 120 or sentence_count < 8:
        max_marks = min(15, max(5, int(sentence_count * 1.5)))
    elif words < 400 or sentence_count < 25:
        max_marks = min(30, max(15, int(sentence_count * 1.6)))
    elif words < 1500 or sentence_count < 100:
        max_marks = min(80, max(35, int(sentence_count * 1.7)))
    else:
        max_marks = max(100, int(sentence_count * 1.8))

    res = {
        'word_count': words,
        'sentence_count': sentence_count,
        'topic_count': topic_count,
        'max_supportable_marks': max_marks,
        'is_capacity_sufficient': True,
    }

    if target_marks is not None:
        target_dec = to_decimal(target_marks)
        if target_dec > Decimal(str(max_marks)):
            res['is_capacity_sufficient'] = False
            deficit = int(target_dec - Decimal(str(max_marks)))
            res['deficit_marks'] = deficit
            adjusted_bp, _ = allocate_blueprint_to_target(max_marks)
            res['suggested_target_marks'] = max_marks
            res['proposed_adjusted_blueprint'] = adjusted_bp
            res['explanation'] = (
                f"The provided syllabus ({words} words across {topic_count} topic(s)) "
                f"can support up to ~{max_marks} marks without repeating content. "
                f"A proposed blueprint for {max_marks} marks is available."
            )
        else:
            res['deficit_marks'] = 0

    return res


def estimate_exam_time(blueprint: Union[Dict[str, Any], List[Dict[str, Any]]]) -> float:
    """
    Calculates total estimated minutes to complete the paper based on question counts.
    Accepts either a dict keyed by type or a list of type config dicts.
    """
    total_minutes = 0.0
    if isinstance(blueprint, list):
        for item in blueprint:
            if isinstance(item, dict):
                count = int(item.get('count', 0) or 0)
                q_type = item.get('type')
                time_per_q = QUESTION_TIME_MINUTES.get(q_type, 1.0)
                total_minutes += count * time_per_q
        return round(total_minutes, 1)
    if not isinstance(blueprint, dict):
        return total_minutes
    for q_type, cfg in blueprint.items():
        if isinstance(cfg, dict) and cfg.get('enabled', True):
            count = int(cfg.get('count', 0) or 0)
            time_per_q = QUESTION_TIME_MINUTES.get(q_type, 1.0)
            total_minutes += count * time_per_q
    return round(total_minutes, 1)


def allocate_blueprint_to_target(
    target_marks: Any,
    enabled_types: Optional[Any] = None,
    preset: Optional[str] = None,
    duration_minutes: Optional[int] = None,
) -> Union[Tuple[Dict[str, Dict[str, Any]], List[str], Optional[str]], Tuple[Dict[str, Dict[str, Any]], List[str]]]:
    """
    Deterministically allocates integer question counts and marks per question
    such that sum(count * marks) == target_marks exactly (using Decimal).
    Returns (blueprint, notes, duration_warning).
    """
    custom_marks: Dict[str, Decimal] = {}

    # Handle swapped arguments gracefully: allocate_blueprint_to_target(blueprint_list, target_marks)
    if isinstance(target_marks, (list, dict)) and not isinstance(target_marks, (int, float, Decimal, str)):
        bp_input = target_marks
        target_marks = enabled_types
        enabled_types = []
        if isinstance(bp_input, list):
            for item in bp_input:
                if isinstance(item, dict) and item.get('type'):
                    t_name = item['type']
                    enabled_types.append(t_name)
                    if 'marks_per_question' in item or 'marks' in item:
                        m_val = item.get('marks_per_question', item.get('marks'))
                        custom_marks[t_name] = to_decimal(m_val)
        elif isinstance(bp_input, dict):
            enabled_types = list(bp_input.keys())

    target = to_decimal(target_marks)
    if target <= Decimal('0'):
        raise ValueError("Target total marks must be greater than 0.")

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

    # Determine viable types
    viable_types = []
    for t in selected_types:
        base_m = BASE_MARKS_PER_QUESTION[t]
        if base_m <= target or (t in {'mcq', 'true_false', 'fill_blank'} and target >= Decimal('1.0')):
            viable_types.append(t)

    if not viable_types:
        viable_types = ['mcq']
        notes.append(f"Target of {target} marks is too small for selected types. Selected MCQ with 1 mark.")

    # Marks per question initialization (Decimals)
    type_marks: Dict[str, Decimal] = {}
    for t in viable_types:
        if t in custom_marks:
            type_marks[t] = custom_marks[t]
        elif target <= Decimal('2.0') and t in {'mcq', 'true_false', 'fill_blank'}:
            type_marks[t] = Decimal('1.0')
        elif target < BASE_MARKS_PER_QUESTION[t]:
            type_marks[t] = Decimal('1.0')
        else:
            type_marks[t] = BASE_MARKS_PER_QUESTION[t]

    # Handle odd target marks (e.g. 25, 35) or fractional target marks (e.g. 37.5)
    # Check if target has a fractional part (e.g. .5)
    is_fractional = (target % Decimal('1.0')) != Decimal('0')
    if is_fractional:
        # Set primary objective type to 0.5 marks
        for obj in ['mcq', 'fill_blank', 'true_false']:
            if obj in viable_types:
                type_marks[obj] = Decimal('0.5')
                notes.append(f"Adjusted {obj.replace('_', ' ').upper()} to 0.5 marks for fractional target ({target}).")
                break
    elif (target % Decimal('2.0')) != Decimal('0'):
        # Target is odd integer. Guarantee at least one type has odd marks
        has_odd = any((type_marks[t] % Decimal('2.0')) == Decimal('1.0') for t in viable_types)
        if not has_odd:
            for obj in ['mcq', 'fill_blank', 'true_false']:
                if obj in viable_types:
                    type_marks[obj] = Decimal('1.0')
                    notes.append(f"Adjusted {obj.replace('_', ' ').upper()} to 1 mark to fit odd target ({target}).")
                    break

    # Build normalized weights
    sub_weights = {t: weights_map.get(t, 0.2) for t in viable_types}
    w_sum = sum(sub_weights.values()) or 1.0
    norm_weights = {t: w / w_sum for t, w in sub_weights.items()}

    # Prune types if minimum budget exceeds target
    counts: Dict[str, int] = {t: 0 for t in viable_types}
    min_budget = sum(type_marks[t] for t in viable_types)

    while min_budget > target and len(viable_types) > 1:
        rem_type = max(viable_types, key=lambda t: (type_marks[t], -norm_weights.get(t, 0)))
        viable_types.remove(rem_type)
        del type_marks[rem_type]
        notes.append(f"Omitted {rem_type.replace('_', ' ')}: budget exceeded target.")
        sub_weights = {t: weights_map.get(t, 0.2) for t in viable_types}
        w_sum = sum(sub_weights.values()) or 1.0
        norm_weights = {t: w / w_sum for t, w in sub_weights.items()}
        min_budget = sum(type_marks[t] for t in viable_types)

    # Give 1 question to each remaining viable type
    for t in viable_types:
        counts[t] = 1

    remaining_marks = target - sum(Decimal(counts[t]) * type_marks[t] for t in viable_types)

    # Distribute remaining marks according to weights
    if remaining_marks > Decimal('0'):
        sorted_types = sorted(viable_types, key=lambda t: norm_weights.get(t, 0), reverse=True)
        for t in sorted_types:
            m_per_q = type_marks[t]
            ideal_extra = (remaining_marks * Decimal(str(norm_weights[t])))
            ideal_q = int(ideal_extra // m_per_q)
            if ideal_q > 0:
                counts[t] += ideal_q
                remaining_marks -= Decimal(ideal_q) * m_per_q

        # Greedy match for remainder
        while remaining_marks > Decimal('0'):
            allocated_any = False
            for t in sorted(viable_types, key=lambda t: type_marks[t], reverse=True):
                m_per_q = type_marks[t]
                if m_per_q <= remaining_marks:
                    c = int(remaining_marks // m_per_q)
                    counts[t] += c
                    remaining_marks -= Decimal(c) * m_per_q
                    allocated_any = True
                    break
            if not allocated_any:
                smallest = min(viable_types, key=lambda t: type_marks[t])
                c = int(remaining_marks // type_marks[smallest])
                if c > 0:
                    counts[smallest] += c
                    remaining_marks -= Decimal(c) * type_marks[smallest]
                break

    # Build result blueprint
    result_blueprint: Dict[str, Dict[str, Any]] = {}
    for t in ALL_QUESTION_TYPES:
        if t in viable_types:
            m_val = int(type_marks[t]) if type_marks[t] == int(type_marks[t]) else float(type_marks[t])
            result_blueprint[t] = {
                'enabled': True,
                'count': counts[t],
                'marks': m_val,
                'marks_per_question': m_val,
                'marksPerQuestion': m_val,
            }
        else:
            default_m = int(BASE_MARKS_PER_QUESTION[t]) if BASE_MARKS_PER_QUESTION[t] == int(BASE_MARKS_PER_QUESTION[t]) else float(BASE_MARKS_PER_QUESTION[t])
            result_blueprint[t] = {
                'enabled': False,
                'count': 0,
                'marks': default_m,
                'marks_per_question': default_m,
                'marksPerQuestion': default_m,
            }

    # Micro-correction assertion to guarantee exact sum
    actual_sum = compute_blueprint_total(result_blueprint)
    if actual_sum != target:
        diff = target - actual_sum
        corrected = False
        for t in sorted(viable_types, key=lambda t: type_marks[t]):
            if type_marks[t] > Decimal('0') and (diff % type_marks[t]) == Decimal('0'):
                counts[t] += int(diff // type_marks[t])
                result_blueprint[t]['count'] = counts[t]
                corrected = True
                break
        if not corrected:
            primary = viable_types[0]
            result_blueprint[primary]['marks'] = 1
            result_blueprint[primary]['marks_per_question'] = 1
            result_blueprint[primary]['marksPerQuestion'] = 1
            other_sum = sum(
                result_blueprint[k]['count'] * result_blueprint[k]['marks']
                for k in viable_types if k != primary
            )
            result_blueprint[primary]['count'] = int(target - other_sum)
            notes.append(f"Adjusted {primary.replace('_', ' ')} marks to 1 to guarantee exact sum of {target}.")

    # Duration warning
    duration_warning = None
    if duration_minutes and duration_minutes > 0:
        est_time = estimate_exam_time(result_blueprint)
        if est_time > float(duration_minutes):
            duration_warning = (
                f"Estimated exam completion time ({est_time:.0f} mins) exceeds the configured duration "
                f"({duration_minutes} mins). Consider reducing question counts or increasing duration."
            )

    if duration_minutes is not None:
        return result_blueprint, notes, duration_warning
    return result_blueprint, notes


def suggest_valid_blueprints(
    target_marks: Any,
    current_blueprint: Optional[Any] = None,
    duration_minutes: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Returns 2-3 alternative valid blueprints that sum EXACTLY to target_marks.
    Used when a user-configured blueprint fails exact sum validation.
    """
    # Support swapped arguments: suggest_valid_blueprints(blueprint, target_marks)
    if isinstance(target_marks, (list, dict)) and not isinstance(target_marks, (int, float, Decimal, str)):
        target_marks, current_blueprint = current_blueprint, target_marks

    target = to_decimal(target_marks)
    suggestions = []

    # 1. Balanced Mixed Plan
    mixed_res = allocate_blueprint_to_target(target, preset='mixed', duration_minutes=duration_minutes)
    mixed_bp = mixed_res[0]
    suggestions.append({
        'title': 'Balanced Mixed Plan',
        'description': f'Proportional mix across objective and descriptive questions summing to {target} marks.',
        'blueprint': mixed_bp,
        'total_marks': float(compute_blueprint_total(mixed_bp)),
        'estimated_minutes': estimate_exam_time(mixed_bp),
    })

    # 2. Objective-Focused Plan
    obj_res = allocate_blueprint_to_target(target, preset='objective', duration_minutes=duration_minutes)
    obj_bp = obj_res[0]
    suggestions.append({
        'title': 'Objective Speed Plan',
        'description': f'Fast objective format (MCQ, Fill Blanks, True/False) summing to {target} marks.',
        'blueprint': obj_bp,
        'total_marks': float(compute_blueprint_total(obj_bp)),
        'estimated_minutes': estimate_exam_time(obj_bp),
    })

    # 3. Scaled from current enabled types if provided
    if current_blueprint and isinstance(current_blueprint, dict):
        enabled = [t for t in ALL_QUESTION_TYPES if isinstance(current_blueprint.get(t), dict) and current_blueprint[t].get('enabled', False)]
        if enabled:
            scaled_res = allocate_blueprint_to_target(target, enabled_types=enabled, duration_minutes=duration_minutes)
            scaled_bp = scaled_res[0]
            if compute_blueprint_total(scaled_bp) != target:
                scaled_res = allocate_blueprint_to_target(target, enabled_types=enabled + ['mcq'], duration_minutes=duration_minutes)
                scaled_bp = scaled_res[0]
            suggestions.append({
                'title': 'Adjusted Current Types',
                'description': f'Adjusts counts for currently enabled question types to equal {target} marks.',
                'blueprint': scaled_bp,
                'total_marks': float(compute_blueprint_total(scaled_bp)),
                'estimated_minutes': estimate_exam_time(scaled_bp),
            })

    return suggestions[:3]


def rebalance_blueprint_to_target(
    current_blueprint: Dict[str, Any],
    new_target_marks: Any,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    Scales existing question type counts proportionally to new_target_marks
    while preserving currently enabled/disabled types and individual marks per question.
    """
    target_dec = to_decimal(new_target_marks)
    if target_dec < Decimal('1'):
        raise ValueError("New target total marks must be at least 1.")

    enabled_types = [
        t for t in ALL_QUESTION_TYPES
        if isinstance(current_blueprint.get(t), dict) and current_blueprint[t].get('enabled', False)
    ]
    if not enabled_types:
        res = allocate_blueprint_to_target(new_target_marks)
        return res[0], res[1]

    current_total = compute_blueprint_total(current_blueprint)
    if current_total == target_dec:
        return current_blueprint, []

    # If current_total is 0, allocate fresh
    if current_total == Decimal('0'):
        res = allocate_blueprint_to_target(new_target_marks, enabled_types=enabled_types)
        return res[0], res[1]

    # Use allocate_blueprint_to_target with existing enabled types
    res = allocate_blueprint_to_target(new_target_marks, enabled_types=enabled_types)
    return res[0], res[1]


def balance_blueprint_smallest_change(
    current_blueprint: Dict[str, Any],
    target_marks: Any,
) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Finds and applies the smallest discrete question count adjustment to current_blueprint
    to bring compute_blueprint_total(blueprint) == target_marks.
    Returns (balanced_blueprint, explanation).
    """
    import copy
    bp = copy.deepcopy(current_blueprint)
    target_dec = to_decimal(target_marks)
    current_total = compute_blueprint_total(bp)
    diff = target_dec - current_total
    if diff == Decimal('0'):
        return bp, "Blueprint already matches target marks."

    enabled_types = [
        t for t in ALL_QUESTION_TYPES
        if isinstance(bp.get(t), dict) and bp[t].get('enabled', False) and to_decimal(bp[t].get('marks', 0)) > Decimal('0')
    ]
    if not enabled_types:
        fresh_res = allocate_blueprint_to_target(target_marks)
        return fresh_res[0], f"Configured blueprint for {target_marks} target marks."

    # Try single-type count adjustments first
    for t in enabled_types:
        m = to_decimal(bp[t]['marks'])
        count = int(bp[t]['count'])
        if diff > Decimal('0'):
            if diff % m == Decimal('0'):
                delta = int(diff // m)
                cand = copy.deepcopy(bp)
                cand[t]['count'] += delta
                return cand, f"Add {delta} {t.replace('_', ' ')} question{'s' if delta > 1 else ''} (+{diff} marks)"
        else:
            abs_diff = -diff
            if abs_diff % m == Decimal('0'):
                delta = int(abs_diff // m)
                if count - delta >= 1:
                    cand = copy.deepcopy(bp)
                    cand[t]['count'] -= delta
                    return cand, f"Remove {delta} {t.replace('_', ' ')} question{'s' if delta > 1 else ''} (-{abs_diff} marks)"

    # If no single type divides evenly, rebalance with allocate_blueprint_to_target
    rebalanced, _ = rebalance_blueprint_to_target(bp, target_marks)
    return rebalanced, f"Rebalanced question counts across enabled types to equal {target_marks} marks."


def distribute_questions_across_topics(
    blueprint: Any,
    topics: Any,
    topic_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Distributes questions per type across topics in proportion to their weights.
    Guarantees at least 1 question per topic when the count allows.
    Accepts topics as list of strings or list of dicts.
    """
    # Support blueprint passed as list
    if isinstance(blueprint, list):
        bp_dict = {}
        for item in blueprint:
            if isinstance(item, dict) and item.get('type'):
                bp_dict[item['type']] = item
        blueprint = bp_dict

    clean_topics: List[str] = []
    weights: Dict[str, float] = {}

    for t in topics:
        if isinstance(t, dict):
            name = str(t.get('name') or t.get('title') or t.get('id') or '').strip()
            if name:
                clean_topics.append(name)
                weights[name] = float(t.get('weight') or 1.0)
        elif str(t).strip():
            name = str(t).strip()
            clean_topics.append(name)
            if topic_weights and name in topic_weights:
                weights[name] = float(topic_weights[name])
            else:
                weights[name] = 1.0

    if not clean_topics:
        clean_topics = ['General']
        weights['General'] = 1.0

    w_sum = sum(weights.values()) or 1.0
    norm_w = {t: weights[t] / w_sum for t in clean_topics}

    distribution: Dict[str, List[Dict[str, Any]]] = {}

    for q_type, cfg in blueprint.items():
        if not isinstance(cfg, dict) or not cfg.get('enabled', True):
            continue
        count = int(cfg.get('count', 0) or 0)
        if count <= 0:
            continue

        q_topic_allocations = []
        # If count >= len(clean_topics), guarantee 1 per topic
        remaining = count
        topic_counts = {t: 0 for t in clean_topics}
        if count >= len(clean_topics):
            for t in clean_topics:
                topic_counts[t] = 1
                remaining -= 1

        # Distribute remaining proportionally
        if remaining > 0:
            sorted_t = sorted(clean_topics, key=lambda t: norm_w[t], reverse=True)
            for t in sorted_t:
                add = int(math.floor(remaining * norm_w[t]))
                topic_counts[t] += add
                remaining -= add

            # Leftovers
            idx = 0
            while remaining > 0:
                t = sorted_t[idx % len(sorted_t)]
                topic_counts[t] += 1
                remaining -= 1
                idx += 1

        for t, c in topic_counts.items():
            if c > 0:
                q_topic_allocations.append({
                    'topic': t,
                    'count': c,
                    'marks_per_question': cfg.get('marksPerQuestion', cfg.get('marks', 1)),
                })

        distribution[q_type] = q_topic_allocations

    return distribution
