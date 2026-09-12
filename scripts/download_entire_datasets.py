"""
AETHER High-Performance Parallel Downloader for Entire Full-Scale LogHub Datasets.

Downloads 100% complete production log files for all systems.
Ensures:
  1. No duplicate files are created.
  2. If file already exists and is complete, it is skipped.
  3. Compressed archives (e.g. BGL.zip, HDFS_v1.zip) are extracted directly to
     data/loghub/<domain>/<system>/raw/<system>_full.log and the archive is deleted.
  4. Concurrent downloading via ThreadPoolExecutor.
"""

import os
import sys
import shutil
import zipfile
import urllib.request
import concurrent.futures
from typing import Dict, Optional

# Ensure clean UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

HF_BOLU_BASE = "https://huggingface.co/datasets/bolu61/loghub_2/resolve/main"
HF_YVAN_BASE = "https://huggingface.co/datasets/YvanCarre/Loghub_dataset/resolve/main"

# Target definitions for ENTIRE production log files
ENTIRE_DATASETS = [
    # Supercomputers
    {
        "name": "BGL",
        "key": "bgl",
        "domain": "supercomputers",
        "type": "zip",
        "url": f"{HF_YVAN_BASE}/BGL.zip",
        "inner_file": "BGL.log",
        "target_file": "data/loghub/supercomputers/bgl/raw/bgl_full.log",
        "expected_min_bytes": 600_000_000,
    },
    {
        "name": "HPC",
        "key": "hpc",
        "domain": "supercomputers",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/data/hpc.txt",
        "target_file": "data/loghub/supercomputers/hpc/raw/hpc_full.log",
        "expected_min_bytes": 30_000_000,
    },
    {
        "name": "Thunderbird",
        "key": "thunderbird",
        "domain": "supercomputers",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/data/thunderbird.txt",
        "target_file": "data/loghub/supercomputers/thunderbird/raw/thunderbird_full.log",
        "expected_min_bytes": 800_000_000,
    },

    # Distributed Systems
    {
        "name": "HDFS",
        "key": "hdfs",
        "domain": "distributed_systems",
        "type": "zip",
        "url": f"{HF_YVAN_BASE}/HDFS_v1.zip",
        "inner_file": "HDFS.log",
        "target_file": "data/loghub/distributed_systems/hdfs/raw/hdfs_full.log",
        "expected_min_bytes": 1_400_000_000,
    },
    {
        "name": "HDFS Anomaly Labels",
        "key": "hdfs_labels",
        "domain": "distributed_systems",
        "type": "direct",
        "url": f"{HF_YVAN_BASE}/raw/anomaly_label.csv",
        "target_file": "data/loghub/distributed_systems/hdfs/ground_truth/anomaly_label.csv",
        "expected_min_bytes": 15_000_000,
    },
    {
        "name": "Hadoop",
        "key": "hadoop",
        "domain": "distributed_systems",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/data/hadoop.txt",
        "target_file": "data/loghub/distributed_systems/hadoop/raw/hadoop_full.log",
        "expected_min_bytes": 30_000_000,
    },
    {
        "name": "Zookeeper",
        "key": "zookeeper",
        "domain": "distributed_systems",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/holdout/zookeeper.txt",
        "target_file": "data/loghub/distributed_systems/zookeeper/raw/zookeeper_full.log",
        "expected_min_bytes": 9_000_000,
    },
    {
        "name": "Spark",
        "key": "spark",
        "domain": "distributed_systems",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/data/spark.txt",
        "target_file": "data/loghub/distributed_systems/spark/raw/spark_full.log",
        "expected_min_bytes": 1_400_000_000,
    },
    {
        "name": "OpenStack",
        "key": "openstack",
        "domain": "distributed_systems",
        "type": "existing",
        "source_candidates": ["data/samples/OpenStack.log", "data/loghub/distributed_systems/openstack/raw/openstack_full.log"],
        "target_file": "data/loghub/distributed_systems/openstack/raw/openstack_full.log",
        "expected_min_bytes": 50_000_000,
    },

    # Operating Systems
    {
        "name": "Linux",
        "key": "linux",
        "domain": "operating_systems",
        "type": "existing",
        "source_candidates": ["data/samples/Linux.log", "data/loghub/operating_systems/linux/raw/linux_full.log"],
        "target_file": "data/loghub/operating_systems/linux/raw/linux_full.log",
        "expected_min_bytes": 2_000_000,
    },
    {
        "name": "Mac",
        "key": "mac",
        "domain": "operating_systems",
        "type": "existing",
        "source_candidates": ["data/loghub/operating_systems/mac/raw/mac_full.log", "data/samples/mac_full.log"],
        "fallback_url": f"{HF_BOLU_BASE}/data/mac.txt",
        "target_file": "data/loghub/operating_systems/mac/raw/mac_full.log",
        "expected_min_bytes": 14_000_000,
    },

    # Mobile Systems
    {
        "name": "HealthApp",
        "key": "healthapp",
        "domain": "mobile_systems",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/data/healthapp.txt",
        "target_file": "data/loghub/mobile_systems/healthapp/raw/healthapp_full.log",
        "expected_min_bytes": 18_000_000,
    },

    # Server Applications
    {
        "name": "Apache",
        "key": "apache",
        "domain": "server_applications",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/data/apache.txt",
        "target_file": "data/loghub/server_applications/apache/raw/apache_full.log",
        "expected_min_bytes": 4_500_000,
    },
    {
        "name": "OpenSSH",
        "key": "openssh",
        "domain": "server_applications",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/data/openssh.txt",
        "target_file": "data/loghub/server_applications/openssh/raw/openssh_full.log",
        "expected_min_bytes": 65_000_000,
    },
    {
        "name": "Proxifier",
        "key": "proxifier",
        "domain": "server_applications",
        "type": "direct",
        "url": f"{HF_BOLU_BASE}/data/proxifier.txt",
        "target_file": "data/loghub/server_applications/proxifier/raw/proxifier_full.log",
        "expected_min_bytes": 2_300_000,
    },
]


