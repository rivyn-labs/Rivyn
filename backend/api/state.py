from typing import Optional, Dict, Any
from backend.normalization.schema import LogBatch
from backend.ai.embeddings import LogEmbeddingIndex

class GlobalState:
    current_batch: Optional[LogBatch] = None
    embedding_index: Optional[LogEmbeddingIndex] = None
    binary_stats: Optional[Dict[str, Any]] = None

state = GlobalState()
