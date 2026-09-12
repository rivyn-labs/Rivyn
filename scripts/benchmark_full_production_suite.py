import os
import sys
import time
import json
from typing import Dict, Any, List
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.analytics.metrics import ObservabilityEvaluator
from backend.storage.binary_engine import BinaryLogEngine

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BENCHMARK_TARGETS = [
    # (Display Name, Domain, File Path, Max Lines to Benchmark)
    ("OpenStack", "Cloud", "data/loghub/distributed_systems/openstack/raw/openstack_full.log", 250000),
    ("Mac OS", "OS", "data/loghub/operating_systems/mac/raw/mac_full.log", 150000),
    ("Hadoop", "Distributed Systems", "data/loghub/distributed_systems/hadoop/raw/hadoop_full.log", 200000),
    ("HealthApp", "Mobile", "data/loghub/mobile_systems/healthapp/raw/healthapp_full.log", 250000),
    ("Zookeeper", "Distributed Systems", "data/loghub/distributed_systems/zookeeper/raw/zookeeper_full.log", 100000),
    ("Apache", "Server App", "data/loghub/server_applications/apache/raw/apache_full.log", 100000),
    ("Linux", "OS", "data/loghub/operating_systems/linux/raw/linux_full.log", 30000),
    ("Proxifier", "Server App", "data/loghub/server_applications/proxifier/raw/proxifier_full.log", 30000),
    ("OpenSSH", "Server App", "data/loghub/server_applications/openssh/raw/openssh_full.log", 250000),
    ("HPC", "Supercomputers", "data/loghub/supercomputers/hpc/raw/hpc_full.log", 250000),
    ("BGL", "Supercomputers", "data/loghub/supercomputers/bgl/raw/bgl_full.log", 250000),
    ("Thunderbird", "Supercomputers", "data/loghub/supercomputers/thunderbird/raw/thunderbird_full.log", 250000),
    ("HDFS", "Distributed Systems", "data/loghub/distributed_systems/hdfs/raw/hdfs_full.log", 250000),
    ("Spark", "Distributed Systems", "data/loghub/distributed_systems/spark/raw/spark_full.log", 250000),
]

def run_suite():
    print("==========================================================================================", flush=True)
    print("           AETHER MULTI-TIER AI OBSERVABILITY & PARQUET BENCHMARK SUITE                   ", flush=True)
    print("==========================================================================================", flush=True)
    
    results: List[Dict[str, Any]] = []

    for name, domain, path, max_lines in BENCHMARK_TARGETS:
        if not os.path.exists(path):
            print(f"Skipping {name}: file {path} not found.", flush=True)
            continue

        raw_size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"\n[Benchmarking {name} ({domain}) - File Size: {raw_size_mb:.2f} MB]...", flush=True)

        # 1. Ingestion & Drain Parser
        t0 = time.time()
        batch = LogLoader.load_from_file(path, max_lines=max_lines, dataset_name=name.lower())
        t_parse = time.time() - t0
        lines_count = len(batch.logs)
        parse_throughput = int(lines_count / max(0.0001, t_parse))
        print(f"  -> Drain Parser: {lines_count:,} lines in {t_parse:.2f}s ({parse_throughput:,} lines/sec) -> {len(batch.templates)} templates (Dialect: {batch.detected_format})", flush=True)

        # 2. Multi-Tier AI Anomaly Detection
        t1 = time.time()
        detector = HybridAnomalyDetector()
        batch.logs = detector.detect_anomalies(batch.logs)
        t_anom = time.time() - t1
        anomalies_count = sum(1 for l in batch.logs if l.is_anomaly)
        print(f"  -> AI Detection: Flagged {anomalies_count:,} anomalies in {t_anom:.2f}s ({int(lines_count/max(0.0001, t_anom)):,} logs/sec)", flush=True)

        # 3. Incident Correlation & KPI Evaluation
        t2 = time.time()
        correlator = IncidentCorrelator()
        incidents = correlator.correlate(batch.logs)
        t_corr = time.time() - t2
        total_pipeline_time = t_parse + t_anom + t_corr
        metrics = ObservabilityEvaluator.calculate_metrics(batch.logs, incidents, len(batch.templates), total_pipeline_time)
        print(f"  -> Correlation: Built {len(incidents)} incidents ({metrics.noise_reduction_ratio}% noise reduction, {metrics.triage_speedup_ratio}x speedup)", flush=True)

        # 4. Parquet Binary Columnar Serialization
        t3 = time.time()
        save_stats = BinaryLogEngine.save_batch(batch, "data/binary")
        t_save = time.time() - t3
        parquet_mb = save_stats["binary_bytes"] / (1024 * 1024)
        raw_text_mb = save_stats["raw_text_bytes"] / (1024 * 1024)
        print(f"  -> Parquet Binary: {raw_text_mb:.2f} MB raw -> {parquet_mb:.2f} MB binary ({save_stats['compression_ratio_pct']}% saved, {save_stats['storage_reduction_factor']} reduction)", flush=True)

        # 5. Zero-Copy Vectorized Scan
        t4 = time.time()
        scan_stats = BinaryLogEngine.scan_anomalies_vectorized(save_stats["file_path"])
        t_scan = time.time() - t4
        print(f"  -> Vectorized Scan: {scan_stats['scan_latency_ms']:.2f} ms ({scan_stats['scan_throughput_rows_per_sec']})", flush=True)

        entry = {
            "system": name,
            "domain": domain,
            "raw_file_mb": round(raw_size_mb, 2),
            "lines_benchmarked": lines_count,
            "dialect": batch.detected_format,
            "templates_count": len(batch.templates),
            "parse_throughput_lines_sec": parse_throughput,
            "parse_time_sec": round(t_parse, 2),
            "anomalies_flagged": anomalies_count,
            "incidents_formed": len(incidents),
            "noise_reduction_ratio": f"{metrics.noise_reduction_ratio}%",
            "triage_speedup": f"{metrics.triage_speedup_ratio}x",
            "raw_text_mb": round(raw_text_mb, 2),
            "parquet_mb": round(parquet_mb, 2),
            "storage_saved_pct": f"{save_stats['compression_ratio_pct']}%",
            "storage_reduction_factor": save_stats["storage_reduction_factor"],
            "scan_latency_ms": scan_stats["scan_latency_ms"],
            "scan_throughput": scan_stats["scan_throughput_rows_per_sec"],
            "total_pipeline_sec": round(total_pipeline_time, 2)
        }
        results.append(entry)

    with open("data/benchmark_full_production_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n==========================================================================================", flush=True)
    print(f"BENCHMARK COMPLETED ACROSS {len(results)} SYSTEMS! Saved to data/benchmark_full_production_results.json", flush=True)
    print("==========================================================================================", flush=True)

if __name__ == "__main__":
    run_suite()
