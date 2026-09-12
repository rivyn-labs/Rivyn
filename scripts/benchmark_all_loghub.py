import os
import time
import json
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.analytics.metrics import ObservabilityEvaluator
from backend.storage.binary_engine import BinaryLogEngine

BENCHMARK_2K_DIR = "data/samples"
LOGHUB_DIR = "data/loghub"

def run_system_benchmark():
    # 16 Systems
    systems = [
        ("HDFS", "distributed_systems/hdfs/raw/hdfs_2k.log", "distributed_systems/hdfs/ground_truth/hdfs_2k.log_templates.csv"),
        ("Hadoop", "distributed_systems/hadoop/raw/hadoop_2k.log", "distributed_systems/hadoop/ground_truth/hadoop_2k.log_templates.csv"),
        ("Spark", "distributed_systems/spark/raw/spark_2k.log", "distributed_systems/spark/ground_truth/spark_2k.log_templates.csv"),
        ("Zookeeper", "distributed_systems/zookeeper/raw/zookeeper_2k.log", "distributed_systems/zookeeper/ground_truth/zookeeper_2k.log_templates.csv"),
        ("OpenStack", "distributed_systems/openstack/raw/openstack_2k.log", "distributed_systems/openstack/ground_truth/openstack_2k.log_templates.csv"),
        ("BGL", "supercomputers/bgl/raw/bgl_2k.log", "supercomputers/bgl/ground_truth/bgl_2k.log_templates.csv"),
        ("HPC", "supercomputers/hpc/raw/hpc_2k.log", "supercomputers/hpc/ground_truth/hpc_2k.log_templates.csv"),
        ("Thunderbird", "supercomputers/thunderbird/raw/thunderbird_2k.log", "supercomputers/thunderbird/ground_truth/thunderbird_2k.log_templates.csv"),
        ("Linux", "operating_systems/linux/raw/linux_2k.log", "operating_systems/linux/ground_truth/linux_2k.log_templates.csv"),
        ("Mac", "operating_systems/mac/raw/mac_2k.log", "operating_systems/mac/ground_truth/mac_2k.log_templates.csv"),
        ("Windows", "operating_systems/windows/raw/windows_2k.log", "operating_systems/windows/ground_truth/windows_2k.log_templates.csv"),
        ("Android", "mobile_systems/android/raw/android_2k.log", "mobile_systems/android/ground_truth/android_2k.log_templates.csv"),
        ("HealthApp", "mobile_systems/healthapp/raw/healthapp_2k.log", "mobile_systems/healthapp/ground_truth/healthapp_2k.log_templates.csv"),
        ("Apache", "server_applications/apache/raw/apache_2k.log", "server_applications/apache/ground_truth/apache_2k.log_templates.csv"),
        ("OpenSSH", "server_applications/openssh/raw/openssh_2k.log", "server_applications/openssh/ground_truth/openssh_2k.log_templates.csv"),
        ("Proxifier", "server_applications/proxifier/raw/proxifier_2k.log", "server_applications/proxifier/ground_truth/proxifier_2k.log_templates.csv")
    ]

    results = []
    print("==========================================================================================")
    print("                    LOGHUB 16-SYSTEM OBSERVEABILITY BENCHMARK SUITE                       ")
    print("==========================================================================================")

    for name, rel_log, rel_gt in systems:
        log_path = os.path.join(LOGHUB_DIR, rel_log)
        gt_path = os.path.join(LOGHUB_DIR, rel_gt)

        if not os.path.exists(log_path):
            continue

        gt_count = 0
        if os.path.exists(gt_path):
            with open(gt_path, "r", encoding="utf-8", errors="ignore") as f:
                gt_count = max(0, sum(1 for _ in f) - 1)

        t0 = time.time()
        batch = LogLoader.load_from_file(log_path, max_lines=2000, dataset_name=name.lower())
        parse_time = time.time() - t0

        t1 = time.time()
        detector = HybridAnomalyDetector()
        batch.logs = detector.detect_anomalies(batch.logs)
        anom_time = time.time() - t1

        t2 = time.time()
        correlator = IncidentCorrelator()
        incidents = correlator.correlate(batch.logs)
        corr_time = time.time() - t2

        total_elapsed = parse_time + anom_time + corr_time
        metrics = ObservabilityEvaluator.calculate_metrics(batch.logs, incidents, len(batch.templates), total_elapsed)

        # Binary Storage
        save_stats = BinaryLogEngine.save_batch(batch, "data/binary")
        scan_stats = BinaryLogEngine.scan_anomalies_vectorized(save_stats["file_path"])

        entry = {
            "system": name,
            "dialect": batch.detected_format,
            "lines": len(batch.logs),
            "templates_found": len(batch.templates),
            "ground_truth_templates": gt_count,
            "anomalies": metrics.anomalies_count,
            "incidents": metrics.incidents_count,
            "noise_reduction": f"{metrics.noise_reduction_ratio}%",
            "triage_speedup": f"{metrics.triage_speedup_ratio}x",
            "compression_saved": f"{save_stats['compression_ratio_pct']}%",
            "scan_throughput": scan_stats["scan_throughput_rows_per_sec"],
            "scan_latency_ms": scan_stats["scan_latency_ms"],
            "total_pipeline_sec": round(total_elapsed, 3)
        }
        results.append(entry)
        print(f"[{name:<11}] {batch.detected_format:<10} | Lines: {len(batch.logs):>4} | Tmpl: {len(batch.templates):>3} (GT: {gt_count:>3}) | Anom: {metrics.anomalies_count:>3} | Inc: {metrics.incidents_count:>2} | NoiseRed: {metrics.noise_reduction_ratio:>5}% | Speedup: {metrics.triage_speedup_ratio:>5}x | Parquet: {save_stats['compression_ratio_pct']:>4}% saved | Scan: {scan_stats['scan_throughput_rows_per_sec']}")

    with open("data/benchmark_16_systems.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nSaved 16-system benchmark results to data/benchmark_16_systems.json")
    return results

if __name__ == "__main__":
    run_system_benchmark()
