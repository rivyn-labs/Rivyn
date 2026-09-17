from typing import Optional, Dict, Any
from backend.normalization.schema import LogBatch
from backend.ai.embeddings import LogEmbeddingIndex

class GlobalState:
    current_batch: Optional[LogBatch] = None
    embedding_index: Optional[LogEmbeddingIndex] = None
    binary_stats: Optional[Dict[str, Any]] = None
    ingestion_jobs: Dict[str, Dict[str, Any]] = {}
    bulk_runs: Dict[str, Dict[str, Any]] = {}
    observed_lines_per_second: Optional[float] = None

state = GlobalState()
