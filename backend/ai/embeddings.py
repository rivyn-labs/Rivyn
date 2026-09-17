import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.normalization.schema import NormalizedLog
from backend.ai.semantic_encoder import SemanticEncoder

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

    def __init__(self, chunk_size: int = 5, use_semantic: bool = True):
        self.chunk_size = chunk_size
        self.chunks: List[LogChunk] = []
        self.vectorizer = TfidfVectorizer(
            max_features=2048,
            ngram_range=(1, 2),
            token_pattern=r'(?u)\b\w+\b|[<*>]'
        )
        self.embeddings: Optional[np.ndarray] = None
        # Dense vectors when a sentence-transformer is installed, otherwise the
        # TF-IDF matrix above. Both answer search() identically.
        self.encoder = SemanticEncoder.shared() if use_semantic else None
        self.semantic_embeddings: Optional[np.ndarray] = None

    def build_index(self, logs: List[NormalizedLog]):
        if not logs:
            return

        self.chunks = []
        self._append_chunks(logs)

    def append_logs(self, logs: List[NormalizedLog]):
        """Add new evidence windows while retaining every existing chunk."""
        if not logs:
            return
        self._append_chunks(logs)

    def _append_chunks(self, logs: List[NormalizedLog]):
        existing = {chunk.chunk_id for chunk in self.chunks}
        total = len(logs)
        # Adapt sliding step for large log streams (cap baseline chunks to ~2000)
        step = max(1, self.chunk_size // 2) if total < 10000 else max(self.chunk_size, total // 2000)
        for i in range(0, total, step):
            window = logs[i:i + self.chunk_size]
            if not window:
                continue
            chunk = LogChunk(f"chunk_{window[0].id}_{window[-1].id}", window)
            if chunk.chunk_id not in existing:
                self.chunks.append(chunk)
                existing.add(chunk.chunk_id)

        # For large streams, ensure all anomalous windows are indexed for Copilot RAG
        if total >= 10000:
            covered_indices = {c.start_id for c in self.chunks}
            for i, l in enumerate(logs):
                if (l.is_anomaly or l.anomaly_score >= 0.55) and i not in covered_indices:
                    if len(self.chunks) >= 5000:
                        break
                    start_i = max(0, i - 2)
                    window = logs[start_i:start_i + self.chunk_size]
                    if window:
                        chunk = LogChunk(f"chunk_{window[0].id}_{window[-1].id}", window)
                        if chunk.chunk_id not in existing:
                            self.chunks.append(chunk)
                            existing.add(chunk.chunk_id)
                        covered_indices.add(start_i)

        texts = [c.text for c in self.chunks]
        if not texts:
            return

        # TF-IDF is always built: it is the fallback, and it stays useful for
        # exact identifiers (a block id, a request id) that dense vectors blur.
        self.embeddings = self.vectorizer.fit_transform(texts)

        if self.encoder is not None and self.encoder.is_available:
            self.semantic_embeddings = self.encoder.encode(texts)

    @property
    def backend(self) -> str:
        """Which retrieval backend answered, so results stay auditable."""
        return "semantic" if self.semantic_embeddings is not None else "tfidf"

    def search(self, query: str, top_k: int = 3) -> List[Tuple[LogChunk, float]]:
        if self.embeddings is None or not self.chunks:
            return []

        scores = None
        if self.semantic_embeddings is not None:
            query_emb = self.encoder.encode([query])
            if query_emb is not None:
                # Vectors are L2-normalised, so a dot product is cosine similarity.
                scores = self.semantic_embeddings @ query_emb[0]

        if scores is None:
            query_vec = self.vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self.embeddings)[0]

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0.01:
                results.append((self.chunks[idx], round(score, 3)))
        return results
