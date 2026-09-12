# AETHER: AI-Powered Observability Platform
### Intelligent Log Monitoring, Anomaly Detection & Evidence-First Root Cause Engine
**Hackathon Team:** Take the Money and Run  
**Challenge:** Case 1 - AI-Powered Observability  
**Case Partner:** MHP – A Porsche Company  
**GitHub Repository:** [git@github.com:vamshidharre/TaketheMoneyandRun_Hackathon.git](https://github.com/vamshidharre/TaketheMoneyandRun_Hackathon)

---

## Executive Summary

Modern enterprise software systems emit billions of unstructured and heterogeneous log events. As highlighted by MHP:
> *"An LLM cannot use evidence it never sees. Raw logs sit outside the model, go stale quickly, and are too large to paste into every prompt. Deterministic steps must retain control over parsing, retrieval, and scoring before generation."*

**AETHER** solves this with an **evidence-first, model-assisted architecture**:
1. **Universal Log Ingestion**: Automatically detects log dialects, handles heterogeneous timestamp formats, and scrubs credentials/PII via a built-in Data Governor.
2. **Deterministic Template Mining**: Implements the **Drain algorithm** (fixed-depth parse trees) to convert millions of variable lines into concise, stable log templates.
3. **Big Data Binary Columnar Engine**: Converts raw text into compressed **Apache Arrow / Parquet** binary columnar format with dictionary encoding and zero-copy memory mapping (`mmap`), reducing storage footprint by ~68% and scanning at over 150,000+ rows/sec.
4. **Hybrid Anomaly Detection**: Combines semantic failure keywords, severity weight multipliers, template frequency rarity, and temporal burst rate z-scores.
5. **Time & Topology Correlation**: Consolidates repetitive alerts into unified, actionable incidents, achieving **>90% alert noise reduction**.
6. **Grounded AI Reasoning**: Generates ranked root cause hypotheses, confidence scores with abstention, and remediation next steps grounded strictly in retrieved log evidence citations (`[Line X @ Timestamp]`).
7. **Interactive Incident Board**: A dark-mode observability dashboard featuring live anomaly timelines, filterable log streams, and an interactive investigation copilot.

---

## System Architecture

```
                    +------------------------------------+
                    |       Heterogeneous Raw Logs       |
                    | (HDFS, BGL, Linux, OpenStack, ...) |
                    +-----------------+------------------+
                                      |
   [Member 1: Ingestion & Parsing]    v
                    +------------------------------------+
                    | - Auto Structure & Dialect Detector|
                    | - Multi-format Fuzzy Timestamps    |
                    | - DataGovernor Redactor (PII/Auth) |
                    | - Domain Entity Miner (IP, blk_id) |
                    | - Drain Tree Template Extraction   |
                    +-----------------+------------------+
                                      | NormalizedLog Stream
   [Member 2: AI Analytics Layer]     v
                    +------------------------------------+
                    | - Hybrid Anomaly Detection         |
                    | - Sequence Transition Miner        |
                    | - TF-IDF Semantic Vector Index     |
                    | - Temporal & Topology Correlator   |
                    | - Grounded Root Cause Reasoner     |
                    +-----------------+------------------+
                                      | Incidents & Citations
   [Member 3 & 4: Dashboard & Demo]   v
                    +------------------------------------+
                    | - Interactive Incident Board UI    |
                    | - Temporal Anomaly Density Chart   |
                    | - Searchable Log Stream Explorer   |
                    | - Grounded AI Investigation Chat   |
                    | - MHP KPI Benchmark Reports        |
                    +------------------------------------+
```

---

## Team Workstream Division (4 Developers)

The project is structured for 4 team members with clean modular boundaries:

| Member | Workstream | Primary Modules | Key Responsibilities |
| :--- | :--- | :--- | :--- |
| **Member 1** | **Log Ingestion, Parsing & Governance** | `backend/ingestion/`<br>`backend/parsing/`<br>`backend/normalization/` | Auto-detects log dialects, multi-format timestamp normalization, Drain template miner, domain entity extraction, PII/secret redaction. |
| **Member 2** | **AI Analytics, Anomalies & Reasoning** | `backend/ai/` | Hybrid anomaly detector (z-score + rarity + severity), sequence transition mining, TF-IDF cosine embeddings, incident correlation, grounded root cause reasoning. |
| **Member 3** | **Incident Board & Visualization** | `frontend/` | Dark-mode single page dashboard, KPI banner, correlated incident cards, temporal anomaly timeline, filterable log table, natural language AI copilot. |
| **Member 4** | **Integration, Evaluation & Hackathon Demo** | `backend/app.py`<br>`backend/api/`<br>`backend/analytics/`<br>`tests/`<br>`scripts/` | FastAPI orchestration, REST API routes, MHP KPI evaluators, automated LogHub benchmark runs, full pytest suite, demo scripts. |

---

## LogHub Test Datasets & Scale Strategy

As recommended by MHP (Slide 10: *"Small to Big"*), AETHER includes **two complete 100% full real-world LogHub datasets** alongside concise representative slices:

| Dataset | System Type | Scale & Completeness | Anomalies Detected | Key Entities Extracted |
| :--- | :--- | :--- | :--- | :--- |
| **OpenStack (Complete)** | Cloud Infrastructure | **100% Complete Real LogHub (207,820 Lines, 61.4 MB)** | HTTP 500 API errors, Nova hypervisor exceptions, instance spawn crashes | Request IDs (`req-...`), Tenant/User IDs, HTTP endpoints |
| **Linux (Complete)** | Operating System | **100% Complete Real LogHub (25,567 Lines, 263.9 Days)** | SSH brute-force attacks, PAM auth failures | Remote IPs, usernames, PAM daemons |
| **HDFS (Slice)** | Distributed File System | 2,000 Lines Focused Slice | DataNode PacketResponder drops | `blk_<id>`, DataNode IP/Port |
| **BGL (Slice)** | Supercomputer | 2,000 Lines Focused Slice | Compute node parity & bus alerts | Node coordinates (`R02-M1...`), hex registers |
| **OpenStack (Slice)** | Cloud Infrastructure | 2,000 Lines Focused Slice | VM lifecycle disruptions | Request ID (`req-...`), Tenant ID |

---

## Multi-Tier AI Anomaly Detection Architecture

AETHER implements the recommended big-data architecture: **Parse & Template Once $\rightarrow$ Bake into Parquet $\rightarrow$ Run Multi-Tier Detection on Binary Data**:

1. **Tier 1 (Frequency-Based Baseline)**: Fast template rarity lookup. Infrequent templates (<2% of traffic) are flagged as suspicious.
2. **Tier 2 (Tabular Machine Learning - Isolation Forest)**: Scikit-learn `IsolationForest(n_estimators=50)` trained over structured numeric features (`[template_freq, severity_num, time_delta, params_count, burst_zscore]`).
3. **Tier 3 (Sequence Transition Mining)**: Markov / n-gram sequence transition modeling per entity session (detecting unexpected state jumps or retry storms).
4. **Tier 4 (Time & Topology Correlation)**: Clusters correlated anomalies within sliding temporal windows and shared entities into unified incidents (**>90% alert noise reduction**).

---

## Measured MHP KPIs & Benchmark Results

### 1. Full-Scale Production Datasets Benchmark (2.55+ Million Lines)

Evaluated across all 14 production systems using the full Parse-Once-to-Binary + Multi-Tier AI Anomaly Detection pipeline:

| System | Domain | Lines Processed | Raw Size | Templates Discovered | Drain Speed | Anomalies Flagged | Correlated Incidents | Alert Noise Reduction | Triage Velocity | Binary Parquet Size | Storage Saved | Parquet Scan Throughput |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **OpenStack** | Cloud | **207,820** | 58.8 MB | 122 | 5,130 lines/s | 5,381 | 4 | **99.90%** | **1,541.0x** | 22.50 MB | **61.5%** | **4.81M rows/s** (43.2ms) |
| **Mac OS** | Operating System | **116,735** | 16.1 MB | 966 | 9,502 lines/s | 105,350 | 2,055 | **98.05%** | **637.1x** | 4.22 MB | **73.3%** | **13.22M rows/s** (8.8ms) |
| **Hadoop** | Distributed MapReduce | **179,993** | 30.4 MB | 213 | 8,057 lines/s | 37,455 | 1,033 | **97.24%** | **443.9x** | 7.19 MB | **76.2%** | **18.34M rows/s** (9.8ms) |
| **HealthApp** | Mobile / Sensors | **212,394** | 19.5 MB | 342 | 12,277 lines/s | 84,777 | 447 | **99.47%** | **2,282.6x** | 9.74 MB | **49.6%** | **20.39M rows/s** (10.4ms) |
| **Zookeeper** | Distributed Coordination | **74,273** | 9.9 MB | 53 | 10,333 lines/s | 55,104 | 477 | **99.13%** | **1,422.7x** | 1.98 MB | **79.8%** | **8.99M rows/s** (8.3ms) |
| **Apache** | Web Server | **51,978** | 4.8 MB | 143 | 11,335 lines/s | 46,422 | 7,305 | **84.26%** | **79.4x** | 1.22 MB | **74.0%** | **4.35M rows/s** (12.0ms) |
| **Linux** | Operating System | **25,567** | 2.3 MB | 452 | 11,523 lines/s | 15,361 | 2,004 | **86.95%** | **95.7x** | 0.75 MB | **66.3%** | **3.01M rows/s** (8.5ms) |
| **Proxifier** | Network Proxy | **21,320** | 2.4 MB | 21 | 9,889 lines/s | 1,071 | 79 | **92.62%** | **164.8x** | 0.96 MB | **59.6%** | **2.45M rows/s** (8.7ms) |
| **OpenSSH** | Authentication Daemon | **250,000** | 25.4 MB | 36 | 11,436 lines/s | 148,096 | 1,941 | **98.69%** | **943.4x** | 5.96 MB | **76.5%** | **21.09M rows/s** (11.9ms) |
| **HPC** | Supercomputer Cluster | **250,000** | 15.6 MB | 294 | 16,577 lines/s | 67,036 | 49,185 | **26.63%** | **17.0x** | 8.26 MB | **47.2%** | **20.70M rows/s** (12.1ms) |
| **BGL** | BlueGene/L Supercomputer | **250,000** | 31.8 MB | 1,237 | 7,642 lines/s | 61,891 | 257 | **99.58%** | **2,676.8x** | 12.13 MB | **61.9%** | **19.73M rows/s** (12.7ms) |
| **Thunderbird** | Supercomputer Cluster | **250,000** | 34.5 MB | 1,155 | 4,474 lines/s | 32,804 | 290 | **99.12%** | **1,202.9x** | 11.09 MB | **67.9%** | **22.10M rows/s** (11.3ms) |
| **HDFS** | Distributed File System | **250,000** | 33.2 MB | 29 | 10,890 lines/s | 655 | 3 | **99.54%** | **318.6x** | 12.22 MB | **63.2%** | **23.90M rows/s** (10.5ms) |
| **Spark** | Distributed Processing | **250,000** | 27.8 MB | 134 | 9,635 lines/s | 51,768 | 480 | **99.07%** | **1,279.1x** | 8.90 MB | **67.9%** | **23.49M rows/s** (10.6ms) |
| **TOTAL** | **14 Diverse Systems** | **2,554,870** | **308.2 MB** | **5,497** | **10,030 avg/s** | **713,271** | **65,160** | **90.86% avg** | **836.5x avg** | **106.33 MB** | **65.5% avg** | **15.4M rows/s avg** |

---

### 2. LogHub 16-System Cross-Domain Benchmark Suite

Evaluated across all 16 systems against official LogHub ground-truth templates:

| Domain | System | Dialect | Discovered Templates | Ground Truth Templates | Template Match Quality | Anomalies Flagged | Noise Reduction | Triage Velocity | Parquet Storage Saved |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Distributed Systems** | **HDFS** | HDFS | 16 | 14 | **High (87.5%)** | 92 | 12.0% | 14.2x | 13.7% |
| | **Hadoop** | Generic | 89 | 114 | **High (78.1%)** | 1,009 | **99.8%** | **5367.0x** | 78.0% |
| | **Spark** | Generic | 24 | 36 | **High (66.7%)** | 38 | **84.2%** | **76.3x** | 53.9% |
| | **Zookeeper** | Generic | 35 | 50 | **High (70.0%)** | 1,458 | **84.7%** | **81.6x** | 62.0% |
| | **OpenStack** | OpenStack | 26 | 43 | **High (60.5%)** | 78 | **98.7%** | **696.4x** | 62.4% |
| **Supercomputers** | **BGL** | BGL | 843 | 120 | Extended | 1,006 | 42.0% | 21.5x | 18.6% |
| | **HPC** | Generic | 77 | 46 | Extended | 811 | 9.0% | 13.7x | 20.7% |
| | **Thunderbird** | BGL | 133 | 149 | **Very High (89.3%)** | 301 | **99.7%** | **2839.6x** | 57.3% |
| **Operating Systems** | **Linux** | Syslog | 112 | 118 | **Very High (94.9%)** | 648 | **92.3%** | **161.3x** | 72.2% |
| | **Mac OS** | Syslog | 311 | 341 | **Very High (91.2%)** | 1,958 | **64.6%** | **35.3x** | 50.7% |
| | **Windows** | Generic | 40 | 50 | **High (80.0%)** | 300 | **98.0%** | **600.0x** | 84.4% |
| **Mobile Systems** | **Android** | Generic | 68 | 166 | Moderate | 15 | 40.0% | 20.2x | 53.6% |
| | **HealthApp** | Generic | 74 | 75 | **Exceptional (98.7%)** | 48 | **81.3%** | **65.0x** | 40.2% |
| **Server Applications** | **Apache** | Generic | 12 | 6 | Extended | 596 | **71.6%** | **44.0x** | 68.0% |
| | **OpenSSH** | Syslog | 24 | 27 | **Very High (88.9%)** | 1,234 | **98.0%** | **611.5x** | 73.9% |
| | **Proxifier** | Generic | 20 | 8 | Extended | 97 | **90.7%** | **131.0x** | 49.4% |

---

## Quickstart Guide

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Git

### 1. Clone & Set Up Environment
```bash
git clone git@github.com:vamshidharre/TaketheMoneyandRun_Hackathon.git
cd TaketheMoneyandRun_Hackathon

# Optional: PowerShell one-click setup
.\scripts\setup_env.ps1
```

Or manually:
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python scripts/download_datasets.py
```

### 2. Run the Application
```bash
python backend/app.py
```
Or with Uvicorn:
```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open the Incident Board
Navigate to **`http://localhost:8000`** in your browser.
- Select any LogHub dataset from the dropdown (HDFS, Linux, BGL, OpenStack) or upload a custom log file.
- Inspect the correlated incident cards and exact line-level root-cause citations.
- Ask the **AI Investigation Copilot** natural language questions grounded in evidence.

---

## Automated Test Suite

Run the full pytest suite covering ingestion, parsing, AI analysis, correlation, and end-to-end API workflows:
```bash
python -m pytest tests/ -v
```
All **19 tests pass in under 4 seconds**.

---

## REST API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status |
| `GET` | `/api/datasets` | List available LogHub sample datasets |
| `POST` | `/api/ingest/sample` | Ingest and analyze a pre-loaded sample |
| `POST` | `/api/ingest/upload` | Upload and analyze a custom log file |
| `GET` | `/api/analysis/overview` | Active dataset summary, templates, and KPIs |
| `GET` | `/api/analysis/incidents` | Correlated incident reports with root causes |
| `GET` | `/api/analysis/logs` | Searchable, paginated log stream |
| `GET` | `/api/analysis/timeline` | Temporal bucket distribution for charting |
| `POST` | `/api/investigate/query` | Grounded natural language Q&A |
| `GET` | `/api/metrics/benchmark` | Automated evaluation across all datasets |

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
