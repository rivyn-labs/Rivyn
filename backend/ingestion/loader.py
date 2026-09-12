import os
import hashlib
from typing import List, Optional
from backend.ingestion.detector import LogStructureDetector
from backend.parsing.generic_parser import GenericLogParser
from backend.normalization.schema import NormalizedLog, LogBatch, ObservabilityMetrics

class LogLoader:
    """
    Ingests log data from files, file paths, or memory streams,
    detects dialect structure, and coordinates normalized parsing.
    """

    # RFC 3164 syslog omits the year.  These values come from the LogHub
    # dataset provenance, not from the local file timestamp, so parsing is
    # deterministic across developer machines and CI.
    DATASET_SYSLOG_YEARS = {
        "linux": 2005,
        "linux_full": 2005,
    }

    @classmethod
    def load_from_file(cls, filepath: str, max_lines: int = 5000, dataset_name: Optional[str] = None) -> LogBatch:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Log file not found at: {filepath}")

        if not dataset_name:
            dataset_name = os.path.splitext(os.path.basename(filepath))[0]

        # Iterate the file and stop at whichever comes first, the cap or EOF.
        # The previous comprehension issued exactly max_lines readline() calls
        # regardless of EOF, so a generous cap meaning "read everything" spun
        # through millions of empty reads instead of returning.
        lines = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if max_lines is not None and len(lines) >= max_lines:
                    break
                lines.append(line.rstrip("\r\n"))

        return cls.load_from_lines(lines, dataset_name=dataset_name, source_id=os.path.abspath(filepath))

    @classmethod
    def load_from_lines(
        cls,
        lines: List[str],
        dataset_name: str = "custom_upload",
        *,
        source_id: Optional[str] = None,
        source_line_offset: int = 0,
        parser: Optional[GenericLogParser] = None,
        dialect: Optional[str] = None,
        start_id: int = 1,
    ) -> LogBatch:
        """Parse a slice without creating identities that conflict with prior slices.

        The optional parser is deliberately injectable: an incremental caller keeps
        one Drain tree per dataset, while existing one-shot callers retain their
        original behaviour.
        """
        source_id = source_id or dataset_name
        clean_lines = [(source_line_offset + idx, line.strip()) for idx, line in enumerate(lines, start=1) if line.strip()]
        if not clean_lines:
            return LogBatch(
                dataset_name=dataset_name,
                detected_format="empty",
                total_lines=0,
                logs=[],
                templates={},
                incidents=[],
                metrics=ObservabilityMetrics()
            )

        # 1. Structure Detection
        detected_dialect = dialect or LogStructureDetector.detect([line for _, line in clean_lines[:100]])["dialect"]

        # 2. Parse all lines
        syslog_year = cls.DATASET_SYSLOG_YEARS.get(dataset_name.lower())
        parser = parser or GenericLogParser(syslog_year=syslog_year)
        normalized_logs: List[NormalizedLog] = []

        for idx, (source_line, line) in enumerate(clean_lines, start=start_id):
            parsed = parser.parse_line(line, line_id=idx, dialect=detected_dialect)
            parsed.source_id = source_id
            parsed.source_line = source_line
            parsed.event_id = hashlib.sha256(f"{source_id}\0{source_line}\0{line}".encode("utf-8")).hexdigest()
            normalized_logs.append(parsed)

        # 3. Collect Templates Catalog
        templates_catalog = {
            cluster.template_id: cluster.get_template_str()
            for cluster in parser.drain.clusters.values()
        }

        return LogBatch(
            dataset_name=dataset_name,
            detected_format=detected_dialect,
            total_lines=len(normalized_logs),
            logs=normalized_logs,
            templates=templates_catalog,
            incidents=[],
            metrics=ObservabilityMetrics(
                raw_logs_count=len(normalized_logs),
                templates_count=len(templates_catalog)
            )
        )
