"""Disk-first ingestion for datasets too large to hold in application memory.

The interactive pipeline intentionally keeps its richer global ML pass for
small uploads.  This module handles bulk files by retaining only bounded
dashboard and incident previews while persisting every normalized event as a
Parquet row group.  It is safe to run on files measured in gigabytes because
its working set is controlled by the configured chunk and preview limits.
"""

from __future__ import annotations

import os
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ingestion.detector import LogStructureDetector
from backend.normalization.schema import EvidenceSnippet, IncidentReport, LogBatch, NormalizedLog, ObservabilityMetrics
from backend.parsing.generic_parser import GenericLogParser
from backend.storage.binary_engine import BinaryLogEngine


ProgressCallback = Callable[[str, int, int], None]


@dataclass
class _IncidentSketch:
    template_id: str
    service: str
    key: str
    count: int = 0
    peak_score: float = 0.0
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    evidence: List[EvidenceSnippet] = field(default_factory=list)

    def add(self, log: NormalizedLog) -> None:
        self.count += 1
        self.peak_score = max(self.peak_score, log.anomaly_score)
        self.first_timestamp = self.first_timestamp or log.timestamp
        self.last_timestamp = log.timestamp or self.last_timestamp
        snippet = EvidenceSnippet(
            log_id=log.id,
            timestamp=log.timestamp,
            level=log.level,
            message=log.message[:180],
            reason=f"Streaming anomaly score {log.anomaly_score:.2f} - template {log.template_id}",
        )
        self.evidence.append(snippet)
        self.evidence.sort(key=lambda item: ("ERROR" in item.level or "FATAL" in item.level, item.log_id), reverse=True)
        del self.evidence[8:]


