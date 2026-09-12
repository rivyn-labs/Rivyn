import re
import numpy as np
from collections import Counter
from typing import List, Dict
from backend.normalization.schema import NormalizedLog

class HybridAnomalyDetector:
    """
    Multi-faceted AI anomaly detection combining:
    1. Semantic error / exception keyword signals
    2. Severity weight multipliers (WARN, ERROR, FATAL, CRITICAL)
    3. Template frequency rarity (rare events in the distribution)
    4. Temporal burst rate anomaly (z-score on sliding time windows)
    """

    KEYWORD_REGEX = re.compile(
        r'(?i)\b(exception|failed|failure|error|fatal|panic|denied|timeout|timed\s+out|dropped|killed|unreachable|corrupt)\b'
    )

    def __init__(self, threshold: float = 0.55):
        self.threshold = threshold

    def detect_anomalies(self, logs: List[NormalizedLog]) -> List[NormalizedLog]:
        if not logs:
            return []

        total_logs = len(logs)

        # 1. Template Frequency Analysis
        template_counts = Counter(log.template_id for log in logs)
        rarity_scores: Dict[str, float] = {}
        for tmpl_id, count in template_counts.items():
            prob = count / total_logs
            rarity = max(0.0, 1.0 - (prob * 10.0))
            rarity_scores[tmpl_id] = rarity

        # 2. Temporal Window Rate Analysis (z-score on time buckets)
        epochs = [log.timestamp_epoch for log in logs if log.timestamp_epoch is not None]
        time_burst_weights = [0.0] * total_logs
        if len(epochs) == total_logs and max(epochs) > min(epochs):
            min_e, max_e = min(epochs), max(epochs)
            span = max(1.0, max_e - min_e)
            num_buckets = max(10, min(100, int(span / 30)))  # 30-sec buckets
            bucket_size = span / num_buckets

            bucket_counts = np.zeros(num_buckets)
            bucket_indices = []
            for ep in epochs:
                b_idx = min(num_buckets - 1, int((ep - min_e) / bucket_size))
                bucket_counts[b_idx] += 1
                bucket_indices.append(b_idx)

            mean_rate = np.mean(bucket_counts)
            std_rate = np.std(bucket_counts) + 1e-5

            for i, b_idx in enumerate(bucket_indices):
                z = (bucket_counts[b_idx] - mean_rate) / std_rate
                if z > 1.0:
                    time_burst_weights[i] = min(0.30, float(z * 0.10))

        # 3. Severity & Keyword Multipliers
        severity_multipliers = {
            "CRITICAL": 0.95,
            "FATAL": 0.90,
            "ERROR": 0.80,
            "WARN": 0.55,
            "INFO": 0.05,
            "DEBUG": 0.0
        }

        analyzed_logs: List[NormalizedLog] = []
        for i, log in enumerate(logs):
            sev_base = severity_multipliers.get(log.level.upper(), 0.05)
            
            # Semantic keyword scan
            has_kw = bool(self.KEYWORD_REGEX.search(log.message))
            kw_boost = 0.25 if has_kw else 0.0

            rarity_val = rarity_scores.get(log.template_id, 0.0) * 0.20
            burst_val = time_burst_weights[i] if i < len(time_burst_weights) else 0.0

            # Combined score: add severity and keyword signals
            composite = sev_base + kw_boost + rarity_val + burst_val
            composite = round(float(min(1.0, max(0.0, composite))), 3)

            is_anomaly = composite >= self.threshold or (has_kw and sev_base >= 0.50) or sev_base >= 0.80

            log.anomaly_score = composite
            log.is_anomaly = is_anomaly
            analyzed_logs.append(log)

        return analyzed_logs
