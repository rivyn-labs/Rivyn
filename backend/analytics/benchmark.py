import time
import os
from typing import Dict, Any, List
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.ai.llm_reasoner import GroundedReasoner
from backend.analytics.metrics import ObservabilityEvaluator

class BenchmarkRunner:
    """
    Executes automated benchmarks across heterogeneous LogHub datasets
    and measures decision quality, noise reduction, and triage velocity.
    """

    SAMPLE_FILES = {
        "hdfs": "data/samples/hdfs_sample.log",
        "bgl": "data/samples/bgl_sample.log",
        "linux": "data/samples/linux_sample.log",
        "openstack": "data/samples/openstack_sample.log"
    }

    @classmethod
    def run_all(cls, max_lines: int = 500) -> Dict[str, Any]:
        results = {}
        for name, path in cls.SAMPLE_FILES.items():
            if not os.path.exists(path):
                continue

            t0 = time.time()
            batch = LogLoader.load_from_file(path, max_lines=max_lines, dataset_name=name)
            load_time = time.time() - t0

            t1 = time.time()
            batch.logs = HybridAnomalyDetector().detect_anomalies(batch.logs)
            incidents = IncidentCorrelator().correlate(batch.logs)
            ai_time = time.time() - t1

            logs_map = {l.id: l for l in batch.logs}
            reasoner = GroundedReasoner()
            for inc in incidents:
                reasoner.explain_incident(inc, logs_map)

            total_elapsed = load_time + ai_time
            metrics = ObservabilityEvaluator.calculate_metrics(
                batch.logs,
                incidents,
                len(batch.templates),
                pipeline_elapsed_sec=total_elapsed
            )
            precision_20 = ObservabilityEvaluator.evaluate_precision_at_k(batch.logs, k=20)

            results[name] = {
                "dataset": name.upper(),
                "detected_dialect": batch.detected_format,
                "total_logs": len(batch.logs),
                "templates_discovered": len(batch.templates),
                "anomalies_flagged": metrics.anomalies_count,
                "incidents_formed": metrics.incidents_count,
                "noise_reduction_pct": metrics.noise_reduction_ratio,
                "precision_at_20": precision_20,
                "manual_triage_sec": metrics.mean_triage_time_manual_sec,
                "ai_triage_sec": metrics.mean_triage_time_ai_sec,
                "speedup_factor": f"{metrics.triage_speedup_ratio}x",
                "top_incident_title": incidents[0].title if incidents else "None",
                "top_incident_root_cause": incidents[0].probable_root_cause if incidents else "N/A"
            }

        return results
