from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Set
from backend.normalization.schema import LogBatch
from backend.ai.embeddings import LogEmbeddingIndex
from backend.parsing.generic_parser import GenericLogParser


@dataclass
class DatasetState:
    """State retained for a de-duplicated interactive dataset."""
    batch: LogBatch
    parser: GenericLogParser = field(default_factory=GenericLogParser)
    embedding_index: Optional[LogEmbeddingIndex] = None
    binary_stats: Optional[Dict[str, Any]] = None
    event_ids: Set[str] = field(default_factory=set)
    next_log_id: int = 1

class GlobalState:
    def __init__(self):
        self.current_batch: Optional[LogBatch] = None
        self.embedding_index: Optional[LogEmbeddingIndex] = None
        self.binary_stats: Optional[Dict[str, Any]] = None
        self.datasets: Dict[str, DatasetState] = {}
        self.ingestion_jobs: Dict[str, Dict[str, Any]] = {}
        self.bulk_runs: Dict[str, Dict[str, Any]] = {}
        self.observed_lines_per_second: Optional[float] = None

state = GlobalState()
