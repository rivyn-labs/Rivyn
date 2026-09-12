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
    assert len(datasets) >= 4

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

    # Check incidents
    res_inc = client.get("/api/analysis/incidents")
    assert res_inc.status_code == 200
    assert len(res_inc.json()["incidents"]) > 0

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
    assert "hdfs" in bench
    assert "linux" in bench
