"""
AETHER LogHub Parallel Downloader & Systematic Organizer.

Downloads and organizes all 16 system log datasets from:
https://github.com/logpai/loghub (ISSRE'23 benchmark suite)
and https://github.com/logpai/loghub-2.0 (corrected labels).

Organizes datasets into clean domain categories:
  - distributed_systems (HDFS, Hadoop, Spark, ZooKeeper, OpenStack)
  - supercomputers      (BGL, HPC, Thunderbird)
  - operating_systems   (Linux, Mac, Windows)
  - mobile_systems      (Android, HealthApp)
  - server_applications (Apache, OpenSSH, Proxifier)

Each dataset folder contains:
  - raw/          (clean raw .log files: 2k benchmark slice and full production logs)
  - ground_truth/ (structured parsed CSVs, template definitions, corrected templates, anomaly labels)
  - README.md     (system architecture, format documentation, and upstream citations)
"""

import os
import sys
import json
import shutil
import urllib.request
import concurrent.futures
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

# Ensure standard output can print Unicode cleanly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LOGHUB_RAW_BASE = "https://raw.githubusercontent.com/logpai/loghub/master"
LOGHUB2_RAW_BASE = "https://raw.githubusercontent.com/logpai/loghub-2.0/master/2k_dataset"
LOGLIZER_RAW_BASE = "https://raw.githubusercontent.com/logpai/loglizer/master/data/HDFS"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass
class DatasetDefinition:
    key: str
    name: str
    domain: str
    github_folder: str
    description: str
    has_corrected: bool = True
    extra_templates: Optional[str] = None
    has_anomaly_labels: bool = False
    full_log_source: Optional[str] = None


DATASET_REGISTRY: List[DatasetDefinition] = [
    # Distributed Systems
    DatasetDefinition(
        key="hdfs",
        name="HDFS",
        domain="distributed_systems",
        github_folder="HDFS",
        description="Hadoop Distributed File System block replication and termination logs",
        extra_templates="HDFS_templates.csv",
        has_anomaly_labels=True,
        full_log_source="data/samples_expanded/hdfs_100k.log",
    ),
    DatasetDefinition(
        key="hadoop",
        name="Hadoop",
        domain="distributed_systems",
        github_folder="Hadoop",
        description="Hadoop MapReduce cluster task execution and job history logs",
    ),
    DatasetDefinition(
        key="spark",
        name="Spark",
        domain="distributed_systems",
        github_folder="Spark",
        description="Apache Spark distributed in-memory data processing framework logs",
    ),
    DatasetDefinition(
        key="zookeeper",
        name="Zookeeper",
        domain="distributed_systems",
        github_folder="Zookeeper",
        description="Apache ZooKeeper coordination service leader election and follower sync logs",
    ),
    DatasetDefinition(
        key="openstack",
        name="OpenStack",
        domain="distributed_systems",
        github_folder="OpenStack",
        description="OpenStack cloud infrastructure Nova, Keystone, Neutron service logs",
        has_anomaly_labels=True,
        full_log_source="data/samples/OpenStack.log",
    ),

    # Supercomputers
    DatasetDefinition(
        key="bgl",
        name="BGL",
        domain="supercomputers",
        github_folder="BGL",
        description="BlueGene/L supercomputer hardware alerts, parity errors, and node failures",
        extra_templates="BGL_templates.csv",
        has_anomaly_labels=True,  # In first column tag ('-' vs alert)
    ),
    DatasetDefinition(
        key="hpc",
        name="HPC",
        domain="supercomputers",
        github_folder="HPC",
        description="High Performance Computing Linux cluster job scheduling and node logs",
    ),
    DatasetDefinition(
        key="thunderbird",
        name="Thunderbird",
        domain="supercomputers",
        github_folder="Thunderbird",
        description="Thunderbird supercomputer system logs with alert and failure categorizations",
        has_anomaly_labels=True,  # In first column tag
    ),

    # Operating Systems
    DatasetDefinition(
        key="linux",
        name="Linux",
        domain="operating_systems",
        github_folder="Linux",
        description="Linux operating system syslog, auth, PAM, and sshd security logs",
        full_log_source="data/samples/Linux.log",
    ),
    DatasetDefinition(
        key="mac",
        name="Mac",
        domain="operating_systems",
        github_folder="Mac",
        description="Apple macOS operating system subsystem and application crash logs",
        full_log_source="temp_loghub2/2k_dataset/Mac/Mac.log",
    ),
    DatasetDefinition(
        key="windows",
        name="Windows",
        domain="operating_systems",
        github_folder="Windows",
        description="Microsoft Windows system and security event log entries",
    ),

    # Mobile Systems
    DatasetDefinition(
        key="android",
        name="Android",
        domain="mobile_systems",
        github_folder="Android",
        description="Android mobile framework ActivityManager and system server logs",
    ),
    DatasetDefinition(
        key="healthapp",
        name="HealthApp",
        domain="mobile_systems",
        github_folder="HealthApp",
        description="Mobile health application step counting, sensor sync, and GPS logs",
    ),

    # Server Applications & Network
    DatasetDefinition(
        key="apache",
        name="Apache",
        domain="server_applications",
        github_folder="Apache",
        description="Apache HTTP web server access errors, rewrite engine, and notice logs",
    ),
    DatasetDefinition(
        key="openssh",
        name="OpenSSH",
        domain="server_applications",
        github_folder="OpenSSH",
        description="OpenSSH daemon remote authentication attempts, handshakes, and terminations",
    ),
    DatasetDefinition(
        key="proxifier",
        name="Proxifier",
        domain="server_applications",
        github_folder="Proxifier",
        description="Proxifier network client TCP/UDP routing, proxy tunnel, and DNS logs",
    ),
]


