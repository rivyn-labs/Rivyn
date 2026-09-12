from typing import Optional
from backend.normalization.schema import LogBatch
from backend.ai.embeddings import LogEmbeddingIndex

class GlobalState:
    current_batch: Optional[LogBatch] = None
    embedding_index: Optional[LogEmbeddingIndex] = None

state = GlobalState()
