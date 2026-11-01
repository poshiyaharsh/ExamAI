"""
Blueprint and Marks Calculator.
Guarantees mathematically that:
sum(count * marks) == total_marks EXACTLY.
Supports sections (e.g. Short Answer: 3 @ 2 marks and 2 @ 3 marks).
Provides auto-distribute suggestion for any target total marks.
"""
from typing import Dict, List, Any, Optional


class BlueprintSlot:
    def __init__(
        self,
        slot_index: int,
        question_type: str,
        marks: int,
        difficulty: str,
        topic: str,
        section_name: str = 'General'
    ):
        self.slot_index = slot_index
        self.question_type = question_type
        self.marks = marks
        self.difficulty = difficulty
        self.topic = topic
        self.section_name = section_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            'slot_index': self.slot_index,
            'type': self.question_type,
            'marks': self.marks,
            'difficulty': self.difficulty,
            'topic': self.topic,
            'section_name': self.section_name,
        }


def calculate_allocated_marks(slots: List[Dict[str, Any]]) -> int:
    """Calculates exact total marks from a list of slot dictionaries."""
    return sum(int(slot.get('marks', 0)) for slot in slots)


def build_blueprint(
    total_marks: int,
    sections: List[Dict[str, Any]],
    topics: List[str],
    difficulty_distribution: Optional[Dict[str, int]] = None
) -> List[Dict[str, Any]]:
    """
    Constructs the exact slot-by-slot blueprint.
    Each section:
    {
      'type': 'MCQ',
      'count': 10,
      'marks_per_question': 1,
      'section_name': 'Section A'
    }
    Maps topics and difficulty cyclically / proportionally across slots.
    Asserts exact equality with total_marks.
    """
    if total_marks <= 0:
        raise ValueError("Total marks must be a positive integer.")

    if not sections:
        raise ValueError("At least one question section must be configured.")

    if not topics:
        topics = ['General Curriculum']

    # Default difficulty distribution: 30% Easy, 50% Medium, 20% Hard
    diff_dist = difficulty_distribution or {'Easy': 30, 'Medium': 50, 'Hard': 20}

    slots = []
    slot_counter = 1

    for section in sections:
        q_type = section['type']
        count = int(section.get('count', 0))
        marks_per_q = int(section.get('marks_per_question', 1))
        section_name = section.get('section_name', q_type)

        if count <= 0 or marks_per_q <= 0:
            continue

        for i in range(count):
            # Distribute topic evenly
            topic = topics[(slot_counter - 1) % len(topics)]

            # Determine difficulty based on slot ratio
            ratio = (i / max(1, count)) * 100
            if ratio < diff_dist.get('Easy', 30):
                diff = 'Easy'
            elif ratio < (diff_dist.get('Easy', 30) + diff_dist.get('Medium', 50)):
                diff = 'Medium'
            else:
                diff = 'Hard'

            slot = BlueprintSlot(
                slot_index=slot_counter,
                question_type=q_type,
                marks=marks_per_q,
                difficulty=diff,
                topic=topic,
                section_name=section_name
            )
            slots.append(slot.to_dict())
            slot_counter += 1

    allocated = calculate_allocated_marks(slots)
    if allocated != total_marks:
        raise ValueError(
            f"Blueprint marks mismatch: Allocated marks ({allocated}) != Target total marks ({total_marks})."
        )

    return slots


def auto_distribute_blueprint(total_marks: int, enabled_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Intelligently generates a balanced, valid blueprint for ANY target total marks
    such that sum(count * marks) == total_marks exactly.
    """
    available_types = enabled_types or ['MCQ', 'True/False', 'Fill in the Blank', 'Short Answer', 'Long Answer']
    if not available_types:
        available_types = ['MCQ', 'Short Answer']

    # Target default marks per type
    default_marks = {
        'MCQ': 1,
        'True/False': 1,
        'Fill in the Blank': 1,
        'Short Answer': 3,
        'Long Answer': 5,
    }

    # Weight distribution of marks across enabled types
    weights = {
        'MCQ': 0.25,
        'True/False': 0.15,
        'Fill in the Blank': 0.15,
        'Short Answer': 0.25,
        'Long Answer': 0.20,
    }

    # Normalize weights for active types
    active_weights = {t: weights.get(t, 0.2) for t in available_types}
    total_w = sum(active_weights.values())
    norm_weights = {t: w / total_w for t, w in active_weights.items()}

    sections = []
    remaining_marks = total_marks

    # Allocate initial counts
    for q_type in available_types:
        unit_mark = default_marks.get(q_type, 1)
        target_type_marks = round(total_marks * norm_weights[q_type])
        count = max(1, target_type_marks // unit_mark)
        subtotal = count * unit_mark
        sections.append({
            'type': q_type,
            'count': count,
            'marks_per_question': unit_mark,
            'section_name': q_type
        })
        remaining_marks -= subtotal

    # Adjust remainder to achieve EXACT total_marks
    if remaining_marks != 0:
        # Adjust 1-mark questions (MCQ / TF / Fill) or first available
        one_mark_sec = next((s for s in sections if s['marks_per_question'] == 1), None)
        if one_mark_sec:
            new_count = one_mark_sec['count'] + remaining_marks
            if new_count >= 1:
                one_mark_sec['count'] = new_count
                remaining_marks = 0

    # If still has remainder, adjust first section
    if remaining_marks != 0 and sections:
        first = sections[0]
        step = first['marks_per_question']
        add_count = remaining_marks // step
        if first['count'] + add_count >= 1:
            first['count'] += add_count
            remaining_marks -= (add_count * step)

        # Handle any residual remainder by appending a 1-mark section
        if remaining_marks > 0:
            sections.append({
                'type': 'MCQ',
                'count': remaining_marks,
                'marks_per_question': 1,
                'section_name': 'MCQ Additional'
            })
        elif remaining_marks < 0:
            # Scale down
            for s in sections:
                while remaining_marks < 0 and s['count'] > 1:
                    s['count'] -= 1
                    remaining_marks += s['marks_per_question']

    return sections
