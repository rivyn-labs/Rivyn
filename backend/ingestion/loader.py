import os
from typing import List, Optional
from backend.ingestion.detector import LogStructureDetector
from backend.parsing.generic_parser import GenericLogParser
from backend.normalization.schema import NormalizedLog, LogBatch, ObservabilityMetrics

class LogLoader:
    """
    Ingests log data from files, file paths, or memory streams,
    detects dialect structure, and coordinates normalized parsing.
    """

    @classmethod
    def load_from_file(cls, filepath: str, max_lines: int = 5000, dataset_name: Optional[str] = None) -> LogBatch:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Log file not found at: {filepath}")

        if not dataset_name:
            dataset_name = os.path.splitext(os.path.basename(filepath))[0]

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            if max_lines is not None:
                lines = [f.readline() for _ in range(max_lines)]
                lines = [l for l in lines if l]
            else:
                lines = [l.rstrip("\r\n") for l in f]

        return cls.load_from_lines(lines, dataset_name=dataset_name)

    @classmethod
    def load_from_lines(cls, lines: List[str], dataset_name: str = "custom_upload") -> LogBatch:
        clean_lines = [l.strip() for l in lines if l.strip()]
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
        detection = LogStructureDetector.detect(clean_lines[:100])
        dialect = detection["dialect"]

        # 2. Parse all lines
        parser = GenericLogParser()
        normalized_logs: List[NormalizedLog] = []

        for idx, line in enumerate(clean_lines, start=1):
            parsed = parser.parse_line(line, line_id=idx, dialect=dialect)
            normalized_logs.append(parsed)

        # 3. Collect Templates Catalog
        templates_catalog = {
            cluster.template_id: cluster.get_template_str()
            for cluster in parser.drain.clusters.values()
        }

        return LogBatch(
            dataset_name=dataset_name,
            detected_format=dialect,
            total_lines=len(normalized_logs),
            logs=normalized_logs,
            templates=templates_catalog,
            incidents=[],
            metrics=ObservabilityMetrics(
                raw_logs_count=len(normalized_logs),
                templates_count=len(templates_catalog)
            )
        )
