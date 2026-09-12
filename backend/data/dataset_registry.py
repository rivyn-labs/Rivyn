"""
LogHub Dataset Registry & Programmatic Accessor.

Provides unified, type-safe access to the datasets loaded in data/samples:
- Linux (Linux.log, 25,567 lines)
- OpenStack (OpenStack.log, 207,820 lines)
- HDFS (HDFS.log, 11,175,629 lines / 1.58 GB)
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_SAMPLES_DIR = os.path.join(BASE_DIR, "data", "samples")


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

    @property
    def raw_path(self) -> str:
        return self.raw_2k_path

    def read_raw(self, max_lines: Optional[int] = None, use_full: bool = False) -> List[str]:
        """Read raw log lines from the dataset."""
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
        """Read ground truth structured log CSV."""
        target = None
        if use_corrected and self.corrected_structured_csv_path and os.path.exists(self.corrected_structured_csv_path):
            target = self.corrected_structured_csv_path
        elif self.structured_csv_path and os.path.exists(self.structured_csv_path):
            target = self.structured_csv_path

        if not target or not os.path.exists(target):
            return pd.DataFrame(columns=["LineId", "Time", "Level", "Content", "EventTemplate"])

        return pd.read_csv(target)

    def read_templates(self, use_corrected: bool = True) -> pd.DataFrame:
        """Read ground truth event templates CSV."""
        target = None
        if use_corrected and self.corrected_templates_csv_path and os.path.exists(self.corrected_templates_csv_path):
            target = self.corrected_templates_csv_path
        elif self.templates_csv_path and os.path.exists(self.templates_csv_path):
            target = self.templates_csv_path

        if not target or not os.path.exists(target):
            return pd.DataFrame(columns=["EventId", "EventTemplate"])

        return pd.read_csv(target)


class DatasetRegistry:
    _DATASETS = {
        "linux": {
            "name": "Linux",
            "domain": "operating_systems",
            "description": "Linux operating system syslog, auth, PAM, and sshd security logs",
            "file": "Linux.log",
        },
        "openstack": {
            "name": "OpenStack",
            "domain": "distributed_systems",
            "description": "OpenStack cloud infrastructure Nova, Keystone, Neutron service logs",
            "file": "OpenStack.log",
        },
        "hdfs": {
            "name": "HDFS",
            "domain": "distributed_systems",
            "description": "Hadoop Distributed File System block replication and termination logs",
            "file": "HDFS.log",
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
        samples_dir = base_dir or BASE_SAMPLES_DIR
        raw_file = os.path.join(samples_dir, info["file"])
        readme_file = os.path.join(samples_dir, "README.md")

        return DatasetEntry(
            key=key,
            name=info["name"],
            domain=info["domain"],
            description=info["description"],
            system_dir=samples_dir,
            raw_2k_path=raw_file,
            raw_full_path=raw_file,
            structured_csv_path=None,
            templates_csv_path=None,
            corrected_structured_csv_path=None,
            corrected_templates_csv_path=None,
            anomaly_labels_path=None,
            readme_path=readme_file if os.path.exists(readme_file) else raw_file,
        )
