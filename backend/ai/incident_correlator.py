from typing import List, Dict
from collections import defaultdict
from backend.normalization.schema import NormalizedLog, IncidentReport, EvidenceSnippet

class IncidentCorrelator:
    """
    Correlates individual anomalous log lines into unified Incidents
    based on temporal co-occurrence and shared entity topology.
    Dramatically reduces alert fatigue and noise.
    """

    def __init__(self, time_window_sec: float = 60.0):
        self.time_window_sec = time_window_sec

    def correlate(self, logs: List[NormalizedLog]) -> List[IncidentReport]:
        anomalous_logs = [l for l in logs if l.is_anomaly or l.anomaly_score >= 0.60]
        if not anomalous_logs:
            return []

        # Cluster by temporal proximity and entity affinity
        clusters: List[List[NormalizedLog]] = []
        current_cluster: List[NormalizedLog] = []

        for log in anomalous_logs:
            if not current_cluster:
                current_cluster.append(log)
                continue

            last_log = current_cluster[-1]
            time_diff = abs((log.timestamp_epoch or 0) - (last_log.timestamp_epoch or 0))

            # Check shared entities
            shared_entities = False
            for k in ["block_id", "req_id", "user", "bgl_node"]:
                if k in log.entities and k in last_log.entities:
                    if log.entities[k] == last_log.entities[k]:
                        shared_entities = True
                        break

            # If within temporal window or sharing same entity
            if time_diff <= self.time_window_sec or shared_entities:
                current_cluster.append(log)
            else:
                clusters.append(current_cluster)
                current_cluster = [log]

        if current_cluster:
            clusters.append(current_cluster)

        # Build IncidentReports from clusters
        incidents: List[IncidentReport] = []
        for idx, cluster in enumerate(clusters, start=101):
            sev_levels = [l.level for l in cluster]
            if "CRITICAL" in sev_levels or "FATAL" in sev_levels:
                severity = "CRITICAL"
            elif "ERROR" in sev_levels:
                severity = "HIGH"
            else:
                severity = "MEDIUM"

            services = sorted(list(set(l.service for l in cluster if l.service)))
            entities_set = set()
            for l in cluster:
                for k, v in l.entities.items():
                    if isinstance(v, list):
                        entities_set.update(str(x) for x in v)
                    else:
                        entities_set.add(f"{k}:{v}")
                if l.host and l.host != "local":
                    entities_set.add(f"host:{l.host}")

            # Top evidence snippets (up to 8)
            evidence_snippets = []
            for l in cluster[:8]:
                evidence_snippets.append(EvidenceSnippet(
                    log_id=l.id,
                    timestamp=l.timestamp,
                    level=l.level,
                    message=l.message[:180],
                    reason=f"Anomaly score {l.anomaly_score:.2f} - template {l.template_id}"
                ))

            start_t = cluster[0].timestamp
            end_t = cluster[-1].timestamp
            peak_score = max(l.anomaly_score for l in cluster)

            incidents.append(IncidentReport(
                id=f"INC-{idx}",
                title=f"Incident in {services[0] if services else 'System'} ({len(cluster)} correlated events)",
                severity=severity,
                confidence=round(min(0.98, max(0.65, peak_score)), 2),
                summary=f"Detected burst of {len(cluster)} anomalous events across {len(services)} services with peak anomaly score {peak_score:.2f}.",
                probable_root_cause="Under analysis by reasoning engine",
                recommended_action="Inspect linked log evidence",
                affected_services=services,
                affected_entities=sorted(list(entities_set)),
                evidence_log_ids=[l.id for l in cluster],
                evidence_snippets=evidence_snippets,
                start_time=start_t,
                end_time=end_t,
                event_count=len(cluster)
            ))

        return incidents