def download_url_to_file(url: str, target_path: str, max_retries: int = 3) -> bool:
    """Download a remote URL to target_path with retry and browser User-Agent."""
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        return True

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    temp_target = target_path + ".download"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as response, open(temp_target, "wb") as out_file:
                shutil.copyfileobj(response, out_file)

            if os.path.exists(temp_target) and os.path.getsize(temp_target) > 0:
                os.replace(temp_target, target_path)
                return True
        except Exception as e:
            if attempt == max_retries:
                # print error on final attempt
                # If 404, file might not exist upstream
                pass
            if os.path.exists(temp_target):
                try:
                    os.remove(temp_target)
                except OSError:
                    pass

    return False


def copy_or_download(source_local: Optional[str], fallback_url: str, dest_path: str) -> bool:
    """Copies from local if present and valid; otherwise downloads from remote fallback URL."""
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return True

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    if source_local and os.path.exists(source_local) and os.path.getsize(source_local) > 0:
        try:
            shutil.copy2(source_local, dest_path)
            return True
        except Exception:
            pass

    return download_url_to_file(fallback_url, dest_path)


def process_dataset(ds: DatasetDefinition, base_data_dir: str = "data/loghub") -> Dict:
    """Download and organize all files for a single dataset definition."""
    system_dir = os.path.join(base_data_dir, ds.domain, ds.key)
    raw_dir = os.path.join(system_dir, "raw")
    gt_dir = os.path.join(system_dir, "ground_truth")

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(gt_dir, exist_ok=True)

    folder = ds.github_folder
    key = ds.key

    tasks = []

    # 1. Raw 2k log
    raw_2k_name = f"{folder}_2k.log"
    local_src_1 = f"temp_loghub/{folder}/{raw_2k_name}"
    local_src_2 = f"temp_loghub2/2k_dataset/{folder}/{raw_2k_name}"
    local_src = local_src_1 if os.path.exists(local_src_1) else local_src_2
    dest_raw_2k = os.path.join(raw_dir, f"{key}_2k.log")
    url_raw_2k = f"{LOGHUB_RAW_BASE}/{folder}/{raw_2k_name}"
    tasks.append(("raw_2k", local_src, url_raw_2k, dest_raw_2k))

    # 2. Structured 2k CSV
    struct_name = f"{folder}_2k.log_structured.csv"
    dest_struct = os.path.join(gt_dir, f"{key}_2k.log_structured.csv")
    tasks.append(("structured_2k", f"temp_loghub/{folder}/{struct_name}", f"{LOGHUB_RAW_BASE}/{folder}/{struct_name}", dest_struct))

    # 3. Templates 2k CSV
    templates_name = f"{folder}_2k.log_templates.csv"
    dest_templates = os.path.join(gt_dir, f"{key}_2k.log_templates.csv")
    tasks.append(("templates_2k", f"temp_loghub/{folder}/{templates_name}", f"{LOGHUB_RAW_BASE}/{folder}/{templates_name}", dest_templates))

    # 4. Corrected Structured & Templates (LogHub 2.0 / ISSRE'23)
    if ds.has_corrected:
        corr_struct = f"{folder}_2k.log_structured_corrected.csv"
        dest_corr_struct = os.path.join(gt_dir, f"{key}_2k.log_structured_corrected.csv")
        tasks.append(("corrected_structured", f"temp_loghub2/2k_dataset/{folder}/{corr_struct}", f"{LOGHUB2_RAW_BASE}/{folder}/{corr_struct}", dest_corr_struct))

        corr_tmpl = f"{folder}_2k.log_templates_corrected.csv"
        dest_corr_tmpl = os.path.join(gt_dir, f"{key}_2k.log_templates_corrected.csv")
        tasks.append(("corrected_templates", f"temp_loghub2/2k_dataset/{folder}/{corr_tmpl}", f"{LOGHUB2_RAW_BASE}/{folder}/{corr_tmpl}", dest_corr_tmpl))

    # 5. Extra domain templates (e.g. HDFS_templates.csv, BGL_templates.csv)
    if ds.extra_templates:
        dest_extra = os.path.join(gt_dir, ds.extra_templates.lower())
        tasks.append(("extra_templates", f"temp_loghub/{folder}/{ds.extra_templates}", f"{LOGHUB_RAW_BASE}/{folder}/{ds.extra_templates}", dest_extra))

    # 6. Readme
    dest_readme = os.path.join(system_dir, "README.md")
    tasks.append(("readme", f"temp_loghub/{folder}/README.md", f"{LOGHUB_RAW_BASE}/{folder}/README.md", dest_readme))

    # 7. Anomaly labels if special
    if ds.key == "hdfs":
        dest_lbl = os.path.join(gt_dir, "anomaly_label.csv")
        url_lbl = f"{LOGLIZER_RAW_BASE}/anomaly_label.csv"
        tasks.append(("anomaly_labels", None, url_lbl, dest_lbl))

    if ds.key == "openstack":
        dest_lbl = os.path.join(gt_dir, "anomaly_labels.txt")
        tasks.append(("anomaly_labels", "data/samples/anomaly_labels.txt", "", dest_lbl))

    # Run copy/downloads
    results = {}
    for task_name, local_path, remote_url, dest in tasks:
        success = copy_or_download(local_path, remote_url, dest)
        results[task_name] = {
            "path": os.path.relpath(dest, base_data_dir).replace("\\", "/"),
            "size": os.path.getsize(dest) if (os.path.exists(dest) and success) else 0,
            "success": success
        }

    # 8. Full production log integration if available
    full_raw_dest = os.path.join(raw_dir, f"{key}_full.log")
    if ds.full_log_source and os.path.exists(ds.full_log_source):
        if not os.path.exists(full_raw_dest) or os.path.getsize(full_raw_dest) != os.path.getsize(ds.full_log_source):
            try:
                shutil.copy2(ds.full_log_source, full_raw_dest)
            except Exception:
                pass
        if os.path.exists(full_raw_dest):
            results["raw_full"] = {
                "path": os.path.relpath(full_raw_dest, base_data_dir).replace("\\", "/"),
                "size": os.path.getsize(full_raw_dest),
                "success": True
            }

    # If dataset is HDFS, ensure hdfs_100k.log is cataloged
    hdfs_100k = os.path.join(raw_dir, "hdfs_100k.log")
    if os.path.exists(hdfs_100k):
        results["raw_100k"] = {
            "path": os.path.relpath(hdfs_100k, base_data_dir).replace("\\", "/"),
            "size": os.path.getsize(hdfs_100k),
            "success": True
        }

    # 9. Also populate backward-compatible data/samples/ files
    samples_dir = "data/samples"
    os.makedirs(samples_dir, exist_ok=True)
    compat_sample = os.path.join(samples_dir, f"{key}_sample.log")
    if os.path.exists(dest_raw_2k) and not os.path.exists(compat_sample):
        try:
            shutil.copy2(dest_raw_2k, compat_sample)
        except Exception:
            pass

    return {
        "key": ds.key,
        "name": ds.name,
        "domain": ds.domain,
        "description": ds.description,
        "files": results
    }


