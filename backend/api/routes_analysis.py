from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from collections import Counter
from backend.api.state import state
from backend.analytics.metrics import ObservabilityEvaluator

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])

@router.get("/overview")
def get_overview():
    if not state.current_batch:
        return {"status": "no_data", "message": "No log dataset loaded yet. Please ingest a dataset first."}

    batch = state.current_batch
    levels_count = Counter(l.level for l in batch.logs)

    return {
        "status": "active",
        "dataset_name": batch.dataset_name,
        "detected_format": batch.detected_format,
        "total_logs": batch.total_lines,
        "templates_count": len(batch.templates),
        "anomalies_count": batch.metrics.anomalies_count,
        "incidents_count": batch.metrics.incidents_count,
        "noise_reduction_ratio": batch.metrics.noise_reduction_ratio,
        "level_breakdown": dict(levels_count),
        "metrics": batch.metrics.model_dump(),
        "triage_baseline": {
            "kind": "modeled",
            "manual_seconds_per_anomalous_log": ObservabilityEvaluator.MANUAL_REVIEW_SEC_PER_LOG,
            "description": "Manual review is modeled at 15 seconds per anomalous log; it is not a human-timed study."
        }
    }

@router.get("/incidents")
def get_incidents(
    limit: int = Query(12, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if not state.current_batch:
        return {"total": 0, "offset": offset, "limit": limit, "incidents": []}

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranked = sorted(
        state.current_batch.incidents,
        key=lambda incident: (
            severity_rank.get(incident.severity.upper(), 4),
            -incident.confidence,
            -incident.event_count,
            incident.start_time or "",
        ),
    )
    return {
        "total": len(ranked),
        "offset": offset,
        "limit": limit,
        "incidents": [inc.model_dump() for inc in ranked[offset : offset + limit]],
    }

@router.get("/logs")
def get_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    severity: Optional[str] = None,
    anomalies_only: bool = False,
    search: Optional[str] = None,
    template_id: Optional[str] = None
):
    if not state.current_batch:
        return {"total": 0, "logs": []}

    filtered = state.current_batch.logs

    if severity:
        sev_upper = severity.upper()
        filtered = [l for l in filtered if l.level.upper() == sev_upper]

    if anomalies_only:
        filtered = [l for l in filtered if l.is_anomaly]

    if template_id:
        filtered = [l for l in filtered if l.template_id == template_id]

    if search:
        s_lower = search.lower()
        filtered = [l for l in filtered if s_lower in l.message.lower() or s_lower in l.service.lower() or s_lower in str(l.entities).lower()]

    total_matching = len(filtered)
    page_logs = filtered[offset : offset + limit]

    return {
        "total": total_matching,
        "offset": offset,
        "limit": limit,
        "logs": [l.model_dump() for l in page_logs]
    }

@router.get("/timeline")
def get_timeline(buckets: int = 30):
    if not state.current_batch or not state.current_batch.logs:
        return {"buckets": []}

    logs = state.current_batch.logs
    epochs = [l.timestamp_epoch for l in logs if l.timestamp_epoch is not None]
    if not epochs:
        return {"buckets": []}

    min_e, max_e = min(epochs), max(epochs)
    span = max(1.0, max_e - min_e)
    bucket_size = span / buckets

    bucket_data = [
        {"bucket_idx": i, "start_epoch": min_e + (i * bucket_size), "total_count": 0, "anomaly_count": 0, "timestamp_label": ""}
        for i in range(buckets)
    ]

    for l in logs:
        if l.timestamp_epoch is None:
            continue
        idx = min(buckets - 1, int((l.timestamp_epoch - min_e) / bucket_size))
        bucket_data[idx]["total_count"] += 1
        if l.is_anomaly:
            bucket_data[idx]["anomaly_count"] += 1
        if not bucket_data[idx]["timestamp_label"] and l.timestamp:
            bucket_data[idx]["timestamp_label"] = l.timestamp.split('T')[-1][:8]

    return {"buckets": bucket_data}
