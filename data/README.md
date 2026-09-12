# LogHub Benchmark Datasets

This directory contains real-world system logs from the [logpai/loghub](https://github.com/logpai/loghub) benchmark collection, maintained by the Chinese University of Hong Kong (CUHK) and freely accessible for AI-driven log analytics research.

## Datasets Overview

| Dataset | System Type | Characteristics | Key Entities | Labeled |
| :--- | :--- | :--- | :--- | :---: |
| **HDFS** | Distributed File System | Block generation, replication, termination | `blk_<id>`, IP addresses | Yes |
| **BGL** | BlueGene/L Supercomputer | Hardware alerts, core dumps, I/O errors | Component node IDs, severity | Yes |
| **Linux** | Operating System | SSH authentication failures, PAM errors | IP addresses, user names, ports | No |
| **OpenStack**| Cloud Infrastructure | VM lifecycle, Nova/Neutron/Keystone events | Request IDs (`req-...`), Tenant IDs | Yes |

## MHP Hackathon Compliance Notice

> **Log Sanitization & Isolation Notice**:
> LogHub notes that raw production logs may contain unsanitized IP addresses or internal hostnames. In compliance with the MHP Hackathon Governance requirements, all logs ingested into this platform pass through our automated **DataGovernor Redaction Engine** (`backend/normalization/redactor.py`) before feature extraction or AI reasoning.

## Fetching Additional Datasets

To re-download or refresh the 2,000-line sample datasets:
```bash
python scripts/download_datasets.py
```
To load external logs, place any `.log` or `.txt` file into `data/` or use the web dashboard's drag-and-drop file uploader.
