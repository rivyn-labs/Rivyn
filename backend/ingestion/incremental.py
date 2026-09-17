"""Transactional, append-only ingestion orchestration."""
import copy
import hashlib
import time
from typing import Iterable, List, Optional

from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.embeddings import LogEmbeddingIndex
from backend.ai.incident_correlator import IncidentCorrelator
from backend.ai.llm_reasoner import GroundedReasoner
from backend.analytics.metrics import ObservabilityEvaluator
from backend.api.state import DatasetState, state
from backend.ingestion.loader import LogLoader
from backend.ingestion.detector import LogStructureDetector
from backend.parsing.generic_parser import GenericLogParser
from backend.normalization.schema import IncidentReport, LogBatch, NormalizedLog
from backend.storage.binary_engine import BinaryLogEngine


def _event_key(source_id: str, source_line: int, raw: str) -> str:
    return hashlib.sha256(f"{source_id}\0{source_line}\0{raw.strip()}".encode("utf-8")).hexdigest()


class IncrementalIngestor:
    """Stages new data off-state and publishes it only after every stage succeeds."""

    @staticmethod
    def ingest(
        lines: Iterable[str],
        dataset_name: str,
        *,
        source_id: Optional[str] = None,
        source_line_offset: int = 0,
        output_dir: str = "data/binary",
    ) -> LogBatch:
        source_id = source_id or dataset_name
        started_at = time.time()
        incoming = list(lines)
        current = state.datasets.get(dataset_name)
        known_events = current.event_ids if current else set()

        # Decide idempotency before parsing.  Source line numbers remain stable
        # for repeated uploads and callers can provide an offset for later slices.
        unseen: List[str] = []
        for relative_line, raw in enumerate(incoming, start=1):
            if not raw.strip():
                continue
            if _event_key(source_id, source_line_offset + relative_line, raw) not in known_events:
                unseen.append(raw)

        if not unseen:
            if current:
                state.current_batch = current.batch
                state.embedding_index = current.embedding_index
                state.binary_stats = current.binary_stats
                return current.batch
            return LogBatch(dataset_name=dataset_name, detected_format="empty", total_lines=0)

        # Preserve source positions when blank lines occur in a slice.
        unseen_positions = [
            (source_line_offset + n, raw)
            for n, raw in enumerate(incoming, start=1)
            if raw.strip() and _event_key(source_id, source_line_offset + n, raw) not in known_events
        ]
        # Loader accepts a contiguous offset. Parse a full contiguous slice in
        # one pass; only uploads with idempotent holes need record-by-record
        # parsing to keep exact original line numbers.
        parser = copy.deepcopy(current.parser) if current else GenericLogParser()
        dialect = current.batch.detected_format if current else LogStructureDetector.detect(unseen[:100])["dialect"]
        next_id = current.next_log_id if current else 1
        new_logs: List[NormalizedLog] = []
        positions = [position for position, _ in unseen_positions]
        contiguous = positions == list(range(positions[0], positions[0] + len(positions)))
        if contiguous:
            parsed = LogLoader.load_from_lines(
                [raw for _, raw in unseen_positions], dataset_name=dataset_name, source_id=source_id,
                source_line_offset=positions[0] - 1, parser=parser, dialect=dialect, start_id=next_id,
            )
            new_logs.extend(parsed.logs)
            next_id += len(parsed.logs)
        else:
            # A duplicate may be interspersed with new source lines. Preserve
            # their original coordinates rather than compacting the slice.
            for source_line, raw in unseen_positions:
                parsed = LogLoader.load_from_lines(
                    [raw], dataset_name=dataset_name, source_id=source_id,
                    source_line_offset=source_line - 1, parser=parser, dialect=dialect,
                    start_id=next_id,
                )
                new_logs.extend(parsed.logs)
                next_id += len(parsed.logs)

        # Analyze only the new records. Existing anomaly values are immutable.
        new_logs = HybridAnomalyDetector().detect_anomalies(new_logs)
        existing_logs = list(current.batch.logs) if current else []
        existing_incidents = list(current.batch.incidents) if current else []
        incidents = IncrementalIngestor._merge_incidents(existing_incidents, new_logs, existing_logs)
        combined_logs = existing_logs + new_logs
        IncrementalIngestor._enrich_new_incidents(incidents, new_logs, combined_logs)

        templates = dict(current.batch.templates) if current else {}
        for template_id, template in (
            (cluster.template_id, cluster.get_template_str()) for cluster in parser.drain.clusters.values()
        ):
            templates.setdefault(template_id, template)

        # Preserve old RAG chunks and append only windows covering new events.
        index = copy.deepcopy(current.embedding_index) if current and current.embedding_index else LogEmbeddingIndex(chunk_size=5)
        if current and current.embedding_index:
            index.append_logs(new_logs)
        else:
            index.build_index(new_logs)

        batch = LogBatch(
            dataset_name=dataset_name,
            detected_format=dialect,
            total_lines=len(combined_logs), logs=combined_logs, templates=templates,
            incidents=incidents,
            metrics=ObservabilityEvaluator.calculate_metrics(
                combined_logs, incidents, len(templates), pipeline_elapsed_sec=time.time() - started_at
            ),
        )

        # This is the commit barrier: binary storage is atomically published
        # before state references are changed, so a failure leaves state intact.
        binary_stats = BinaryLogEngine.save_batch(
            batch.model_copy(update={"logs": new_logs}), output_dir=output_dir, append=True
        )

        dataset_state = DatasetState(
            batch=batch, parser=parser, embedding_index=index, binary_stats=binary_stats,
            event_ids=known_events | {log.event_id for log in new_logs}, next_log_id=next_id,
        )
        state.datasets[dataset_name] = dataset_state
        state.current_batch = batch
        state.embedding_index = index
        state.binary_stats = binary_stats
        return batch

    @staticmethod
    def _enrich_new_incidents(
        incidents: List[IncidentReport], new_logs: List[NormalizedLog], all_logs: List[NormalizedLog]
    ) -> None:
        """Use the configured LLM for a bounded set of incidents changed by this ingest.

        GroundedReasoner calls OpenAI when ``OPENAI_API_KEY`` is configured and
        retains its deterministic, evidence-linked fallback when it is not.  A
        cap keeps a large upload responsive and prevents unbounded API spend.
        """
        if not incidents or not new_logs:
            return

        changed_log_ids = {log.id for log in new_logs}
        candidates = [
            incident for incident in incidents
            if changed_log_ids.intersection(incident.evidence_log_ids)
        ]
        if not candidates:
            return

        from backend.config import settings

        reasoner = GroundedReasoner()
        logs_map = {log.id: log for log in all_logs}
        limit = max(0, settings.llm_max_incidents_per_ingestion)
        for incident in candidates[:limit]:
            reasoner.explain_incident(incident, logs_map)

    @staticmethod
    def _merge_incidents(
        existing: List[IncidentReport], new_logs: List[NormalizedLog], existing_logs: List[NormalizedLog]
    ) -> List[IncidentReport]:
        """Attach new anomaly clusters to compatible existing incidents, never recreate them."""
        reports = [report.model_copy(deep=True) for report in existing]
        log_by_id = {log.id: log for log in existing_logs + new_logs}
        next_number = max((int(report.id.split("-")[-1]) for report in reports if report.id.rsplit("-", 1)[-1].isdigit()), default=100) + 1
        correlator = IncidentCorrelator()
        for candidate in correlator.correlate(new_logs):
            candidate_logs = [log_by_id[lid] for lid in candidate.evidence_log_ids if lid in log_by_id]
            candidate_templates = {log.template_id for log in candidate_logs}
            candidate_entities = set().union(*(correlator._entity_keys(log) for log in candidate_logs)) if candidate_logs else set()
            match = None
            for report in reports:
                old_logs = [log_by_id[lid] for lid in report.evidence_log_ids if lid in log_by_id]
                old_templates = {log.template_id for log in old_logs}
                old_entities = set().union(*(correlator._entity_keys(log) for log in old_logs)) if old_logs else set()
                candidate_span = correlator._span(candidate_logs)
                old_span = correlator._span(old_logs)
                same_session = (
                    candidate_span[0] <= old_span[1] + correlator.session_gap_sec
                    and old_span[0] <= candidate_span[1] + correlator.session_gap_sec
                )
                same_template = bool(candidate_templates & old_templates) and same_session
                related_topology = bool(candidate_entities & old_entities) and correlator._overlaps(candidate_logs, old_logs)
                if same_template or related_topology:
                    match = report
                    break
            if match is None:
                candidate.id = f"INC-{next_number}"
                next_number += 1
                reports.append(candidate)
                continue
            added_ids = [lid for lid in candidate.evidence_log_ids if lid not in match.evidence_log_ids]
            match.evidence_log_ids.extend(added_ids)
            match.evidence_snippets.extend(s for s in candidate.evidence_snippets if s.log_id in added_ids)
            match.evidence_snippets = match.evidence_snippets[:8]
            match.event_count = len(match.evidence_log_ids)
            match.affected_services = sorted(set(match.affected_services) | set(candidate.affected_services))
            match.affected_entities = sorted(set(match.affected_entities) | set(candidate.affected_entities))
            match.end_time = candidate.end_time or match.end_time
        return reports
