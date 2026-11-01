"""
RAG Retriever:
1. Retrieves top-k chunks per question slot based on topic, difficulty, and question type.
2. Spreads retrieval evenly across units/topics.
3. Supports retry expansion (top_k=top_k+2) when INSUFFICIENT_CONTEXT is flagged.
4. Logs retrieval details (query, chunk IDs, scores) to rag.log.
"""
import logging
from typing import Dict, List, Any, Optional
from ..config import TOP_K_RETRIEVAL
from .vector_store import LocalVectorStore
from ..logging_setup import log_event

logger = logging.getLogger(__name__)


class RAGRetriever:
    def __init__(self, vector_store: LocalVectorStore, job_id: int):
        self.vector_store = vector_store
        self.job_id = job_id

    def retrieve_context_for_slot(
        self,
        topic: str,
        question_type: str,
        difficulty: str,
        expansion_level: int = 0,
        unit_weightage: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Retrieves context for a question slot.
        If expansion_level > 0 (retry on INSUFFICIENT_CONTEXT), retrieves more chunks.
        Logs details to rag.log.
        """
        top_k = TOP_K_RETRIEVAL + (expansion_level * 2)
        query = f"Topic: {topic}. Academic concept for {difficulty} level {question_type} examination question."

        results = self.vector_store.similarity_search(query, top_k=top_k, topic_filter=topic)

        if not results:
            # Fallback to general search without topic filter if empty
            results = self.vector_store.similarity_search(query, top_k=top_k)

        chunk_ids = [c[0].get('chunk_id') for c in results]
        scores = [round(c[1], 4) for c in results]

        log_event(
            'RAG',
            f"Retrieved {len(results)} chunks for topic='{topic}', type='{question_type}' (expansion={expansion_level}). "
            f"Chunk IDs: {chunk_ids}, Scores: {scores}",
            job_id=self.job_id,
            details={'topic': topic, 'chunk_ids': chunk_ids, 'scores': scores}
        )

        if not results:
            return ""

        context_blocks = []
        for idx, (chunk, score) in enumerate(results, start=1):
            source = chunk.get('source', 'document')
            page = chunk.get('page', 1)
            text = chunk.get('text', '').strip()
            context_blocks.append(f"--- [Source: {source}, Section/Page {page}] ---\n{text}")

        return "\n\n".join(context_blocks)

    def retrieve_context_for_topics(self, topics: List[str], expansion_level: int = 0) -> str:
        """
        Retrieves context for a batch of topics.
        """
        if not topics:
            return ""
        contexts = []
        for t in topics:
            ctx = self.retrieve_context_for_slot(topic=t, question_type="Batch Questions", difficulty="Medium", expansion_level=expansion_level)
            if ctx:
                contexts.append(f"### Curriculum Focus: {t}\n{ctx}")
        return "\n\n".join(contexts)
