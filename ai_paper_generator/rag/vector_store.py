"""
Local Vector Store for RAG.
Stores embeddings and chunk metadata in an isolated index per generation job.
Ensures generation jobs never mix material.
Supports persistence to UTF-8 JSON for job resumability.
"""
import json
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from ..config import RAG_STORAGE_DIR
from .embedder import RAGEmbedder


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculates cosine similarity between two normalized or raw vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class LocalVectorStore:
    def __init__(
        self,
        job_id: int,
        embedder: Optional[RAGEmbedder] = None,
        language: str = "en"
    ):
        self.job_id = job_id
        self.language = language or "en"
        self.embedder = embedder or RAGEmbedder(language=self.language)
        self.chunks: List[Dict[str, Any]] = []
        self.vectors: List[List[float]] = []
        self.storage_file = RAG_STORAGE_DIR / f"job_{job_id}.json"

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """Adds text chunks, generates embeddings, and saves to job index."""
        if not chunks:
            return

        texts = [c['text'] for c in chunks]
        self.embedder.initialize(texts)

        for chunk in chunks:
            vec = self.embedder.embed_text(chunk['text'])
            self.chunks.append(chunk)
            self.vectors.append(vec)

        self.save_to_disk()

    def similarity_search(self, query: str, top_k: int = 4, topic_filter: Optional[str] = None) -> List[Tuple[Dict[str, Any], float]]:
        """
        Retrieves top_k most relevant chunks using cosine similarity.
        Optionally filters by unit/topic.
        """
        if not self.chunks or not self.vectors:
            self.load_from_disk()

        if not self.chunks or not self.vectors:
            return []

        query_vec = self.embedder.embed_text(query)
        scored_results = []

        for idx, (chunk, vec) in enumerate(zip(self.chunks, self.vectors)):
            # Optional topic match boost
            score = cosine_similarity(query_vec, vec)
            if topic_filter and topic_filter.lower() in chunk.get('topic', '').lower():
                score += 0.15  # topic alignment boost

            scored_results.append((chunk, score))

        # Sort descending by score
        scored_results.sort(key=lambda item: item[1], reverse=True)
        return scored_results[:top_k]

    def save_to_disk(self):
        """Persists the vector store to disk for job resumability with ensure_ascii=False."""
        data = {
            'job_id': self.job_id,
            'language': self.language,
            'model_name': getattr(self.embedder, 'model_name', None),
            'chunks': self.chunks,
            'vectors': self.vectors,
        }
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def load_from_disk(self) -> bool:
        """Loads cached vector store from disk."""
        if not self.storage_file.exists():
            return False
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.chunks = data.get('chunks', [])
            self.vectors = data.get('vectors', [])
            saved_lang = data.get('language')
            if saved_lang:
                self.language = saved_lang
            return True
        except Exception:
            return False

    def clear(self):
        """Removes local storage for this job."""
        if self.storage_file.exists():
            try:
                self.storage_file.unlink()
            except Exception:
                pass
        self.chunks = []
        self.vectors = []