class StreamingLogProcessor:
    """Normalizes a file in chunks and saves it without a global log list."""

    CHUNK_LINES = 25_000
    MAX_DASHBOARD_LOGS = 20_000
    MAX_INCIDENT_KEYS = 10_000
    MAX_TEMPLATE_CATALOG = 100_000

    _SEVERITY_SCORES = {
        "CRITICAL": 0.95,
        "FATAL": 0.90,
        "ERROR": 0.80,
        "WARN": 0.55,
        "INFO": 0.05,
        "DEBUG": 0.0,
    }

    def __init__(self, chunk_lines: int = CHUNK_LINES) -> None:
        self.chunk_lines = max(1_000, chunk_lines)

    @staticmethod
    def _read_sample(filepath: str, limit: int = 100) -> List[str]:
        sample: List[str] = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as source:
            for line in source:
                line = line.strip()
                if line:
                    sample.append(line)
                if len(sample) >= limit:
                    break
        return sample

    @staticmethod
    def _concrete_key(log: NormalizedLog) -> str:
        for name in ("block_id", "req_id", "user", "bgl_node", "tenant_id", "pid"):
            value = log.entities.get(name)
            if isinstance(value, list) and value:
                return f"{name}:{value[0]}"
            if value is not None:
                return f"{name}:{value}"
        return f"service:{log.service or 'unknown'}"

    def _score_streaming_log(self, log: NormalizedLog) -> None:
        """Use a deterministic, stateless detector suitable for chunking.

        Isolation Forest and global rarity need the full corpus.  This path
        therefore makes only severity and failure-keyword claims while writing
        the full corpus for future offline/global re-analysis.
        """
        severity = self._SEVERITY_SCORES.get(log.level.upper(), 0.05)
        has_failure_signal = bool(HybridAnomalyDetector.KEYWORD_REGEX.search(log.message))
        score = min(1.0, severity + (0.25 if has_failure_signal else 0.0))
        log.anomaly_score = round(max(log.anomaly_score, score), 3)
        log.is_anomaly = log.anomaly_score >= 0.55 or (has_failure_signal and severity >= 0.50)

    @staticmethod
    def _chunks(source: Iterable[str], size: int) -> Iterable[List[str]]:
        chunk: List[str] = []
        for line in source:
            cleaned = line.rstrip("\r\n")
            if cleaned.strip():
                chunk.append(cleaned)
            if len(chunk) >= size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    @staticmethod
    def _make_incidents(sketches: Dict[Tuple[str, str], _IncidentSketch]) -> List[IncidentReport]:
        ordered = sorted(
            sketches.values(),
            key=lambda item: (item.peak_score, item.count),
            reverse=True,
        )[:200]
        reports: List[IncidentReport] = []
        for index, item in enumerate(ordered, start=101):
            severity = "CRITICAL" if item.peak_score >= 0.95 else "HIGH" if item.peak_score >= 0.80 else "MEDIUM"
            reports.append(IncidentReport(
                id=f"STREAM-{index}",
                title=f"{severity.title()} signal in {item.service}",
                severity=severity,
                confidence=round(min(0.98, max(0.65, item.peak_score)), 2),
                summary=f"{item.count:,} streamed anomalous events grouped by template and {item.key}.",
                probable_root_cause="Streaming candidate. Review the stored Parquet evidence before remediation.",
                recommended_action="Inspect the cited event samples and run targeted correlation on the relevant time range.",
                affected_services=[item.service] if item.service else [],
                affected_entities=[item.key],
                evidence_log_ids=[snippet.log_id for snippet in item.evidence],
                evidence_snippets=item.evidence,
                start_time=item.first_timestamp,
                end_time=item.last_timestamp,
                event_count=item.count,
            ))
        return reports

    def process_file(
        self,
        filepath: str,
        dataset_name: str,
        output_dir: str,
        progress: Optional[ProgressCallback] = None,
    ) -> Tuple[LogBatch, Dict[str, object]]:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Bulk log file not found: {filepath}")

        file_size = max(1, os.path.getsize(filepath))
        sample = self._read_sample(filepath)
        if not sample:
            raise ValueError("The bulk log file contains no readable lines.")

        dialect = LogStructureDetector.detect(sample)["dialect"]
        parser = GenericLogParser(syslog_year=2005 if dataset_name.lower().startswith("linux") else None)
        target_path = os.path.join(output_dir, f"{dataset_name}.parquet")
        writer = BinaryLogEngine.open_stream_writer(target_path)
        templates: Dict[str, str] = {}
        sketches: Dict[Tuple[str, str], _IncidentSketch] = {}
        dashboard_logs: List[NormalizedLog] = []
        rng = random.Random(42)
        total_lines = anomaly_count = raw_bytes = 0
        started = time.time()

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as source:
                for lines in self._chunks(source, self.chunk_lines):
                    parsed: List[NormalizedLog] = []
                    for raw in lines:
                        total_lines += 1
                        raw_bytes += len(raw.encode("utf-8", errors="ignore")) + 1
                        log = parser.parse_line(raw, line_id=total_lines, dialect=dialect)
                        self._score_streaming_log(log)
                        parsed.append(log)
                        if log.is_anomaly:
                            anomaly_count += 1
                            key = (log.template_id, self._concrete_key(log))
                            sketch = sketches.get(key)
                            if sketch is None and len(sketches) < self.MAX_INCIDENT_KEYS:
                                sketch = _IncidentSketch(log.template_id, log.service or "unknown", key[1])
                                sketches[key] = sketch
                            if sketch is not None:
                                sketch.add(log)

                        if len(dashboard_logs) < self.MAX_DASHBOARD_LOGS:
                            dashboard_logs.append(log)
                        else:
                            replacement = rng.randrange(total_lines)
                            if replacement < self.MAX_DASHBOARD_LOGS:
                                dashboard_logs[replacement] = log

                    BinaryLogEngine.write_stream_chunk(writer, parsed)
                    for log in parsed:
                        if len(templates) < self.MAX_TEMPLATE_CATALOG or log.template_id in templates:
                            templates[log.template_id] = log.template

                    if progress:
                        # Text iteration disables ``TextIOWrapper.tell`` on
                        # some Python versions; buffered byte position remains
                        # a safe, approximate progress signal.
                        consumed = source.buffer.tell()
                        percent = 5 + int(min(0.87, consumed / file_size) * 87)
                        progress("Streaming, normalizing, and writing Parquet", percent, total_lines)
        finally:
            writer.close()

        incidents = self._make_incidents(sketches)
        elapsed = max(0.01, time.time() - started)
        # Candidate grouping is intentionally not promoted as the exact global
        # noise-reduction metric; global ML correlation belongs in an offline
        # batch job over the persisted Parquet dataset.
        metrics = ObservabilityMetrics(
            raw_logs_count=total_lines,
            templates_count=len(templates),
            anomalies_count=anomaly_count,
            incidents_count=len(incidents),
            noise_reduction_ratio=0.0,
            mean_triage_time_manual_sec=0.0,
            mean_triage_time_ai_sec=elapsed,
            triage_speedup_ratio=0.0,
        )
        batch = LogBatch(
            dataset_name=dataset_name,
            detected_format=dialect,
            total_lines=total_lines,
            logs=sorted(dashboard_logs, key=lambda log: log.id),
            templates=templates,
            incidents=incidents,
            metrics=metrics,
        )
        binary_bytes = os.path.getsize(target_path)
        binary_stats: Dict[str, object] = {
            "file_path": target_path,
            "filename": os.path.basename(target_path),
            "row_count": total_lines,
            "raw_text_bytes": raw_bytes,
            "binary_bytes": binary_bytes,
            "compression_ratio_pct": round(max(0.0, (1 - binary_bytes / max(1, raw_bytes)) * 100), 2),
            "write_time_sec": round(elapsed, 3),
            "storage_reduction_factor": f"{round(raw_bytes / max(1, binary_bytes), 1)}x",
            "execution_mode": "streaming",
            "working_set": f"{self.chunk_lines:,} parsed lines per chunk",
            "dashboard_preview_rows": len(dashboard_logs),
            "incident_preview_count": len(incidents),
            "detection_mode": "streaming severity + failure-keyword signals",
            "global_correlation": "Run against persisted Parquet ranges; not materialized in RAM.",
        }
        binary_stats.update(BinaryLogEngine.scan_anomalies_vectorized(target_path))
        if progress:
            progress("Bulk dataset ready", 100, total_lines)
        return batch, binary_stats
