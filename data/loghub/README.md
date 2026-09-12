# LogHub Benchmark Suite: Master Dataset Catalog & Taxonomy

This directory contains the complete, systematically organized collection of **16 production system log datasets** from [logpai/loghub](https://github.com/logpai/loghub) (ISSRE'23) and corrected template benchmarks from [logpai/loghub-2.0](https://github.com/logpai/loghub-2.0).

All datasets are structured with zero ambiguity:
- **Clean domain categorization** (Distributed Systems, Supercomputers, Operating Systems, Mobile Systems, Server Applications)
- **Separation of Raw vs Ground Truth** (`raw/` vs `ground_truth/`)
- **Integration of both standard 2k slices and full large-scale datasets** (e.g. OpenStack 207k lines, Mac 117k lines, Linux 25.5k lines, HDFS 100k lines)
- **Programmatic Python API** (`from backend.data.dataset_registry import DatasetRegistry`)

---

## Master Dataset Matrix

| System | Domain | Log Format / System Description | 2k Slice | Full Production Log | Ground Truth Structured | Ground Truth Templates | Anomaly Ground Truth |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **HDFS** | Distributed Systems | Hadoop Distributed File System (Block generation, replication, termination) | :white_check_mark: | :white_check_mark: **1,504.88 MB** (11.2M lines) | :white_check_mark: | :white_check_mark: | :white_check_mark: (`anomaly_label.csv` 17.2 MB) |
| **Hadoop** | Distributed Systems | MapReduce cluster task execution, job history & shuffle logs | :white_check_mark: | :white_check_mark: **30.41 MB** (394k lines) | :white_check_mark: | :white_check_mark: | — |
| **Spark** | Distributed Systems | Apache Spark distributed in-memory compute framework & worker logs | :white_check_mark: | :white_check_mark: **1,553.87 MB** (33.2M lines) | :white_check_mark: | :white_check_mark: | — |
| **Zookeeper**| Distributed Systems | Apache ZooKeeper leader election, quorum consensus & client state | :white_check_mark: | :white_check_mark: **9.85 MB** (74.3k lines) | :white_check_mark: | :white_check_mark: | — |
| **OpenStack**| Distributed Systems | Cloud Infrastructure (Nova compute, Keystone auth, Neutron net) | :white_check_mark: | :white_check_mark: **58.79 MB** (207.8k lines) | :white_check_mark: | :white_check_mark: | :white_check_mark: (`anomaly_labels.txt`) |
| **BGL** | Supercomputers | BlueGene/L Supercomputer hardware alerts, parity errors & core dumps | :white_check_mark: | :white_check_mark: **708.76 MB** (4.7M lines) | :white_check_mark: | :white_check_mark: | :white_check_mark: (First column tag) |
| **HPC** | Supercomputers | High Performance Computing Linux cluster SLURM / PBS job logs | :white_check_mark: | :white_check_mark: **31.10 MB** (433k lines) | :white_check_mark: | :white_check_mark: | — |
| **Thunderbird**| Supercomputers| Thunderbird Supercomputer hardware events & memory parity alerts | :white_check_mark: | :white_check_mark: **845.25 MB** | :white_check_mark: | :white_check_mark: | :white_check_mark: (First column tag) |
| **Linux** | Operating Systems | Linux OS syslog, auth.log, PAM sessions, SSH login attempts | :white_check_mark: | :white_check_mark: **2.27 MB** (25.5k lines) | :white_check_mark: | :white_check_mark: | — |
| **Mac** | Operating Systems | Apple macOS subsystem daemon logs, sandbox alerts & crash reporter | :white_check_mark: | :white_check_mark: **16.10 MB** (117.2k lines) | :white_check_mark: | :white_check_mark: | — |
| **Windows** | Operating Systems | Windows Event Logs (System & Security event streams) | :white_check_mark: | — (2k slice) | :white_check_mark: | :white_check_mark: | — |
| **Android** | Mobile Systems | Android OS framework, ActivityManager, window manager logs | :white_check_mark: | — (2k slice) | :white_check_mark: | :white_check_mark: | — |
| **HealthApp**| Mobile Systems | Android health application step tracking, sync routines & GPS events | :white_check_mark: | :white_check_mark: **19.53 MB** (253k lines) | :white_check_mark: | :white_check_mark: | — |
| **Apache** | Server Apps | Apache HTTP Web Server error logs, rewrite notices & HTTP codes | :white_check_mark: | :white_check_mark: **4.75 MB** (56.4k lines) | :white_check_mark: | :white_check_mark: | — |
| **OpenSSH** | Server Apps | OpenSSH daemon remote authentication handshakes & terminations | :white_check_mark: | :white_check_mark: **67.27 MB** (655k lines) | :white_check_mark: | :white_check_mark: | — |
| **Proxifier**| Server Apps | Network tunneling proxy traffic, SOCKS5/HTTPS routing & DNS | :white_check_mark: | :white_check_mark: **2.40 MB** (21.3k lines) | :white_check_mark: | :white_check_mark: | — |

---

## Directory Organization & File Conventions

Every dataset folder follows the exact same predictable layout:

```
data/loghub/<domain>/<system_name>/
├── raw/
│   ├── <system_name>_2k.log                  # Standard 2,000-line authentic raw log slice
│   └── <system_name>_full.log                # Full production log (when available)
├── ground_truth/
│   ├── <system_name>_2k.log_structured.csv   # Parsed columns: LineId, Time, Level, Content, EventTemplate
│   ├── <system_name>_2k.log_templates.csv    # Mined templates: EventId, EventTemplate, Occurrences
│   ├── <system_name>_2k.log_structured_corrected.csv # ISSRE'23 LogHub-2.0 corrected parsed logs
│   ├── <system_name>_2k.log_templates_corrected.csv  # ISSRE'23 LogHub-2.0 corrected templates
│   └── [anomaly_label.csv / anomaly_labels.txt]      # Domain anomaly labels (HDFS, OpenStack, etc.)
└── README.md                                 # Upstream LogHub system documentation & log dialect specification
```

---

## Python Programmatic Access (Quickstart)

Never hardcode file paths! Use the built-in `DatasetRegistry`:

```python
from backend.data.dataset_registry import DatasetRegistry

# 1. Inspect available datasets
print(DatasetRegistry.list_domains())
# Output: ['distributed_systems', 'mobile_systems', 'operating_systems', 'server_applications', 'supercomputers']

print(DatasetRegistry.list_datasets(domain="distributed_systems"))
# Output: ['hdfs', 'hadoop', 'spark', 'zookeeper', 'openstack']

# 2. Access a specific dataset
hdfs = DatasetRegistry.get("hdfs")

# Read raw log lines
sample_lines = hdfs.read_raw(max_lines=50)
print(f"Loaded {len(sample_lines)} lines from {hdfs.name}")

# Read ground-truth parsed DataFrame
df_structured = hdfs.read_structured()
print("Columns:", df_structured.columns.tolist())
# Columns: ['LineId', 'Date', 'Time', 'Pid', 'Level', 'Component', 'Content', 'EventId', 'EventTemplate']

# Read ground-truth templates
df_templates = hdfs.read_templates()
print(f"Extracted {len(df_templates)} unique templates")

# Access full production dataset (if available)
if hdfs.raw_full_path:
    full_lines = hdfs.read_raw(use_full=True, max_lines=1000)
```

---

## Automated Refresh & Parallel Downloader

To verify or refresh all 16 datasets with high-concurrency multithreading:

```bash
python scripts/download_datasets.py --all --workers 8
```

Or run the parallel script directly:
```bash
python scripts/download_loghub_parallel.py
```
