from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict
from backend.normalization.schema import NormalizedLog, IncidentReport, EvidenceSnippet

# Entity keys that identify a concrete actor in the system. Two anomalies that
# name the same one are far more likely to belong to the same incident than two
# that merely happen to occur at the same moment.
CORRELATION_ENTITY_KEYS = ("block_id", "req_id", "user", "bgl_node", "tenant_id", "pid")


class IncidentCorrelator:
    """
    Correlates individual anomalous log lines into unified Incidents.

    Grouping runs in two deterministic passes:

    1. Signature grouping -- anomalies sharing a mined Drain template are the
       same *kind* of event, so they collapse into one incident. A run is split
       whenever the quiet gap between consecutive occurrences exceeds
       ``session_gap_sec``, which keeps a recurrence next week from being folded
       into today's outage.

    2. Topology merge -- groups from *different* templates are merged when they
       overlap in time AND name a shared entity (block, request, user, node).
       This is what turns "connection refused" plus "replica missing" on the
       same block into a single incident instead of two.

    The previous implementation compared each log only against the last member
    of the open cluster, which made grouping order-dependent and never used the
    template at all -- so recurring identical events stayed separate and noise
    reduction collapsed on datasets whose anomalies are time-scattered.
    """

    def __init__(
        self,
        time_window_sec: float = 60.0,
        session_gap_sec: Optional[float] = None,
    ):
        # Retained for API compatibility: callers construct with no arguments,
        # and time_window_sec still controls how much slack two groups get when
        # deciding whether they overlap in time.
        self.time_window_sec = time_window_sec
        self.session_gap_sec = session_gap_sec if session_gap_sec is not None else time_window_sec * 5

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _entity_keys(log: NormalizedLog) -> Set[str]:
        """
        Signals that tie a log line to a shared actor.

        Concrete entities (block, request, user, node) are the strongest link.
        Service and host are weaker but essential: on datasets such as BGL the
        template miner produces a near-unique template per line, so the service
        is the only thing connecting a burst of kernel faults that a responder
        would triage as one event.
        """
        keys: Set[str] = set()
        for k in CORRELATION_ENTITY_KEYS:
            v = log.entities.get(k)
            if v is None:
                continue
            if isinstance(v, list):
                keys.update(f"{k}:{item}" for item in v)
            else:
                keys.add(f"{k}:{v}")

        if log.service:
            keys.add(f"svc:{log.service}")
        if log.host and log.host != "local":
            keys.add(f"host:{log.host}")
        return keys

    @staticmethod
    def _span(group: List[NormalizedLog]) -> Tuple[float, float]:
        stamps = [l.timestamp_epoch for l in group if l.timestamp_epoch is not None]
        if not stamps:
            return (0.0, 0.0)
        return (min(stamps), max(stamps))

    def _overlaps(self, a: List[NormalizedLog], b: List[NormalizedLog]) -> bool:
        a_start, a_end = self._span(a)
        b_start, b_end = self._span(b)
        slack = self.time_window_sec
        return a_start <= b_end + slack and b_start <= a_end + slack

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def correlate(self, logs: List[NormalizedLog]) -> List[IncidentReport]:
        anomalous_logs = [l for l in logs if l.is_anomaly or l.anomaly_score >= 0.60]
        if not anomalous_logs:
            return []

        anomalous_logs.sort(key=lambda l: (l.timestamp_epoch or 0.0, l.id))

        groups = self._group_by_signature(anomalous_logs)
        groups = self._merge_by_topology(groups)

        # Most severe and most confident first, so the board leads with what matters.
        groups.sort(
            key=lambda g: (
                max(l.anomaly_score for l in g),
                len(g),
            ),
            reverse=True,
        )

        return [
            self._build_report(idx, cluster)
            for idx, cluster in enumerate(groups, start=101)
        ]

    # ------------------------------------------------------------------ #
    # Pass 1 -- collapse repeats of the same mined template
    # ------------------------------------------------------------------ #
    def _group_by_signature(self, anomalous_logs: List[NormalizedLog]) -> List[List[NormalizedLog]]:
        by_template: Dict[str, List[NormalizedLog]] = defaultdict(list)
        for log in anomalous_logs:
            by_template[log.template_id].append(log)

        groups: List[List[NormalizedLog]] = []
        for entries in by_template.values():
            run = [entries[0]]
            for prev, cur in zip(entries, entries[1:]):
                gap = (cur.timestamp_epoch or 0.0) - (prev.timestamp_epoch or 0.0)
                if gap > self.session_gap_sec:
                    groups.append(run)
                    run = [cur]
                else:
                    run.append(cur)
            groups.append(run)
        return groups

    # ------------------------------------------------------------------ #
    # Pass 2 -- join groups that share an entity and a moment in time
    # ------------------------------------------------------------------ #
    def _merge_by_topology(self, groups: List[List[NormalizedLog]]) -> List[List[NormalizedLog]]:
        n = len(groups)
        if n <= 1:
            return groups

        parent = list(range(n))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)

        # Index entity -> groups naming it, so we only compare plausible pairs
        # instead of every group against every other.
        entity_index: Dict[str, List[int]] = defaultdict(list)
        for gi, group in enumerate(groups):
            seen: Set[str] = set()
            for log in group:
                seen.update(self._entity_keys(log))
            for key in seen:
                entity_index[key].append(gi)

        for candidates in entity_index.values():
            if len(candidates) < 2:
                continue
            # Chaining consecutive candidates is enough: union-find makes the
            # relation transitive across the whole set.
            for a, b in zip(candidates, candidates[1:]):
                if find(a) != find(b) and self._overlaps(groups[a], groups[b]):
                    union(a, b)

        merged: Dict[int, List[NormalizedLog]] = defaultdict(list)
        for gi, group in enumerate(groups):
            merged[find(gi)].extend(group)

        result = []
        for cluster in merged.values():
            cluster.sort(key=lambda l: (l.timestamp_epoch or 0.0, l.id))
            result.append(cluster)
        return result

    # ------------------------------------------------------------------ #
    # Report construction
    # ------------------------------------------------------------------ #
    def _build_report(self, idx: int, cluster: List[NormalizedLog]) -> IncidentReport:
        sev_levels = {l.level for l in cluster}
        if "CRITICAL" in sev_levels or "FATAL" in sev_levels:
            severity = "CRITICAL"
        elif "ERROR" in sev_levels:
            severity = "HIGH"
        else:
            severity = "MEDIUM"

        services = sorted({l.service for l in cluster if l.service})
        templates = sorted({l.template_id for l in cluster})

        entities_set: Set[str] = set()
        for l in cluster:
            for k, v in l.entities.items():
                if isinstance(v, list):
                    entities_set.update(str(x) for x in v)
                else:
                    entities_set.add(f"{k}:{v}")
            if l.host and l.host != "local":
                entities_set.add(f"host:{l.host}")

        evidence_snippets = [
            EvidenceSnippet(
                log_id=l.id,
                timestamp=l.timestamp,
                level=l.level,
                message=l.message[:180],
                reason=f"Anomaly score {l.anomaly_score:.2f} - template {l.template_id}",
            )
            for l in sorted(cluster, key=lambda x: x.anomaly_score, reverse=True)[:8]
        ]

        peak_score = max(l.anomaly_score for l in cluster)
        scope = services[0] if services else "System"

        if len(templates) > 1:
            summary = (
                f"{len(cluster)} correlated anomalies spanning {len(templates)} log templates "
                f"and {len(services) or 1} service(s), joined by shared entities within the same "
                f"time window. Peak anomaly score {peak_score:.2f}."
            )
        else:
            summary = (
                f"{len(cluster)} recurrences of a single log template in {scope}, consolidated "
                f"into one incident. Peak anomaly score {peak_score:.2f}."
            )

        return IncidentReport(
            id=f"INC-{idx}",
            title=f"Incident in {scope} ({len(cluster)} correlated events)",
            severity=severity,
            confidence=round(min(0.98, max(0.65, peak_score)), 2),
            summary=summary,
            probable_root_cause="Under analysis by reasoning engine",
            recommended_action="Inspect linked log evidence",
            affected_services=services,
            affected_entities=sorted(entities_set),
            evidence_log_ids=[l.id for l in cluster],
            evidence_snippets=evidence_snippets,
            start_time=cluster[0].timestamp,
            end_time=cluster[-1].timestamp,
            event_count=len(cluster),
        )
