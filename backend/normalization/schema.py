from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

class LogSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    WARNING = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

class NormalizedLog(BaseModel):
    id: int = Field(..., description="Unique line sequence identifier")
    source_id: str = Field("", description="Stable identifier for the originating log source")
    source_line: int = Field(0, description="One-based line number within the originating source")
    event_id: str = Field("", description="Stable, idempotency key for this source line/event")
    timestamp: Optional[str] = Field(None, description="ISO-formatted or parsed timestamp")
    timestamp_epoch: Optional[float] = Field(None, description="Epoch seconds for temporal windowing")
    level: str = Field("INFO", description="Standardized log level")
    service: Optional[str] = Field("unknown", description="Originating service or component")
    host: Optional[str] = Field(None, description="Hostname or node identifier")
    pid: Optional[str] = Field(None, description="Process ID or thread ID")
    message: str = Field(..., description="Cleaned message body")
    template: str = Field(..., description="Abstracted template pattern with <*> wildcards")
    template_id: str = Field(..., description="Unique template cluster hash/id")
    params: List[str] = Field(default_factory=list, description="Extracted dynamic variable parameters")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities like block_id, IPs, UUIDs")
    raw: str = Field(..., description="Original raw log line")
    anomaly_score: float = Field(0.0, description="Calculated anomaly score between 0.0 and 1.0")
    is_anomaly: bool = Field(False, description="Flag indicating whether this event is anomalous")

class EvidenceSnippet(BaseModel):
    log_id: int
    timestamp: Optional[str]
    level: str
    message: str
    reason: str

class IncidentReport(BaseModel):
    id: str
    title: str
    severity: str = "HIGH"
    confidence: float = 0.85
    summary: str
    probable_root_cause: str
    recommended_action: str
    affected_services: List[str] = Field(default_factory=list)
    affected_entities: List[str] = Field(default_factory=list)
    evidence_log_ids: List[int] = Field(default_factory=list)
    evidence_snippets: List[EvidenceSnippet] = Field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    event_count: int = 0

class ObservabilityMetrics(BaseModel):
    raw_logs_count: int = 0
    templates_count: int = 0
    anomalies_count: int = 0
    incidents_count: int = 0
    noise_reduction_ratio: float = 0.0
    mean_triage_time_manual_sec: float = 0.0
    mean_triage_time_ai_sec: float = 0.0
    triage_speedup_ratio: float = 0.0

class LogBatch(BaseModel):
    dataset_name: str
    detected_format: str
    total_lines: int
    logs: List[NormalizedLog] = Field(default_factory=list)
    templates: Dict[str, str] = Field(default_factory=dict)
    incidents: List[IncidentReport] = Field(default_factory=list)
    metrics: ObservabilityMetrics = Field(default_factory=ObservabilityMetrics)
