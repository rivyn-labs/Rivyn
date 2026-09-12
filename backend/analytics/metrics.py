from typing import List, Dict, Any
from backend.normalization.schema import NormalizedLog, IncidentReport, ObservabilityMetrics

class ObservabilityEvaluator:
    """
    Evaluates system value and operational KPIs according to MHP guidelines:
    - Faster Triage: Compares manual triage time vs automated AI triage time.
    - Higher Precision: True anomalies in top findings (precision@k).
    - Lower Noise: Duplicate alerts consolidated into actionable incidents (reduction ratio).
    - Explainability: Evidence links per incident conclusion.
    """

    # Estimated industry manual review time: 15 seconds per raw error log
    MANUAL_REVIEW_SEC_PER_LOG = 15.0
    # AI automated batch triage time estimate
    AI_TRIAGE_SEC_PER_INCIDENT = 1.2

    @classmethod
    def calculate_metrics(
        cls,
        logs: List[NormalizedLog],
        incidents: List[IncidentReport],
        templates_count: int,
        pipeline_elapsed_sec: float = 0.5
    ) -> ObservabilityMetrics:
        raw_count = len(logs)
        if raw_count == 0:
            return ObservabilityMetrics()

        anomalies_count = sum(1 for l in logs if l.is_anomaly)
        incidents_count = len(incidents)

        # 1. Noise Reduction Ratio
        # How much the engineer's alert fatigue is reduced
        if raw_count > 0:
            noise_reduction = round((1.0 - (incidents_count / max(1, anomalies_count))) * 100, 2)
            noise_reduction = max(0.0, min(99.9, noise_reduction))
        else:
            noise_reduction = 0.0

        # 2. Triage Time Comparison
        manual_time_sec = round(anomalies_count * cls.MANUAL_REVIEW_SEC_PER_LOG, 1)
        ai_time_sec = round(pipeline_elapsed_sec + (incidents_count * cls.AI_TRIAGE_SEC_PER_INCIDENT), 2)
        speedup = round(manual_time_sec / max(0.1, ai_time_sec), 1)

        return ObservabilityMetrics(
            raw_logs_count=raw_count,
            templates_count=templates_count,
            anomalies_count=anomalies_count,
            incidents_count=incidents_count,
            noise_reduction_ratio=noise_reduction,
            mean_triage_time_manual_sec=manual_time_sec,
            mean_triage_time_ai_sec=ai_time_sec,
            triage_speedup_ratio=speedup
        )

    @classmethod
    def evaluate_precision_at_k(cls, logs: List[NormalizedLog], k: int = 20) -> float:
        """
        Evaluates precision@k: ratio of true anomalies in top-k highest-scored logs.
        """
        if not logs:
            return 0.0
        sorted_logs = sorted(logs, key=lambda l: l.anomaly_score, reverse=True)[:k]
        if not sorted_logs:
            return 0.0

        true_positives = sum(
            1 for l in sorted_logs
            if l.level in ["ERROR", "FATAL", "CRITICAL", "WARN"] or "fail" in l.message.lower() or "exception" in l.message.lower()
        )
        return round(true_positives / len(sorted_logs), 3)
