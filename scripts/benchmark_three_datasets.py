import os
import sys
import time
import json
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.analytics.metrics import ObservabilityEvaluator
from backend.storage.binary_engine import BinaryLogEngine

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# The three datasets in D:\StartStuttgartHackathon\data\samples
TARGETS = [
    ("Linux", "data/samples/Linux.log", None),            # All 25,567 lines (100% complete)
    ("OpenStack", "data/samples/OpenStack.log", None),    # All 207,820 lines (100% complete)
    ("HDFS", "data/samples/HDFS.log", 1000000),           # 1,000,000 lines milestone from 1.47GB file
]

def run_benchmarks():
    print("==========================================================================================", flush=True)
    print("        AETHER BENCHMARK SUITE: THREE USER DATASETS (Linux, OpenStack, HDFS)             ", flush=True)
    print("==========================================================================================", flush=True)
    
    results = []
    
    for name, path, max_lines in TARGETS:
        if not os.path.exists(path):
            print(f"Error: File {path} not found!", flush=True)
            continue
            
        file_size_bytes = os.path.getsize(path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        print(f"\n[{name}] -> File: {path} ({file_size_mb:.2f} MB)", flush=True)

        # 1. Ingestion & Drain Parser
        t0 = time.time()
        batch = LogLoader.load_from_file(path, max_lines=max_lines, dataset_name=name.lower())
        t_parse = time.time() - t0
        lines_count = len(batch.logs)
        throughput = int(lines_count / max(0.0001, t_parse))
        print(f"  [1] Drain Online Parser: {lines_count:,} lines in {t_parse:.2f}s ({throughput:,} lines/sec) -> {len(batch.templates)} templates (Dialect: {batch.detected_format})", flush=True)

        # 2. Multi-Tier AI Anomaly Detection
        t1 = time.time()
        detector = HybridAnomalyDetector()
        batch.logs = detector.detect_anomalies(batch.logs)
        t_anom = time.time() - t1
        anomalies_count = sum(1 for l in batch.logs if l.is_anomaly)
        print(f"  [2] Multi-Tier AI Anomaly Detection: Flagged {anomalies_count:,} anomalies in {t_anom:.2f}s ({int(lines_count/max(0.0001, t_anom)):,} logs/sec)", flush=True)

        # 3. Incident Correlation & KPI Evaluation
        t2 = time.time()
        correlator = IncidentCorrelator()
        incidents = correlator.correlate(batch.logs)
        t_corr = time.time() - t2
        total_time = t_parse + t_anom + t_corr
        metrics = ObservabilityEvaluator.calculate_metrics(batch.logs, incidents, len(batch.templates), total_time)
        print(f"  [3] Incident Correlation: {len(incidents):,} correlated incidents ({metrics.noise_reduction_ratio}% noise reduction, {metrics.triage_speedup_ratio}x triage speedup)", flush=True)

        # 4. Big Data Parquet Binary Serialization
        t3 = time.time()
        save_stats = BinaryLogEngine.save_batch(batch, "data/binary")
        t_save = time.time() - t3
        raw_mb = save_stats["raw_text_bytes"] / (1024 * 1024)
        parquet_mb = save_stats["binary_bytes"] / (1024 * 1024)
        print(f"  [4] Parquet Binary Engine: {raw_mb:.2f} MB raw text -> {parquet_mb:.2f} MB Parquet ({save_stats['compression_ratio_pct']}% saved, {save_stats['storage_reduction_factor']} reduction)", flush=True)

        # 5. Zero-Copy Vectorized Anomaly Scan
        t4 = time.time()
        scan_stats = BinaryLogEngine.scan_anomalies_vectorized(save_stats["file_path"])
        t_scan = time.time() - t4
        print(f"  [5] Vectorized Zero-Copy Scan: Scanned {scan_stats['total_rows_scanned']:,} rows in {scan_stats['scan_latency_ms']:.2f} ms ({scan_stats['scan_throughput_rows_per_sec']})", flush=True)

        entry = {
            "dataset": name,
            "filepath": path,
            "raw_file_size_mb": round(file_size_mb, 2),
            "lines_processed": lines_count,
            "dialect": batch.detected_format,
            "templates_count": len(batch.templates),
            "parse_throughput_lines_sec": throughput,
            "parse_time_sec": round(t_parse, 2),
            "anomalies_flagged": anomalies_count,
            "incidents_formed": len(incidents),
            "noise_reduction_ratio": f"{metrics.noise_reduction_ratio}%",
            "triage_speedup": f"{metrics.triage_speedup_ratio}x",
            "raw_text_mb": round(raw_mb, 2),
            "parquet_binary_mb": round(parquet_mb, 2),
            "storage_saved_pct": f"{save_stats['compression_ratio_pct']}%",
            "storage_reduction_factor": save_stats["storage_reduction_factor"],
            "scan_latency_ms": scan_stats["scan_latency_ms"],
            "scan_throughput": scan_stats["scan_throughput_rows_per_sec"],
            "total_pipeline_time_sec": round(total_time, 2)
        }
        results.append(entry)

    with open("data/benchmark_three_datasets.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n==========================================================================================", flush=True)
    print("BENCHMARK COMPLETED FOR ALL THREE DATASETS! Results saved to data/benchmark_three_datasets.json", flush=True)
    print("==========================================================================================", flush=True)
    return results

if __name__ == "__main__":
    run_benchmarks()
