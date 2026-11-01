"""
Embedder for RAG.
1. Checks if Ollama has an embedding model (e.g., nomic-embed-text) installed and uses it.
2. If not, falls back to local fast TF-IDF / word-embedding vectorizer, ensuring zero crashes.
3. Logs all decisions to rag.log.
"""
import math
import re
import logging
from collections import Counter
from typing import List, Optional, Union
from ..config import PREFERRED_EMBEDDING_MODEL
from ..ollama_client import OllamaClient
from ..logging_setup import log_event

logger = logging.getLogger(__name__)


class LocalTfIdfEmbedder:
    """
    Self-contained, ultra-fast vectorizer.
    Produces normalized vector representations without requiring heavy PyTorch installations.
    """
    def __init__(self):
        self.vocab = {}
        self.idf = {}

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\b[a-zA-Z0-9_]{2,}\b', text.lower())

    def fit(self, documents: List[str]):
        doc_count = len(documents)
        df = Counter()
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                df[token] += 1

        self.vocab = {term: idx for idx, term in enumerate(df.keys())}
        self.idf = {term: math.log((1 + doc_count) / (1 + freq)) + 1.0 for term, freq in df.items()}

    def transform(self, text: str) -> List[float]:
        tokens = self._tokenize(text)
        if not tokens or not self.vocab:
            return [0.0] * max(1, len(self.vocab))

        tf = Counter(tokens)
        vector = [0.0] * len(self.vocab)
        for term, count in tf.items():
            if term in self.vocab:
                idx = self.vocab[term]
                vector[idx] = (count / len(tokens)) * self.idf.get(term, 1.0)

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector


class RAGEmbedder:
    def __init__(self, ollama_client: Optional[OllamaClient] = None, model_name: Optional[str] = None):
        self.client = ollama_client or OllamaClient()
        self.model_name = model_name
        self.local_embedder = LocalTfIdfEmbedder()
        self.using_ollama = False
        self._initialized = False

    def initialize(self, documents: List[str]):
        """Initializes embedder and determines Ollama vs local mode."""
        if self._initialized:
            return

        # Check if Ollama has embedding capability
        if self.model_name:
            test_vec = self.client.get_embeddings(self.model_name, "test context")
            if test_vec is not None:
                self.using_ollama = True
                log_event(
                    'RAG',
                    f"RAG initialized with Ollama embedding model: '{self.model_name}'",
                    level=logging.INFO
                )
                self._initialized = True
                return

        # Fallback to local
        self.local_embedder.fit(documents)
        self.using_ollama = False
        log_event(
            'RAG',
            "RAG initialized with local optimized embedder (Ollama embedding model not found).",
            level=logging.INFO
        )
        self._initialized = True

    def embed_text(self, text: str) -> List[float]:
        """Embeds single text string."""
        if self.using_ollama and self.model_name:
            vec = self.client.get_embeddings(self.model_name, text)
            if vec is not None:
                return vec

        return self.local_embedder.transform(text)

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """Embeds multiple texts."""
        if not self._initialized:
            self.initialize(documents)

        return [self.embed_text(doc) for doc in documents]
