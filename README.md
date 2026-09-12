# Rivyn: Log Intelligence

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyArrow](https://img.shields.io/badge/PyArrow-Columnar_Parquet-teal.svg)](https://arrow.apache.org/docs/python/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit_Learn-Isolation_Forest-F7931E.svg?logo=scikitlearn&logoColor=white)](https://scikit-learn.org)
[![OpenAI GPT-4o](https://img.shields.io/badge/OpenAI-GPT--4o_LLM-412991.svg?logo=openai&logoColor=white)](https://openai.com)
[![Tests](https://img.shields.io/badge/pytest-31_passed_6_skipped-brightgreen.svg)](https://pytest.org)
[![MHP Challenge](https://img.shields.io/badge/MHP_Hackathon-Take_the_Money_and_Run-blueviolet.svg)](#)

> **Rivyn** is an AI log intelligence platform designed for the **MHP Hackathon ("Take the Money and Run")**. It transforms multi-gigabyte unformatted raw system logs into structured columnar binary storage (**Apache Parquet**), uncovers rare behavioral shifts using **Multi-Tier AI Anomaly Detection**, and clusters alert floods into root-cause incident tickets, measured at **88-97% alert noise reduction** on the committed LogHub datasets.

---

## Architecture: Parse & Store Once, Detect & Query at Binary Speed

```
 RAW LOG INGESTION (Syslog, OpenStack, HDFS, etc.)
        │
        ▼
 ┌─────────────────────────────────────────────────────────┐
 │ 1. Single-Pass Regex Drain Tree Parser                  │
 │    • Dynamic regex-masked parameter extraction          │
 │    • Semantic template mining (2.3k-5k lines/sec)       │
 └─────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────┐
 │ 2. Columnar Binary Engine (Apache Parquet + Snappy)     │
 │    • Schema: {timestamp, template_id, params, level...} │
 │    • 59% – 66% storage reduction vs raw text             │
 │    • Zero-copy SIMD columnar pushdown scans             │
 └─────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────┐
 │ 3. Multi-Tier AI Anomaly Detection Engine               │
 │    • Tier 1: Statistical Template Rarity Lookup         │
 │    • Tier 2: Scikit-learn Isolation Forest on Features  │
 │    • Tier 3: Markov Sequence Transition Mining          │
 └─────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────┐
 │ 4. Temporal & Topological Incident Correlator           │
 │    • Sliding time-window correlation (Δt ≤ 120s)        │
 │    • Compresses alerts into root-cause tickets          │
 │    • 88% - 97% measured alert noise reduction           │
 └─────────────────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────────────────┐
 │ 5. Grounded Copilot & Interactive Incident Board        │
 │    • TF-IDF or semantic retrieval, always cited       │
 │    • Live Web Dashboard running at http://localhost:8000 │
 └─────────────────────────────────────────────────────────┘
```

---

## Definitive Benchmark Results: 7 LogHub Production Datasets (2.7M+ Lines)

Evaluated across **all 7 heterogeneous LogHub production datasets** in `data/samples/`:
1. **Linux**: 100% complete OS syslog & auth logs (25,567 lines)
2. **OpenStack**: 100% complete cloud infrastructure logs (207,820 lines, 58.6 MB)
3. **ZooKeeper**: 100% complete distributed coordination logs (74,380 lines, 10.4 MB)
4. **Hadoop**: 100% complete MapReduce/YARN container logs (393,431 lines across 978 files, 46.4 MB)
5. **Spark**: 500,000 lines milestone from distributed compute executor cluster logs
6. **BGL (BlueGene/L)**: 500,000 lines milestone from 131k-core LLNL supercomputer RAS kernel logs
7. **HDFS**: 1,000,000 lines milestone from 1.58 GB / 11.17M lines storage cluster dataset

### Comprehensive 7-System Performance & Storage KPI Summary

| Metric | Linux | OpenStack | ZooKeeper | Hadoop | Spark | BGL (Supercomputer) | HDFS |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **System Category** | OS / Syslog | Cloud IaaS | Coordination | Big Data Compute | Analytics Engine | HPC Supercomputer | Distributed Storage |
| **Raw File Path** | `Linux.log` | `OpenStack.log` | `Zookeeper.log` | `Hadoop.log` | `Spark.log` | `BGL/BGL.log` | `HDFS.log` |
| **Lines Processed** | **25,567** (100%) | **207,820** (100%) | **74,380** (100%) | **393,431** (100%) | **500,000** | **500,000** | **1,000,000** |
| **Detected Dialect** | `syslog` | `openstack` | `zookeeper` | `hadoop` | `spark` | `bgl` | `hdfs` |
| **Templates Discovered** | 452 | 122 | 89 | 1,712 | 720 | 132 | 36 |
| **Drain Parse Speed** | **11,520 lines/s** | **6,143 lines/s** | **12,601 lines/s** | **13,372 lines/s** | **12,223 lines/s** | **9,190 lines/s** | **9,984 lines/s** |
| **Anomalies Flagged** | 15,361 | 5,379 | 53,972 | 166,780 | 103,995 | 274,030 | 94,523 |
| **Correlated Incidents** | 1,811 | 137 | 437 | 5,767 | 2,153 | 530 | 24 |
| **Alert Noise Reduction** | **88.21%** | **97.45%** | **99.19%** | **96.54%** | **97.93%** | **99.81%** | **99.90%** |
| **Triage Velocity Speedup** | **105.9x** | **391.8x** | **1,522.2x** | **359.6x** | **592.4x** | **5,888.2x** | **9,502.3x** |
| **Raw Text Size** | 2.21 MB | 58.40 MB | 9.79 MB | 45.40 MB | 51.35 MB | 64.91 MB | 132.35 MB |
| **Parquet Binary Size** | **0.75 MB** | **22.62 MB** | **1.15 MB** | **8.11 MB** | **11.55 MB** | **6.94 MB** | **53.82 MB** |
| **Storage Saved (%)** | **66.25%** | **61.27%** | **88.22%** | **82.13%** | **77.50%** | **89.30%** | **59.33%** |
| **Storage Reduction** | **3.0x** | **2.6x** | **8.5x** | **5.6x** | **4.4x** | **9.3x** | **2.5x** |
| **Zero-Copy Scan Speed** | **408k rows/s** | **11.9M rows/s** | **6.6M rows/s** | **28.1M rows/s** | **25.4M rows/s** | **33.3M rows/s** | **21.0M rows/s** |

*All benchmark results are automatically generated and verifiable via `scripts/benchmark_all_datasets.py` and stored in `data/benchmark_all_datasets.json` (Total: **2,701,198 lines** processed in 350.71s).*

### Semantic retrieval: matching meaning, not wording

MHP's opening slide poses the problem as `"find me all dogs"` returning a picture
of a puppy. TF-IDF cannot do that -- it matches tokens, so a query only finds a
log line if they literally share words.

With `requirements-semantic.txt` installed, retrieval runs on dense embeddings
instead. Measured on the same four-line corpus, using queries that deliberately
share **no** vocabulary with the logs they should find:

| Query | TF-IDF | Semantic |
| :--- | :---: | :--- |
| "brute force login attack" | no match | `authentication failure for user root` |
| "disk replica pipeline aborted" | no match | `PacketResponder terminating for block` |
| "faulty RAM hardware fault" | no match | `memory parity error corrected` |
| "virtual machine created" | no match | `instance spawned successfully` |

TF-IDF retrieves nothing in all four cases. Semantic retrieval finds the right
line every time. Reproduce with `pytest tests/test_semantic_retrieval.py -v`.

### Known limitations

Stated plainly, because the MHP brief asks for documented limitations rather than
a clean-looking table.

- **BGL correlation remains the weakest at ~46% noise reduction**, though the
  template miner no longer over-splits it (843 templates across 2,000 lines
  reduced to 107 by stripping the BGL header and masking node coordinates).
  What remains is genuine: BGL spans seven months of sparse, heterogeneous
  hardware faults with little to consolidate.
- **Ingestion is bounded by memory.** The pipeline holds every parsed line in RAM
  as a Pydantic object, measured at roughly 3.5 KB per line. That puts a practical
  ceiling near 1-2M lines on a 16 GB machine. Streaming ingestion is the next
  architectural step and is not implemented.
- **Semantic retrieval is opt-in.** The base install uses TF-IDF, which matches
  wording rather than meaning, so a query for "brute force attack" will not reach
  a line reading "authentication failure". Installing
  `requirements-semantic.txt` switches retrieval to a sentence-transformer
  (`all-MiniLM-L6-v2`) that matches meaning instead. It is kept optional because
  it pulls in torch, a multi-gigabyte download, and the base clone must stay
  runnable. `LogEmbeddingIndex.backend` reports which is active
  (`"semantic"` / `"tfidf"`), and nothing breaks without it.
- **LLM reasoning is opt-in.** Without an API key the platform serves its
  deterministic rule-based narratives, so incident text on the board may come from
  either the LLM or the rule engine and the response does not currently say which.
- **HDFS tests skip on a fresh clone.** Five tests depend on the 1.58 GB
  `HDFS.log`, which is not committed. They skip with an actionable message rather
  than failing; fetch the dataset into `data/samples/` to run them.

---

## Key Technical Highlights

### 1. Ingestion & Pre-Parsing Optimization (Drain3 Algorithm)
- Replaced slow multi-pass regex loops with a single-pass compiled regex mask (`COMBINED_MASK`) matching IP addresses, UUIDs, hex values, file paths, and dates in a single scan.
- Measured at **2,300 - 5,100 lines/second** pure Python parsing throughput on a consumer laptop (hardware-dependent).
- Discovers semantic clusters without manual regex configuration.

### 2. Big Data Binary Columnar Storage (Apache Parquet)
- Bakes structured schema (`timestamp`, `template_id`, `parameter_list`, `service`, `level`, `anomaly_score`) directly into Parquet files with dictionary encoding and Snappy compression.
- Achieves **2.5x to 3.0x storage reduction** compared to raw plaintext.
- Vectorized PyArrow scanners push filters down at the byte level. Scan throughput is reported per run by `/api/storage/binary-stats` rather than quoted here, since it varies widely with cache state.

### 3. Multi-Tier AI Anomaly Detection & Incident Correlation
- **Tier 1 (Template Rarity)**: Identifies infrequent log templates (<1-2% of overall frequency).
- **Tier 2 (Isolation Forest)**: Trains an ensemble of isolation trees on extracted numerical telemetry features (`[template_freq, severity_num, time_delta, params_count, burst_zscore]`).
- **Tier 3 (Sequence Mining)**: Flags improbable state transitions across sliding execution windows.
- **Incident Correlator**: Groups anomalies by mined template, then merges across templates that share an entity and overlap in time, into unified incident cards. Measured at **88.21% (Linux) and 97.45% (OpenStack)** noise reduction.

### 4. Generative LLM Incident Reasoning & Copilot (OpenAI / Claude / Gemini)
- **OpenAI Integration (Primary)**: Powered by OpenAI (`gpt-4o-mini` / `gpt-4o`) via `OPENAI_API_KEY` (leveraging hackathon OpenAI credits), with support for Anthropic Claude and Google Gemini.
- **Root-Cause Synthesis**: Generates executive summaries, technical root-cause hypotheses citing exact log lines, and numbered remediation checklists using strict JSON schema validation.
- **Grounded Copilot (RAG)**: Conversational assistant answering natural language questions grounded strictly in retrieved log evidence passages with line citations (`[Line <id> @ <timestamp>]`).
- **Deterministic Offline Fallback**: Automatically switches to the deterministic engine if no API key is provided or if network calls timeout, ensuring 100% offline reliability for hackathon presentations.

---

## Quickstart Guide

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Git

### 1. Installation
```bash
git clone git@github.com:vamshidharre/TaketheMoneyandRun_Hackathon.git
cd TaketheMoneyandRun_Hackathon

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Run the Web Application
```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser.
- Switch between **all 7 datasets** (Linux, OpenStack, ZooKeeper, Hadoop, Spark, BGL, HDFS).
- View real-time alert noise reduction KPIs, Drain template graphs, and incident cards.
- Investigate root causes interactively with the AI Investigation Copilot (OpenAI `gpt-4o-mini`).

### 3. Run the Automated Benchmarks
```bash
python scripts/benchmark_all_datasets.py
```
Processes and benchmarks all 7 datasets (2.7M+ lines), generating `data/benchmark_all_datasets.json`.

### 4. Run Automated Tests
```bash
python -m pytest tests/ -v
```
The semantic-retrieval test automatically skips when its optional model is
not installed. Run this command on the presentation machine and report the
exact result rather than relying on a stale test-count claim.

### 5. Interpret Triage Speedup Correctly
The dashboard's triage-speedup KPI compares measured pipeline time against a
**modeled** 15-seconds-per-anomalous-log manual baseline. It is not a human
timed study. See [the baseline comparison protocol](docs/baseline_comparison.md)
for the reproducible human-review evaluation used for final validation.

### 6. Security & Secrets Management
API keys (such as `OPENAI_API_KEY`) are loaded from `.env` via `python-dotenv`. `.env` and all credential files are strictly excluded via `.gitignore` and are never committed to version control. An example template is provided in `.env.example`.

---

## REST API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Application health and status check |
| `GET` | `/api/datasets` | List available authoritative datasets (Linux, OpenStack, HDFS) |
| `POST` | `/api/ingest/sample` | Ingest and analyze a dataset from disk |
| `POST` | `/api/ingest/upload` | Upload and analyze a custom raw log file |
| `GET` | `/api/analysis/overview` | Active dataset KPIs, templates, and noise reduction stats |
| `GET` | `/api/analysis/incidents` | Correlated incident reports with root-cause summaries |
| `GET` | `/api/analysis/logs` | Searchable, paginated log stream |
| `GET` | `/api/analysis/timeline` | Incident distribution across temporal buckets |
| `GET` | `/api/storage/binary-stats`| Parquet binary size, compression ratio, and scan throughput |
| `POST` | `/api/investigate/query` | Grounded natural language Q&A with line citations |
| `GET` | `/api/metrics/benchmark` | Run cross-dataset evaluation benchmark |

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
