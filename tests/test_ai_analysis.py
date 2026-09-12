import pytest
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.sequence_miner import SequenceMiner
from backend.ai.embeddings import LogEmbeddingIndex
from backend.ai.llm_reasoner import GroundedReasoner
from conftest import dataset_path

def test_anomaly_detector():
    batch = LogLoader.load_from_file(dataset_path("Linux.log"), max_lines=150)
    detector = HybridAnomalyDetector()
    analyzed = detector.detect_anomalies(batch.logs)
    anomalies = [l for l in analyzed if l.is_anomaly]
    assert len(anomalies) > 0
    # Top anomalies should have high anomaly scores
    assert max(l.anomaly_score for l in anomalies) >= 0.70

def test_embeddings_and_retrieval():
    batch = LogLoader.load_from_file(dataset_path("HDFS.log"), max_lines=100)
    index = LogEmbeddingIndex(chunk_size=4)
    index.build_index(batch.logs)
    
    results = index.search("PacketResponder block terminating", top_k=2)
    assert len(results) > 0
    chunk, score = results[0]
    assert score > 0.0
    assert "PacketResponder" in chunk.text

def test_grounded_reasoner_qa():
    batch = LogLoader.load_from_file(dataset_path("HDFS.log"), max_lines=100)
    index = LogEmbeddingIndex(chunk_size=4)
    index.build_index(batch.logs)
    
    reasoner = GroundedReasoner()
    qa_res = reasoner.investigate_query("PacketResponder", batch.logs, index)
    assert qa_res["confidence"] > 0.0
    assert len(qa_res["evidence"]) > 0
    assert "Line" in qa_res["answer"]

def test_grounded_reasoner_extract_json():
    from backend.ai.llm_reasoner import _extract_json
    raw = '```json\n{"title": "Test Incident", "confidence": 0.95}\n```'
    parsed = _extract_json(raw)
    assert parsed["title"] == "Test Incident"
    assert parsed["confidence"] == 0.95

def test_grounded_reasoner_anthropic_mock(monkeypatch):
    from unittest.mock import MagicMock
    from backend.normalization.schema import IncidentReport
    import anthropic
    
    fake_client = MagicMock()
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"title": "Claude Diagnosed Incident", "summary": "Cluster failure", "root_cause": "[Line 1 @ T0] Auth dropped", "recommended_action": "Rotate keys", "confidence": 0.98}')]
    fake_client.messages.create.return_value = fake_msg

    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_client)
    
    reasoner = GroundedReasoner(anthropic_api_key="sk-ant-test-key")
    batch = LogLoader.load_from_file(dataset_path("Linux.log"), max_lines=50)
    incident = IncidentReport(
        id="inc-test",
        title="Initial",
        summary="",
        probable_root_cause="",
        recommended_action="",
        confidence=0.5,
        evidence_log_ids=[batch.logs[0].id],
        event_count=1,
        severity="HIGH",
        created_at="2026-09-12T10:00:00"
    )
    logs_map = {batch.logs[0].id: batch.logs[0]}
    res = reasoner.explain_incident(incident, logs_map)
    assert res.title == "Claude Diagnosed Incident"
    assert res.confidence == 0.98
    assert "Auth dropped" in res.probable_root_cause

def test_grounded_reasoner_openai_mock(monkeypatch):
    from unittest.mock import MagicMock
    from backend.normalization.schema import IncidentReport
    import openai
    
    fake_client = MagicMock()
    fake_completion = MagicMock()
    fake_choice = MagicMock()
    fake_choice.message.content = '{"title": "OpenAI Diagnosed Incident", "summary": "Nova failure", "root_cause": "[Line 1 @ T0] Hypervisor crash", "recommended_action": "Migrate VM", "confidence": 0.97}'
    fake_completion.choices = [fake_choice]
    fake_client.chat.completions.create.return_value = fake_completion

    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: fake_client)
    
    reasoner = GroundedReasoner(openai_api_key="sk-proj-test-key")
    batch = LogLoader.load_from_file(dataset_path("Linux.log"), max_lines=50)
    incident = IncidentReport(
        id="inc-openai-test",
        title="Initial",
        summary="",
        probable_root_cause="",
        recommended_action="",
        confidence=0.5,
        evidence_log_ids=[batch.logs[0].id],
        event_count=1,
        severity="HIGH",
        created_at="2026-09-12T10:00:00"
    )
    logs_map = {batch.logs[0].id: batch.logs[0]}
    res = reasoner.explain_incident(incident, logs_map)
    assert res.title == "OpenAI Diagnosed Incident"
    assert res.confidence == 0.97
    assert "Hypervisor crash" in res.probable_root_cause


