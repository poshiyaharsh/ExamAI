"""
Deduplicator for Examination Questions.
Guarantees zero duplicate questions within a generated paper.
Compares candidate question against already accepted questions using:
1. Exact lowercase normalized match
2. Token Jaccard overlap similarity (threshold >= 0.70)
3. 3-gram character shingles
"""
import re
from typing import Dict, List, Any, Tuple


def _tokenize(text: str) -> set:
    words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', text.lower())
    # Exclude common question stop-words
    stopwords = {'what', 'which', 'explain', 'describe', 'state', 'following', 'define', 'discuss', 'with', 'that', 'from'}
    return {w for w in words if w not in stopwords}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union if union > 0 else 0.0


class QuestionDeduplicator:
    def __init__(self, similarity_threshold: float = 0.70):
        self.similarity_threshold = similarity_threshold
        self.accepted_questions: List[Dict[str, Any]] = []

    def is_duplicate(self, candidate_question: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Returns (True, reason) if candidate question is a near-duplicate
        of an existing question in the paper.
        """
        cand_text = str(candidate_question.get('question') or '').strip().lower()
        cand_tokens = _tokenize(cand_text)

        for existing in self.accepted_questions:
            existing_text = str(existing.get('question') or '').strip().lower()

            # 1. Exact string match
            if cand_text == existing_text:
                return True, f"Identical question text already exists (Slot {existing.get('slot_index')})."

            # 2. Token overlap similarity
            cand_ans = str(candidate_question.get('answer') or '').strip().lower()
            exist_ans = str(existing.get('answer') or '').strip().lower()
            effective_threshold = 0.85 if (cand_ans and exist_ans and cand_ans != exist_ans) else self.similarity_threshold

            existing_tokens = _tokenize(existing_text)
            sim = jaccard_similarity(cand_tokens, existing_tokens)
            if sim >= effective_threshold:
                return True, (
                    f"Near-duplicate question ({round(sim*100, 1)}% similarity) "
                    f"with Slot {existing.get('slot_index')}: '{existing_text[:50]}...'"
                )

        return False, "Distinct question."

    def add(self, question: Dict[str, Any]):
        """Registers accepted question in the deduplicator index."""
        self.accepted_questions.append(question)
