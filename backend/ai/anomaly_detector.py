import re
import numpy as np
from collections import Counter
from typing import List, Dict, Tuple
from sklearn.ensemble import IsolationForest
from backend.normalization.schema import NormalizedLog

class HybridAnomalyDetector:
    """
    Multi-Tiered AI Anomaly Detection Architecture:
    1. Simple Baseline: Template frequency rarity scoring (rare template_id = suspicious).
    2. Tabular ML: Scikit-learn IsolationForest over tabular + numeric features
       (template_freq, severity_num, time_delta, params_count, burst_zscore).
    3. Semantic Rules: Failure/Exception keyword triggers.
    """

    KEYWORD_REGEX = re.compile(
        r'(?i)\b(exception|failed|failure|error|fatal|panic|denied|timeout|timed\s+out|dropped|killed|unreachable|corrupt)\b'
    )

    SEVERITY_NUM_MAP = {
        "DEBUG": 0.0,
        "INFO": 1.0,
        "WARN": 2.0,
        "ERROR": 3.0,
        "FATAL": 4.0,
        "CRITICAL": 4.5
    }

    def __init__(self, threshold: float = 0.55):
        self.threshold = threshold

    def detect_anomalies(self, logs: List[NormalizedLog]) -> List[NormalizedLog]:
        if not logs:
            return []

        total_logs = len(logs)

        # -------------------------------------------------------------
        # Tier 1: Frequency-Based Template Rarity Baseline
        # -------------------------------------------------------------
        template_counts = Counter(log.template_id for log in logs)
        rarity_scores: Dict[str, float] = {}
        for tmpl_id, count in template_counts.items():
            prob = count / total_logs
            # Rare templates that make up <2% get high rarity scores
            rarity = max(0.0, 1.0 - (prob * 10.0))
            rarity_scores[tmpl_id] = rarity

        # -------------------------------------------------------------
        # Tier 2: Temporal Window Burst Rate (z-score on 30s buckets)
        # -------------------------------------------------------------
        epochs = [log.timestamp_epoch for log in logs if log.timestamp_epoch is not None]
        time_burst_weights = [0.0] * total_logs
        time_deltas = [0.0] * total_logs

        if len(epochs) == total_logs and max(epochs) > min(epochs):
            min_e, max_e = min(epochs), max(epochs)
            span = max(1.0, max_e - min_e)
            num_buckets = max(10, min(100, int(span / 30)))
            bucket_size = span / num_buckets

            bucket_counts = np.zeros(num_buckets)
            bucket_indices = []
            for i, ep in enumerate(epochs):
                b_idx = min(num_buckets - 1, int((ep - min_e) / bucket_size))
                bucket_counts[b_idx] += 1
                bucket_indices.append(b_idx)
                if i > 0:
                    time_deltas[i] = max(0.0, ep - epochs[i - 1])

            mean_rate = np.mean(bucket_counts)
            std_rate = np.std(bucket_counts) + 1e-5

            for i, b_idx in enumerate(bucket_indices):
                z = (bucket_counts[b_idx] - mean_rate) / std_rate
                if z > 1.0:
                    time_burst_weights[i] = min(0.35, float(z * 0.10))

        # -------------------------------------------------------------
        # Tier 3: Tabular ML Isolation Forest over Structured Features
        # -------------------------------------------------------------
        feature_matrix = []
        for i, log in enumerate(logs):
            sev_num = self.SEVERITY_NUM_MAP.get(log.level.upper(), 1.0)
            t_freq = template_counts[log.template_id] / total_logs
            t_delta = time_deltas[i] if i < len(time_deltas) else 0.0
            p_count = float(len(log.params))
            has_kw = 1.0 if self.KEYWORD_REGEX.search(log.message) else 0.0
            burst_val = time_burst_weights[i] if i < len(time_burst_weights) else 0.0

            feature_matrix.append([sev_num, t_freq, t_delta, p_count, has_kw, burst_val])

        # Run Isolation Forest if dataset has sufficient sample size
        iforest_scores = [0.0] * total_logs
        if total_logs >= 20:
            try:
                X = np.array(feature_matrix)
                # Contamination set to dynamic expected anomaly proportion
                clf = IsolationForest(n_estimators=50, contamination=0.08, random_state=42)
                clf.fit(X)
                # Decision function: lower/negative = more anomalous
                decisions = clf.decision_function(X)
                # Normalize decision function to [0.0, 1.0] probability
                min_d, max_d = np.min(decisions), np.max(decisions)
                if max_d > min_d:
                    iforest_scores = 1.0 - ((decisions - min_d) / (max_d - min_d))
                else:
                    iforest_scores = [0.1] * total_logs
            except Exception:
                iforest_scores = [0.0] * total_logs

        # -------------------------------------------------------------
        # Composite Multi-Tier Decision Fusion
        # -------------------------------------------------------------
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
            has_kw = bool(self.KEYWORD_REGEX.search(log.message))
            kw_boost = 0.25 if has_kw else 0.0

            rarity_val = rarity_scores.get(log.template_id, 0.0) * 0.20
            burst_val = time_burst_weights[i] if i < len(time_burst_weights) else 0.0
            ml_iforest = float(iforest_scores[i]) * 0.25

            # Multi-tier ensemble fusion
            composite = sev_base + kw_boost + rarity_val + burst_val + ml_iforest
            composite = round(float(min(1.0, max(0.0, composite))), 3)

            is_anomaly = composite >= self.threshold or (has_kw and sev_base >= 0.50) or sev_base >= 0.80

            log.anomaly_score = composite
            log.is_anomaly = is_anomaly
            analyzed_logs.append(log)

        return analyzed_logs
