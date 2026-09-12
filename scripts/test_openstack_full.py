import time
import os
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.storage.binary_engine import BinaryLogEngine

def test_full_pipeline():
    file_path = "data/samples/OpenStack.log"
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist!")
        return

    raw_bytes = os.path.getsize(file_path)
    print("=== OpenStack Complete Dataset Benchmark ===")
    print(f"File size on disk: {raw_bytes / (1024*1024):.2f} MB")

    # Step 1: Load & Drain Parse
    t0 = time.time()
    batch = LogLoader.load_from_file(file_path, max_lines=300000, dataset_name="openstack_full")
    t_drain = time.time() - t0
    print(f"[1] Ingestion & Drain Parser: {len(batch.logs):,} lines parsed into {len(batch.templates):,} templates in {t_drain:.2f}s ({len(batch.logs)/t_drain:,.0f} lines/sec)")

    # Step 2: Anomaly Detection (Isolation Forest + Frequency + Semantic)
    t1 = time.time()
    detector = HybridAnomalyDetector()
    batch.logs = detector.detect_anomalies(batch.logs)
    t_anomaly = time.time() - t1
    anomalies = [l for l in batch.logs if l.is_anomaly]
    print(f"[2] Multi-Tier AI Anomaly Detection: Flagged {len(anomalies):,} anomalies in {t_anomaly:.2f}s")

    # Step 3: Incident Correlation
    t2 = time.time()
    correlator = IncidentCorrelator()
    incidents = correlator.correlate(batch.logs)
    t_corr = time.time() - t2
    print(f"[3] Incident Correlation: Built {len(incidents):,} correlated incidents in {t_corr:.2f}s")

    # Step 4: Parquet Columnar Serialization
    t3 = time.time()
    save_stats = BinaryLogEngine.save_batch(batch, "data/binary")
    t_save = time.time() - t3
    print(f"[4] Binary Storage: Saved {save_stats['row_count']:,} rows to Parquet in {t_save:.2f}s")
    print(f"    Raw Text: {save_stats['raw_text_bytes'] / (1024*1024):.2f} MB -> Parquet: {save_stats['binary_bytes'] / (1024*1024):.2f} MB (Reduction: {save_stats['storage_reduction_factor']}, Saved: {save_stats['compression_ratio_pct']}%)")

    # Step 5: Vectorized Zero-Copy Parquet Scan
    t4 = time.time()
    scan_stats = BinaryLogEngine.scan_anomalies_vectorized(save_stats["file_path"])
    t_scan = time.time() - t4
    print(f"[5] Parquet Vectorized Scan: Scanned {scan_stats['total_rows_scanned']:,} rows in {scan_stats['scan_latency_ms']:.2f} ms ({scan_stats['scan_throughput_rows_per_sec']})")
    print(f"    Anomalies identified in binary scan: {scan_stats['anomalies_found']:,}")
    print("=== Complete Pipeline Successful ===")

if __name__ == "__main__":
    test_full_pipeline()