def download_stream(url: str, dest_path: str, chunk_size: int = 1024 * 1024) -> bool:
    """Streams download directly to a temporary file, then renames to dest_path."""
    temp_path = dest_path + ".part"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as response, open(temp_path, "wb") as f_out:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f_out.write(chunk)

        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            os.replace(temp_path, dest_path)
            return True
    except Exception as e:
        print(f"  [ERROR] Failed to download {url}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
    return False


def process_dataset_entry(item: Dict) -> Dict:
    name = item["name"]
    target = os.path.abspath(item["target_file"])
    min_bytes = item.get("expected_min_bytes", 1000)

    # 1. Check if already present and valid size (Prevent Duplicate Downloads)
    if os.path.exists(target) and os.path.getsize(target) >= min_bytes:
        sz_mb = os.path.getsize(target) / (1024 * 1024)
        print(f"[ALREADY EXISTS] {name:20s} -> {target} ({sz_mb:.2f} MB)")
        return {"name": name, "status": "exists", "path": target, "size": os.path.getsize(target)}

    os.makedirs(os.path.dirname(target), exist_ok=True)

    # 2. Handle 'existing' type (already present locally)
    if item["type"] == "existing":
        for cand in item.get("source_candidates", []):
            if os.path.exists(cand) and os.path.getsize(cand) >= min_bytes:
                if os.path.abspath(cand) != target:
                    shutil.copy2(cand, target)
                sz_mb = os.path.getsize(target) / (1024 * 1024)
                print(f"[VERIFIED]       {name:20s} -> {target} ({sz_mb:.2f} MB)")
                return {"name": name, "status": "verified", "path": target, "size": os.path.getsize(target)}

        # If fallback url exists
        if "fallback_url" in item:
            print(f"[DOWNLOADING]    {name:20s} from remote fallback...")
            if download_stream(item["fallback_url"], target):
                sz_mb = os.path.getsize(target) / (1024 * 1024)
                print(f"[DOWNLOADED]     {name:20s} -> {target} ({sz_mb:.2f} MB)")
                return {"name": name, "status": "downloaded", "path": target, "size": os.path.getsize(target)}

    # 3. Handle 'direct' download
    if item["type"] == "direct":
        url = item["url"]
        print(f"[DOWNLOADING]    {name:20s} from {url}...")
        success = download_stream(url, target)
        if success:
            sz_mb = os.path.getsize(target) / (1024 * 1024)
            print(f"[DOWNLOADED]     {name:20s} -> {target} ({sz_mb:.2f} MB)")
            return {"name": name, "status": "downloaded", "path": target, "size": os.path.getsize(target)}
        else:
            return {"name": name, "status": "failed", "path": target, "size": 0}

    # 4. Handle 'zip' extraction (e.g. BGL.zip, HDFS_v1.zip)
    if item["type"] == "zip":
        url = item["url"]
        inner_filename = item["inner_file"]
        temp_zip = target + ".zip"

        print(f"[DOWNLOADING ZIP]{name:20s} from {url}...")
        if download_stream(url, temp_zip):
            print(f"[EXTRACTING]     {name:20s} inner file '{inner_filename}'...")
            try:
                with zipfile.ZipFile(temp_zip, "r") as z:
                    # Find inner file matching name (case-insensitive)
                    matched = None
                    for member in z.namelist():
                        if os.path.basename(member).lower() == inner_filename.lower():
                            matched = member
                            break
                    if matched:
                        with z.open(matched) as z_in, open(target, "wb") as f_out:
                            shutil.copyfileobj(z_in, f_out)
                        print(f"[EXTRACTED]      {name:20s} -> {target}")
                    else:
                        print(f"[ERROR] Inner file '{inner_filename}' not found in {temp_zip}")
            except Exception as e:
                print(f"[ERROR] Failed to extract {temp_zip}: {e}")
            finally:
                # Clean up zip archive so no duplicate/extraneous archive is left
                if os.path.exists(temp_zip):
                    try:
                        os.remove(temp_zip)
                    except OSError:
                        pass

            if os.path.exists(target) and os.path.getsize(target) >= min_bytes:
                sz_mb = os.path.getsize(target) / (1024 * 1024)
                print(f"[COMPLETE]       {name:20s} -> {target} ({sz_mb:.2f} MB)")
                return {"name": name, "status": "extracted", "path": target, "size": os.path.getsize(target)}

    return {"name": name, "status": "failed", "path": target, "size": 0}


def download_all_entire_datasets(max_workers: int = 4):
    print("=" * 80)
    print("  AETHER OBSERVABILITY: DOWNLOAD ENTIRE PRODUCTION LOG DATASETS")
    print("=" * 80)
    print(f"Parallel Workers : {max_workers}")
    print(f"Total Entire Sets: {len(ENTIRE_DATASETS)}")
    print("-" * 80)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_dataset_entry, item) for item in ENTIRE_DATASETS]
        for f in concurrent.futures.as_completed(futures):
            try:
                res = f.result()
                results.append(res)
            except Exception as e:
                print(f"[THREAD ERROR] {e}")

    print("=" * 80)
    print("  ENTIRE LOGHUB PRODUCTION DATASETS: DOWNLOAD SUMMARY")
    print("=" * 80)
    total_bytes = 0
    for r in sorted(results, key=lambda x: x["name"]):
        sz_mb = r["size"] / (1024 * 1024)
        total_bytes += r["size"]
        print(f"  {r['name']:22s} | Status: {r['status']:10s} | Size: {sz_mb:8.2f} MB | {r['path']}")

    print("-" * 80)
    print(f"  TOTAL ENTIRE DATA: {total_bytes / (1024 * 1024 * 1024):.2f} GB ({total_bytes:,} bytes)")
    print("=" * 80)
    return results


if __name__ == "__main__":
    download_all_entire_datasets(max_workers=4)
