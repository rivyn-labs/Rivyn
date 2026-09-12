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
