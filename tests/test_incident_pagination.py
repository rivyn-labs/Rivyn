from types import SimpleNamespace

from backend.api.routes_analysis import get_incidents
from backend.api.state import state
from backend.normalization.schema import IncidentReport


def _incident(incident_id, severity, confidence, event_count):
    return IncidentReport(
        id=incident_id,
        title=incident_id,
        severity=severity,
        confidence=confidence,
        summary="test incident",
        probable_root_cause="test cause",
        recommended_action="test action",
        event_count=event_count,
    )


def test_incidents_are_ranked_and_paginated():
    original_batch = state.current_batch
    try:
        state.current_batch = SimpleNamespace(incidents=[
            _incident("INC-MED", "MEDIUM", 0.99, 99),
            _incident("INC-HIGH", "HIGH", 0.70, 2),
            _incident("INC-CRIT-LOW", "CRITICAL", 0.80, 2),
            _incident("INC-CRIT-HIGH", "CRITICAL", 0.95, 1),
        ])

        first_page = get_incidents(limit=2, offset=0)
        second_page = get_incidents(limit=2, offset=2)

        assert first_page["total"] == 4
        assert [incident["id"] for incident in first_page["incidents"]] == [
            "INC-CRIT-HIGH", "INC-CRIT-LOW"
        ]
        assert [incident["id"] for incident in second_page["incidents"]] == [
            "INC-HIGH", "INC-MED"
        ]
    finally:
        state.current_batch = original_batch