def download_all_parallel(max_workers: int = 8, base_data_dir: str = "data/loghub"):
    """Concurrently process and download all registered LogHub datasets."""
    print("=" * 75)
    print("  AETHER OBSERVABILITY: PARALLEL LOGHUB DATASET DOWNLOADER")
    print("=" * 75)
    print(f"Target directory: {os.path.abspath(base_data_dir)}")
    print(f"Total datasets  : {len(DATASET_REGISTRY)} systems across 5 domains")
    print(f"Parallel workers: {max_workers}")
    print("-" * 75)

    catalog = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ds = {
            executor.submit(process_dataset, ds, base_data_dir): ds
            for ds in DATASET_REGISTRY
        }

        for future in concurrent.futures.as_completed(future_to_ds):
            ds = future_to_ds[future]
            try:
                res = future.result()
                catalog[ds.key] = res
                total_files = len([f for f in res["files"].values() if f["success"]])
                total_bytes = sum(f["size"] for f in res["files"].values() if f["success"])
                size_mb = total_bytes / (1024 * 1024)
                print(f"[OK] {ds.name:12s} ({ds.domain:20s}) -> {total_files} files, {size_mb:6.2f} MB")
            except Exception as exc:
                print(f"[ERROR] {ds.name} generated exception: {exc}")

    # Write master machine-readable catalog.json
    catalog_path = os.path.join(base_data_dir, "catalog.json")
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    print("-" * 75)
    print(f"Successfully generated catalog: {catalog_path}")
    return catalog


import stat

def cleanup_temp_directories():
    """Removes temporary clone caches to keep repo tidy."""
    def remove_readonly(func, path, excinfo):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    for temp_dir in ["temp_loghub", "temp_loghub2"]:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, onerror=remove_readonly)
                print(f"Cleaned up temporary cache: {temp_dir}")
            except Exception as e:
                print(f"Note: could not remove {temp_dir}: {e}")


if __name__ == "__main__":
    download_all_parallel(max_workers=8)
    cleanup_temp_directories()
