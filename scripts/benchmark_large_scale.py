"""
Large-Scale Big Data Benchmark for AETHER Binary Columnar Storage Engine:
Tests ingestion, Drain template mining, hybrid anomaly scoring,
Parquet binary serialization, and zero-copy memory-mapped scans at 10k, 50k, and 100k lines.
"""

import os
import sys
import time
import json

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.expand_datasets import expand_dataset
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.storage.binary_engine import BinaryLogEngine

def run_scale_test():
    print("=" * 70)
    print("      AETHER BIG DATA BENCHMARK: 100,000 LINES SCALE TEST        ")
    print("=" * 70)

    source_hdfs = "data/samples/hdfs_sample.log"
    target_hdfs_100k = "data/samples_expanded/hdfs_100k.log"

    # 1. Expand dataset to 100,000 lines if not already generated
    if not os.path.exists(target_hdfs_100k):
        print("\n[*] Step 1: Generating 100,000-line enterprise HDFS dataset...")
        expand_dataset(source_hdfs, target_hdfs_100k, target_lines=100000)
    else:
        print(f"\n[*] Step 1: Using existing 100,000-line dataset at {target_hdfs_100k}")

    raw_file_size = os.path.getsize(target_hdfs_100k)
    print(f"    Raw Text File Size: {raw_file_size:,} bytes ({round(raw_file_size / (1024*1024), 2)} MB)")

    # 2. Benchmark across multiple scale tiers: 10k, 50k, 100k
    scale_tiers = [10000, 50000, 100000]
    benchmark_results = []

    for tier in scale_tiers:
        print(f"\n" + "-" * 70)
        print(f"[*] Testing Scale Tier: {tier:,} Lines")
        print("-" * 70)

        # A. Ingestion & Drain Parsing
        t0 = time.time()
        batch = LogLoader.load_from_file(target_hdfs_100k, max_lines=tier, dataset_name=f"hdfs_{tier // 1000}k")
        ingest_time = time.time() - t0
        ingest_rate = int(tier / max(0.001, ingest_time))
        print(f"  [1] Ingestion & Drain Parsing : {ingest_time:.3f} sec ({ingest_rate:,} lines/sec)")
        print(f"      Templates Discovered      : {len(batch.templates)}")

        # B. AI Anomaly Scoring
        t1 = time.time()
        detector = HybridAnomalyDetector()
        batch.logs = detector.detect_anomalies(batch.logs)
        ai_time = time.time() - t1
        ai_rate = int(tier / max(0.001, ai_time))
        anomalies_count = sum(1 for l in batch.logs if l.is_anomaly)
        print(f"  [2] Hybrid AI Anomaly Scoring : {ai_time:.3f} sec ({ai_rate:,} logs/sec)")
        print(f"      Anomalies Flagged         : {anomalies_count:,} ({round(anomalies_count/tier*100, 2)}%)")

        # C. Binary Columnar Parquet Serialization
        t2 = time.time()
        save_stats = BinaryLogEngine.save_batch(batch, output_dir="data/binary")
        bin_write_time = time.time() - t2
        print(f"  [3] Binary Parquet Encoding   : {bin_write_time:.3f} sec (Snappy + Dictionary)")
        print(f"      Raw ASCII Footprint       : {save_stats['raw_text_bytes']:,} bytes ({round(save_stats['raw_text_bytes']/(1024*1024), 2)} MB)")
        print(f"      Binary Parquet Footprint  : {save_stats['binary_bytes']:,} bytes ({round(save_stats['binary_bytes']/(1024*1024), 2)} MB)")
        print(f"      Compression Ratio         : {save_stats['compression_ratio_pct']}% reduction ({save_stats['storage_reduction_factor']} smaller)")

        # D. Zero-Copy Vectorized Anomaly Scan directly on Binary File
        scan_stats = BinaryLogEngine.scan_anomalies_vectorized(save_stats["file_path"])
        print(f"  [4] Zero-Copy Vectorized Scan : {scan_stats['scan_latency_ms']} ms ({scan_stats['scan_throughput_rows_per_sec']})")

        benchmark_results.append({
            "tier_lines": tier,
            "raw_size_mb": round(save_stats['raw_text_bytes'] / (1024*1024), 2),
            "binary_size_mb": round(save_stats['binary_bytes'] / (1024*1024), 2),
            "compression_pct": save_stats['compression_ratio_pct'],
            "reduction_factor": save_stats['storage_reduction_factor'],
            "ingest_time_sec": round(ingest_time, 2),
            "ai_time_sec": round(ai_time, 2),
            "scan_latency_ms": scan_stats['scan_latency_ms'],
            "scan_throughput": scan_stats['scan_throughput_rows_per_sec']
        })

    print("\n" + "=" * 70)
    print("                    FINAL BENCHMARK SUMMARY TABLE                     ")
    print("=" * 70)
    print(f"{'Scale Tier':<12} | {'Raw Text':<10} | {'Binary Parquet':<15} | {'Reduction':<10} | {'Scan Latency':<12} | {'Throughput':<16}")
    print("-" * 75)
    for r in benchmark_results:
        print(f"{r['tier_lines']:<12,} | {r['raw_size_mb']} MB   | {r['binary_size_mb']} MB        | {r['reduction_factor']:<10} | {r['scan_latency_ms']:<7} ms   | {r['scan_throughput']}")
    print("=" * 75)

if __name__ == "__main__":
    run_scale_test()
