import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_e2e_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_e2e_datasets_list():
    res = client.get("/api/datasets")
    assert res.status_code == 200
    datasets = res.json()["datasets"]
    assert len(datasets) >= 3
    dataset_ids = [d["id"] for d in datasets]
    assert "openstack" in dataset_ids
    assert "linux" in dataset_ids
    assert "hdfs" in dataset_ids

def test_e2e_openstack_slice():
    res = client.post("/api/ingest/sample", json={"dataset": "openstack", "max_lines": 500})
    assert res.status_code == 200
    data = res.json()
    assert data["total_lines"] == 500
    assert data["status"] == "success"
    assert "binary_storage" in data


def test_e2e_upload_small_log_and_duplicate_is_idempotent():
    content = (
        b"2024-01-01 00:00:01 ERROR api: request req-12345678 failed\n"
        b"2024-01-01 00:00:02 INFO api: retry scheduled\n"
        b"2024-01-01 00:00:03 ERROR api: request req-12345678 failed\n"
    )
    files = {"file": ("upload-e2e.log", content, "text/plain")}

    first = client.post("/api/ingest/upload", files=files)
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["submitted_lines"] == 3
    assert first_data["accepted_lines"] == 3
    assert first_data["new_lines"] == 3
    assert first_data["duplicate"] is False
    assert first_data["source_line_start"] == 1
    assert first_data["source_line_end"] == 3
    assert first_data["next_source_line"] == 4
    assert first_data["truncated"] is False

    second = client.post("/api/ingest/upload", files=files)
    assert second.status_code == 200
    duplicate_data = second.json()
    assert duplicate_data["new_lines"] == 0
    assert duplicate_data["duplicate"] is True
    assert duplicate_data["next_source_line"] == 4


def test_e2e_upload_rejects_empty_file():
    res = client.post("/api/ingest/upload", files={"file": ("empty.log", b"", "text/plain")})
    assert res.status_code == 400
    assert "no log lines" in res.json()["detail"]


def test_e2e_upload_has_no_line_limit():
    content = b"\n".join(
        f"2024-01-01 00:00:{index % 60:02d} INFO api: event {index}".encode()
        for index in range(1, 2003)
    )
    response = client.post("/api/ingest/upload", files={"file": ("unlimited-e2e.log", content, "text/plain")})
    assert response.status_code == 200
    data = response.json()
    assert data["accepted_lines"] == 2002
    assert data["new_lines"] == 2002
    assert data["source_line_start"] == 1
    assert data["source_line_end"] == 2002
    assert data["truncated"] is False


def test_e2e_ai_status_does_not_expose_a_key():
    res = client.get("/api/ai/status")
    assert res.status_code == 200
    data = res.json()
    assert set(data) == {"openai_configured", "active_provider", "model", "max_incidents_per_ingestion"}

def test_e2e_ingest_and_query():
    # Ingest linux sample
    res = client.post("/api/ingest/sample", json={"dataset": "linux", "max_lines": 150})
    assert res.status_code == 200
    data = res.json()
    assert data["detected_format"] == "syslog"
    assert data["total_lines"] > 0

    # Check overview
    res_ov = client.get("/api/analysis/overview")
    assert res_ov.status_code == 200
    assert res_ov.json()["status"] == "active"
    assert res_ov.json()["triage_baseline"]["kind"] == "modeled"

    # Check incidents
    res_inc = client.get("/api/analysis/incidents?limit=3&offset=0")
    assert res_inc.status_code == 200
    assert len(res_inc.json()["incidents"]) > 0
    assert res_inc.json()["total"] >= len(res_inc.json()["incidents"])
    assert len(res_inc.json()["incidents"]) <= 3

    # Query Copilot
    res_qa = client.post("/api/investigate/query", json={"query": "authentication failure"})
    assert res_qa.status_code == 200
    qa_data = res_qa.json()
    assert qa_data["confidence"] > 0.0
    assert len(qa_data["evidence"]) > 0

def test_e2e_benchmark():
    res = client.get("/api/metrics/benchmark")
    assert res.status_code == 200
    bench = res.json()["benchmark_results"]
    # The benchmark covers whichever datasets are present; HDFS is a large
    # optional download and may legitimately be absent from a fresh clone.
    assert bench, "benchmark returned no datasets"
    assert "linux" in bench
