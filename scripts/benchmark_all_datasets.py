import os
import sys
import time
import json
import gc
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.analytics.metrics import ObservabilityEvaluator
from backend.storage.binary_engine import BinaryLogEngine

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Comprehensive targets across all 7 LogHub datasets in data/samples
TARGETS = [
    ("Linux", "data/samples/Linux.log", None),                          # 25,567 lines (100% complete)
    ("OpenStack", "data/samples/OpenStack.log", None),                  # 207,820 lines (100% complete)
    ("ZooKeeper", "data/samples/Zookeeper.log", None),                  # 74,380 lines (100% complete)
    ("Hadoop", "data/samples/Hadoop.log", None),                        # 394,310 lines (100% complete)
    ("Spark", "data/samples/Spark.log", 500000),                        # 500,000 lines milestone
    ("BGL", "data/samples/BGL/BGL.log", 500000),                        # 500,000 lines milestone (BlueGene/L HPC)
    ("HDFS", "data/samples/HDFS.log", 1000000),                         # 1,000,000 lines milestone (1.58 GB file)
]

def run_benchmarks():
    print("==========================================================================================", flush=True)
    print("        AETHER BENCHMARK SUITE: ALL SEVEN HETEROGENEOUS LOG DATASETS                     ", flush=True)
    print("==========================================================================================", flush=True)
    
    results = []
    total_pipeline_start = time.time()
    total_lines_all = 0
    
    for name, path, max_lines in TARGETS:
        target_path = path
        if not os.path.exists(target_path):
            # Fallback alt paths
            if name == "ZooKeeper" and os.path.exists("data/samples/Zookeeper/Zookeeper.log"):
                target_path = "data/samples/Zookeeper/Zookeeper.log"
            elif name == "BGL" and os.path.exists("data/samples/BGL.log"):
                target_path = "data/samples/BGL.log"
            else:
                print(f"Error: Target {name} file {path} not found! Skipping...", flush=True)
                continue
            
        file_size_bytes = os.path.getsize(target_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        print(f"\n>>> [{name}] -> File: {target_path} ({file_size_mb:.2f} MB)", flush=True)

        # 1. Ingestion & Drain Parser
        t0 = time.time()
        batch = LogLoader.load_from_file(target_path, max_lines=max_lines, dataset_name=name.lower())
        t_parse = time.time() - t0
        lines_count = len(batch.logs)
        total_lines_all += lines_count
        throughput = int(lines_count / max(0.0001, t_parse))
        print(f"  [1] Drain Online Parser: {lines_count:,} lines in {t_parse:.2f}s ({throughput:,} lines/sec) -> {len(batch.templates):,} templates (Dialect: {batch.detected_format})", flush=True)

        # 2. Multi-Tier AI Anomaly Detection
        t1 = time.time()
        detector = HybridAnomalyDetector()
        batch.logs = detector.detect_anomalies(batch.logs)
        t_anom = time.time() - t1
        anomalies_count = sum(1 for l in batch.logs if l.is_anomaly)
        anom_throughput = int(lines_count / max(0.0001, t_anom))
        print(f"  [2] Multi-Tier Anomaly Detection: Flagged {anomalies_count:,} anomalies in {t_anom:.2f}s ({anom_throughput:,} logs/sec)", flush=True)

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
            "filepath": target_path,
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
        del batch
        del incidents
        gc.collect()

    total_wall_time = time.time() - total_pipeline_start
    overall_summary = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_datasets_benchmarked": len(results),
        "total_lines_processed": total_lines_all,
        "total_wall_time_sec": round(total_wall_time, 2),
        "datasets": results
    }

    output_file = "data/benchmark_all_datasets.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(overall_summary, f, indent=2)

    print("\n==========================================================================================", flush=True)
    print(f"BENCHMARK SUITE COMPLETE! {total_lines_all:,} total lines processed across {len(results)} datasets in {total_wall_time:.2f}s.", flush=True)
    print(f"Full benchmark data saved to: {output_file}", flush=True)
    print("==========================================================================================", flush=True)
    return overall_summary

if __name__ == "__main__":
    run_benchmarks()
