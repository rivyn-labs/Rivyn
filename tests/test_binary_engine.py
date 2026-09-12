import os
import pytest
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.storage.binary_engine import BinaryLogEngine
from conftest import dataset_path

def test_binary_engine_save_and_scan():
    batch = LogLoader.load_from_file(dataset_path("HDFS.log"), max_lines=500)
    batch.logs = HybridAnomalyDetector().detect_anomalies(batch.logs)

    # Save to binary
    stats = BinaryLogEngine.save_batch(batch, output_dir="data/binary")
    assert os.path.exists(stats["file_path"])
    assert stats["row_count"] == 500
    assert stats["binary_bytes"] > 0
    assert stats["compression_ratio_pct"] > 0

    # Vectorized scan
    scan = BinaryLogEngine.scan_anomalies_vectorized(stats["file_path"])
    assert scan["total_rows_scanned"] == 500
    assert scan["scan_latency_ms"] >= 0
    assert "rows/sec" in scan["scan_throughput_rows_per_sec"]

    # Slice zero-copy
    slice_rows = BinaryLogEngine.read_slice(stats["file_path"], offset=0, limit=10)
    assert len(slice_rows) == 10
    assert "message" in slice_rows[0]
    assert "template_id" in slice_rows[0]
