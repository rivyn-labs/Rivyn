import os
import time
import json
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.analytics.metrics import ObservabilityEvaluator
from backend.storage.binary_engine import BinaryLogEngine

LARGE_DATASETS = [
    ("OpenStack (Full Complete)", "data/loghub/distributed_systems/openstack/raw/openstack_full.log", 250000),
    ("Mac OS (Full Complete)", "data/loghub/operating_systems/mac/raw/mac_full.log", 150000),
    ("HDFS (100k Big Data)", "data/loghub/distributed_systems/hdfs/raw/hdfs_100k.log", 120000),
    ("Linux (Full Complete)", "data/loghub/operating_systems/linux/raw/linux_full.log", 30000),
]

def run_large_benchmarks():
    print("==========================================================================================")
    print("                 LOGHUB LARGE-SCALE & FULL DATASET BENCHMARK SUITE                        ")
    print("==========================================================================================")
    results = []

    for name, path, max_lines in LARGE_DATASETS:
        if not os.path.exists(path):
            print(f"Skipping {name}: {path} not found.")
            continue

        raw_size_mb = os.path.getsize(path) / (1024 * 1024)
        t0 = time.time()
        batch = LogLoader.load_from_file(path, max_lines=max_lines, dataset_name=name.lower().split()[0])
        t_parse = time.time() - t0
        parse_throughput = int(len(batch.logs) / max(0.001, t_parse))

        t1 = time.time()
        detector = HybridAnomalyDetector()
        batch.logs = detector.detect_anomalies(batch.logs)
        t_anomaly = time.time() - t1

        t2 = time.time()
        correlator = IncidentCorrelator()
        incidents = correlator.correlate(batch.logs)
        t_corr = time.time() - t2

        total_elapsed = t_parse + t_anomaly + t_corr
        metrics = ObservabilityEvaluator.calculate_metrics(batch.logs, incidents, len(batch.templates), total_elapsed)

        # Binary Storage
        t3 = time.time()
        save_stats = BinaryLogEngine.save_batch(batch, "data/binary")
        t_save = time.time() - t3

        # Vectorized Scan
        t4 = time.time()
        scan_stats = BinaryLogEngine.scan_anomalies_vectorized(save_stats["file_path"])
        t_scan = time.time() - t4

        entry = {
            "dataset": name,
            "raw_file_mb": round(raw_size_mb, 2),
            "lines": len(batch.logs),
            "detected_format": batch.detected_format,
            "templates_count": len(batch.templates),
            "parse_throughput_lines_sec": parse_throughput,
            "parse_time_sec": round(t_parse, 2),
            "anomalies_count": metrics.anomalies_count,
            "incidents_count": metrics.incidents_count,
            "noise_reduction_ratio": f"{metrics.noise_reduction_ratio}%",
            "triage_speedup": f"{metrics.triage_speedup_ratio}x",
            "parquet_size_mb": round(save_stats["binary_bytes"] / (1024*1024), 2),
            "storage_compression_saved": f"{save_stats['compression_ratio_pct']}%",
            "storage_reduction_factor": save_stats["storage_reduction_factor"],
            "scan_throughput": scan_stats["scan_throughput_rows_per_sec"],
            "scan_latency_ms": scan_stats["scan_latency_ms"],
        }
        results.append(entry)

        print(f"[{name}]")
        print(f"  Lines: {len(batch.logs):,} ({raw_size_mb:.2f} MB) | Dialect: {batch.detected_format}")
        print(f"  Drain Parser: {len(batch.templates)} templates in {t_parse:.2f}s ({parse_throughput:,} lines/sec)")
        print(f"  AI Anomalies: {metrics.anomalies_count:,} flagged | Correlated Incidents: {metrics.incidents_count}")
        print(f"  Noise Reduction: {metrics.noise_reduction_ratio}% | Triage Velocity: {metrics.triage_speedup_ratio}x")
        print(f"  Binary Parquet: {save_stats['raw_text_bytes']/(1024*1024):.2f} MB -> {save_stats['binary_bytes']/(1024*1024):.2f} MB ({save_stats['compression_ratio_pct']}% saved, {save_stats['storage_reduction_factor']} reduction)")
        print(f"  Vectorized Scan: {scan_stats['scan_latency_ms']:.2f} ms ({scan_stats['scan_throughput_rows_per_sec']})")
        print("------------------------------------------------------------------------------------------")

    with open("data/benchmark_large_datasets.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nSaved large dataset benchmarks to data/benchmark_large_datasets.json")
    return results

if __name__ == "__main__":
    run_large_benchmarks()
