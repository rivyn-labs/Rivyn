import pytest
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.sequence_miner import SequenceMiner
from backend.ai.embeddings import LogEmbeddingIndex
from backend.ai.llm_reasoner import GroundedReasoner

def test_anomaly_detector():
    batch = LogLoader.load_from_file("data/samples/Linux.log", max_lines=150)
    detector = HybridAnomalyDetector()
    analyzed = detector.detect_anomalies(batch.logs)
    anomalies = [l for l in analyzed if l.is_anomaly]
    assert len(anomalies) > 0
    # Top anomalies should have high anomaly scores
    assert max(l.anomaly_score for l in anomalies) >= 0.70

def test_embeddings_and_retrieval():
    batch = LogLoader.load_from_file("data/samples/HDFS.log", max_lines=100)
    index = LogEmbeddingIndex(chunk_size=4)
    index.build_index(batch.logs)
    
    results = index.search("PacketResponder block terminating", top_k=2)
    assert len(results) > 0
    chunk, score = results[0]
    assert score > 0.0
    assert "PacketResponder" in chunk.text

def test_grounded_reasoner_qa():
    batch = LogLoader.load_from_file("data/samples/HDFS.log", max_lines=100)
    index = LogEmbeddingIndex(chunk_size=4)
    index.build_index(batch.logs)
    
    reasoner = GroundedReasoner()
    qa_res = reasoner.investigate_query("PacketResponder", batch.logs, index)
    assert qa_res["confidence"] > 0.0
    assert len(qa_res["evidence"]) > 0
    assert "Line" in qa_res["answer"]
