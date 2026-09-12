import pytest
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.analytics.metrics import ObservabilityEvaluator

def test_incident_correlation():
    batch = LogLoader.load_from_file("data/samples/linux_sample.log", max_lines=150)
    detector = HybridAnomalyDetector()
    batch.logs = detector.detect_anomalies(batch.logs)

    correlator = IncidentCorrelator()
    incidents = correlator.correlate(batch.logs)

    assert len(incidents) > 0
    first_inc = incidents[0]
    assert first_inc.event_count > 0
    assert len(first_inc.evidence_log_ids) > 0
    assert first_inc.confidence >= 0.5

def test_metrics_evaluation():
    batch = LogLoader.load_from_file("data/samples/hdfs_sample.log", max_lines=150)
    batch.logs = HybridAnomalyDetector().detect_anomalies(batch.logs)
    incidents = IncidentCorrelator().correlate(batch.logs)

    metrics = ObservabilityEvaluator.calculate_metrics(batch.logs, incidents, len(batch.templates))
    assert metrics.noise_reduction_ratio > 0.0
    assert metrics.triage_speedup_ratio > 1.0


def _synthetic_log(idx, template_id, epoch, service="datanode", entities=None, score=0.9):
    """Minimal anomalous log line for correlator unit tests."""
    from backend.normalization.schema import NormalizedLog
    return NormalizedLog(
        id=idx,
        raw=f"line {idx}",
        message=f"event {idx}",
        timestamp="2008-11-09T21:40:43",
        timestamp_epoch=epoch,
        level="ERROR",
        service=service,
        host="node-1",
        template=f"event <*>",
        template_id=template_id,
        entities=entities or {},
        anomaly_score=score,
        is_anomaly=True,
    )


def test_repeated_template_collapses_into_one_incident():
    """
    Regression: the original correlator compared each log only against the last
    member of the open cluster and never looked at the mined template, so a
    template repeating on a slow cadence produced one incident per occurrence
    and noise reduction collapsed.
    """
    # 120s cadence: wider than the old 60s adjacency window, narrower than the
    # session gap -- the exact regime the original implementation fragmented.
    logs = [_synthetic_log(i, "tpl-repeat", epoch=i * 120.0) for i in range(20)]
    incidents = IncidentCorrelator().correlate(logs)

    assert len(incidents) == 1, f"expected 1 consolidated incident, got {len(incidents)}"
    assert incidents[0].event_count == 20
    assert len(incidents[0].evidence_log_ids) == 20


def test_distinct_templates_stay_separate_when_unrelated():
    """Different templates, different services, no time overlap -> no merging."""
    logs = [
        _synthetic_log(1, "tpl-a", epoch=0.0, service="svc-a"),
        _synthetic_log(2, "tpl-b", epoch=100_000.0, service="svc-b"),
    ]
    incidents = IncidentCorrelator().correlate(logs)
    assert len(incidents) == 2


def test_shared_entity_merges_across_templates():
    """Different templates naming the same block at the same moment are one incident."""
    logs = [
        _synthetic_log(1, "tpl-a", epoch=0.0, entities={"block_id": "blk_42"}),
        _synthetic_log(2, "tpl-b", epoch=5.0, entities={"block_id": "blk_42"}),
    ]
    incidents = IncidentCorrelator().correlate(logs)
    assert len(incidents) == 1
    assert incidents[0].event_count == 2
