# AETHER Log Data Repository

This directory contains benchmark and production system logs organized for the AETHER Observability Platform.

---

## Directory Organization

```
data/
├── loghub/              # Complete, systematically categorized collection of all 16 LogHub datasets
│   ├── README.md        # Master catalog matrix, taxonomy, schema documentation, and API usage
│   ├── catalog.json     # Machine-readable metadata and verification records
│   ├── distributed_systems/  (HDFS, Hadoop, Spark, ZooKeeper, OpenStack)
│   ├── supercomputers/       (BGL, HPC, Thunderbird)
│   ├── operating_systems/    (Linux, Mac, Windows)
│   ├── mobile_systems/       (Android, HealthApp)
│   └── server_applications/  (Apache, OpenSSH, Proxifier)
│
├── samples/             # Fast-bootstrapping slices used by unit tests and quick demo runs
│   ├── hdfs_sample.log
│   ├── bgl_sample.log
│   ├── linux_sample.log
│   ├── openstack_sample.log
│   ├── Linux.log        # Full Linux syslog (25,567 lines)
│   ├── OpenStack.log    # Full OpenStack infrastructure log (207,820 lines)
│   └── anomaly_labels.txt
│
├── samples_expanded/    # Scaled realistic workloads (25,000+ to 100,000+ lines)
│   └── hdfs_100k.log
│
└── binary/              # Optimized zero-copy Apache Parquet columnar binary caches
    ├── hdfs.parquet
    ├── linux_full.parquet
    └── openstack_full.parquet
```

---

## Working with Datasets in Python

Use the `DatasetRegistry` module for unified, programmatic access:

```python
from backend.data.dataset_registry import DatasetRegistry

# Load any of the 16 datasets with ease:
bgl = DatasetRegistry.get("bgl")
raw_lines = bgl.read_raw(max_lines=200)
ground_truth_df = bgl.read_structured()
```

---

## Refreshing or Downloading Datasets

To download and organize all 16 datasets concurrently:
```bash
python scripts/download_datasets.py --all --workers 8
```

For quick local bootstrapping of the 4 primary hackathon demo files:
```bash
python scripts/download_datasets.py --quick
```

---

## MHP Hackathon Compliance Notice

> **Log Sanitization & Isolation**:
> Production logs may contain unsanitized IP addresses or internal hostnames. All logs ingested into AETHER pass through our automated **DataGovernor Redaction Engine** (`backend/normalization/redactor.py`) before feature extraction or AI reasoning.
