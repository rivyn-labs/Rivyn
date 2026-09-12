import numpy as np
from typing import List, Dict, Any, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.normalization.schema import NormalizedLog

class LogChunk:
    def __init__(self, chunk_id: str, logs: List[NormalizedLog]):
        self.chunk_id = chunk_id
        self.logs = logs
        self.text = " | ".join(f"[{l.level}] {l.service}: {l.message}" for l in logs)
        self.start_id = logs[0].id if logs else 0
        self.end_id = logs[-1].id if logs else 0
        self.has_anomaly = any(l.is_anomaly for l in logs)

class LogEmbeddingIndex:
    """
    Evidence-First Vector Retrieval Engine:
    Chunks log streams into contextual passages, computes vectorized embeddings,
    and indexes them for semantic similarity search and RAG grounding.
    """

    def __init__(self, chunk_size: int = 5):
        self.chunk_size = chunk_size
        self.chunks: List[LogChunk] = []
        self.vectorizer = TfidfVectorizer(
            max_features=2048,
            ngram_range=(1, 2),
            token_pattern=r'(?u)\b\w+\b|[<*>]'
        )
        self.embeddings: Optional[np.ndarray] = None

    def build_index(self, logs: List[NormalizedLog]):
        if not logs:
            return

        self.chunks = []
        # Create overlapping sliding window chunks
        step = max(1, self.chunk_size // 2)
        for i in range(0, len(logs), step):
            window = logs[i:i + self.chunk_size]
            if not window:
                continue
            chunk = LogChunk(f"chunk_{i}", window)
            self.chunks.append(chunk)

        texts = [c.text for c in self.chunks]
        if texts:
            self.embeddings = self.vectorizer.fit_transform(texts)

    def search(self, query: str, top_k: int = 3) -> List[Tuple[LogChunk, float]]:
        if self.embeddings is None or not self.chunks:
            return []

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.embeddings)[0]

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0.01:
                results.append((self.chunks[idx], round(score, 3)))
        return results
