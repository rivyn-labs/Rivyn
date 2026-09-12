"""
LogHub Dataset Registry & Programmatic Accessor.

Provides unified, type-safe access to all 16 LogHub system log datasets
organized under `data/loghub/`.

Usage:
    from backend.data.dataset_registry import DatasetRegistry

    # List all datasets
    print(DatasetRegistry.list_datasets())

    # Get specific dataset entry
    ds = DatasetRegistry.get("hdfs")
    print(ds.name, ds.domain, ds.raw_2k_path)

    # Read raw logs
    raw_lines = ds.read_raw(max_lines=100)

    # Read ground-truth parsed DataFrame
    df_structured = ds.read_structured()

    # Read ground-truth templates
    df_templates = ds.read_templates()
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import pandas as pd


BASE_LOGHUB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "loghub")


@dataclass
class DatasetEntry:
    key: str
    name: str
    domain: str
    description: str
    system_dir: str
    raw_2k_path: str
    raw_full_path: Optional[str]
    structured_csv_path: Optional[str]
    templates_csv_path: Optional[str]
    corrected_structured_csv_path: Optional[str]
    corrected_templates_csv_path: Optional[str]
    anomaly_labels_path: Optional[str]
    readme_path: str

    def read_raw(self, max_lines: Optional[int] = None, use_full: bool = False) -> List[str]:
        """Read raw log lines from the 2k benchmark or full log file."""
        target_path = self.raw_full_path if (use_full and self.raw_full_path and os.path.exists(self.raw_full_path)) else self.raw_2k_path
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Raw log file not found at: {target_path}")

        lines = []
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if max_lines and i >= max_lines:
                    break
                lines.append(line.rstrip("\r\n"))
        return lines

    def read_structured(self, use_corrected: bool = True) -> pd.DataFrame:
        """Read ground truth structured log CSV (LineId, Time, Level, Content, EventTemplate)."""
        target = None
        if use_corrected and self.corrected_structured_csv_path and os.path.exists(self.corrected_structured_csv_path):
            target = self.corrected_structured_csv_path
        elif self.structured_csv_path and os.path.exists(self.structured_csv_path):
            target = self.structured_csv_path

        if not target or not os.path.exists(target):
            raise FileNotFoundError(f"Structured CSV not found for dataset '{self.key}'")

        return pd.read_csv(target)

    def read_templates(self, use_corrected: bool = True) -> pd.DataFrame:
        """Read ground truth event templates CSV."""
        target = None
        if use_corrected and self.corrected_templates_csv_path and os.path.exists(self.corrected_templates_csv_path):
            target = self.corrected_templates_csv_path
        elif self.templates_csv_path and os.path.exists(self.templates_csv_path):
            target = self.templates_csv_path

        if not target or not os.path.exists(target):
            raise FileNotFoundError(f"Templates CSV not found for dataset '{self.key}'")

        return pd.read_csv(target)


class DatasetRegistry:
    _DATASETS = {
        "hdfs": {
            "name": "HDFS",
            "domain": "distributed_systems",
            "description": "Hadoop Distributed File System block replication and termination logs",
            "has_full": True,
            "has_anomaly_labels": True,
        },
        "hadoop": {
            "name": "Hadoop",
            "domain": "distributed_systems",
            "description": "Hadoop MapReduce cluster task execution and job history logs",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "spark": {
            "name": "Spark",
            "domain": "distributed_systems",
            "description": "Apache Spark distributed in-memory data processing framework logs",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "zookeeper": {
            "name": "Zookeeper",
            "domain": "distributed_systems",
            "description": "Apache ZooKeeper coordination service leader election and follower sync logs",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "openstack": {
            "name": "OpenStack",
            "domain": "distributed_systems",
            "description": "OpenStack cloud infrastructure Nova, Keystone, Neutron service logs",
            "has_full": True,
            "has_anomaly_labels": True,
        },
        "bgl": {
            "name": "BGL",
            "domain": "supercomputers",
            "description": "BlueGene/L supercomputer hardware alerts, parity errors, and node failures",
            "has_full": False,
            "has_anomaly_labels": True,
        },
        "hpc": {
            "name": "HPC",
            "domain": "supercomputers",
            "description": "High Performance Computing Linux cluster job scheduling and node logs",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "thunderbird": {
            "name": "Thunderbird",
            "domain": "supercomputers",
            "description": "Thunderbird supercomputer system logs with alert and failure categorizations",
            "has_full": False,
            "has_anomaly_labels": True,
        },
        "linux": {
            "name": "Linux",
            "domain": "operating_systems",
            "description": "Linux operating system syslog, auth, PAM, and sshd security logs",
            "has_full": True,
            "has_anomaly_labels": False,
        },
        "mac": {
            "name": "Mac",
            "domain": "operating_systems",
            "description": "Apple macOS operating system subsystem and application crash logs",
            "has_full": True,
            "has_anomaly_labels": False,
        },
        "windows": {
            "name": "Windows",
            "domain": "operating_systems",
            "description": "Microsoft Windows system and security event log entries",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "android": {
            "name": "Android",
            "domain": "mobile_systems",
            "description": "Android mobile framework ActivityManager and system server logs",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "healthapp": {
            "name": "HealthApp",
            "domain": "mobile_systems",
            "description": "Mobile health application step counting, sensor sync, and GPS logs",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "apache": {
            "name": "Apache",
            "domain": "server_applications",
            "description": "Apache HTTP web server access errors, rewrite engine, and notice logs",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "openssh": {
            "name": "OpenSSH",
            "domain": "server_applications",
            "description": "OpenSSH daemon remote authentication attempts, handshakes, and terminations",
            "has_full": False,
            "has_anomaly_labels": False,
        },
        "proxifier": {
            "name": "Proxifier",
            "domain": "server_applications",
            "description": "Proxifier network client TCP/UDP routing, proxy tunnel, and DNS logs",
            "has_full": False,
            "has_anomaly_labels": False,
        },
    }

    @classmethod
    def list_datasets(cls, domain: Optional[str] = None) -> List[str]:
        """Returns list of dataset keys, optionally filtered by domain."""
        if domain:
            return [k for k, v in cls._DATASETS.items() if v["domain"] == domain]
        return list(cls._DATASETS.keys())

    @classmethod
    def list_domains(cls) -> List[str]:
        """Returns distinct system domains."""
        return sorted(list(set(v["domain"] for v in cls._DATASETS.values())))

    @classmethod
    def get(cls, name: str, base_dir: Optional[str] = None) -> DatasetEntry:
        """Fetch DatasetEntry for given dataset key (case-insensitive)."""
        key = name.lower().strip()
        if key not in cls._DATASETS:
            valid = ", ".join(cls._DATASETS.keys())
            raise KeyError(f"Unknown dataset '{name}'. Available: {valid}")

        info = cls._DATASETS[key]
        data_root = base_dir or BASE_LOGHUB_DIR

        sys_dir = os.path.join(data_root, info["domain"], key)
        raw_dir = os.path.join(sys_dir, "raw")
        gt_dir = os.path.join(sys_dir, "ground_truth")

        raw_2k = os.path.join(raw_dir, f"{key}_2k.log")

        # Check full raw path
        raw_full = None
        for candidate in [f"{key}_full.log", f"{key}_100k.log", f"{info['name']}.log"]:
            cand_path = os.path.join(raw_dir, candidate)
            if os.path.exists(cand_path):
                raw_full = cand_path
                break

        struct_csv = os.path.join(gt_dir, f"{key}_2k.log_structured.csv")
        tmpl_csv = os.path.join(gt_dir, f"{key}_2k.log_templates.csv")
        corr_struct = os.path.join(gt_dir, f"{key}_2k.log_structured_corrected.csv")
        corr_tmpl = os.path.join(gt_dir, f"{key}_2k.log_templates_corrected.csv")

        # Anomaly labels
        anom_path = None
        for candidate_anom in ["anomaly_label.csv", "anomaly_labels.txt"]:
            cand = os.path.join(gt_dir, candidate_anom)
            if os.path.exists(cand):
                anom_path = cand
                break

        readme_file = os.path.join(sys_dir, "README.md")

        return DatasetEntry(
            key=key,
            name=info["name"],
            domain=info["domain"],
            description=info["description"],
            system_dir=sys_dir,
            raw_2k_path=raw_2k,
            raw_full_path=raw_full if (raw_full and os.path.exists(raw_full)) else None,
            structured_csv_path=struct_csv if os.path.exists(struct_csv) else None,
            templates_csv_path=tmpl_csv if os.path.exists(tmpl_csv) else None,
            corrected_structured_csv_path=corr_struct if os.path.exists(corr_struct) else None,
            corrected_templates_csv_path=corr_tmpl if os.path.exists(corr_tmpl) else None,
            anomaly_labels_path=anom_path,
            readme_path=readme_file,
        )
