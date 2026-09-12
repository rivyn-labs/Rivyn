# AETHER: Autonomous Enterprise Log Triage & Binary Observability Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PyArrow](https://img.shields.io/badge/PyArrow-Columnar_Parquet-teal.svg)](https://arrow.apache.org/docs/python/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit_Learn-Isolation_Forest-F7931E.svg?logo=scikitlearn&logoColor=white)](https://scikit-learn.org)
[![OpenAI GPT-4o](https://img.shields.io/badge/OpenAI-GPT--4o_LLM-412991.svg?logo=openai&logoColor=white)](https://openai.com)
[![Tests](https://img.shields.io/badge/pytest-27_passed_5_skipped-brightgreen.svg)](https://pytest.org)
[![MHP Challenge](https://img.shields.io/badge/MHP_Hackathon-Take_the_Money_and_Run-blueviolet.svg)](#)

> **AETHER** is an enterprise-grade AI observability platform designed for the **MHP Hackathon ("Take the Money and Run")**. It transforms multi-gigabyte unformatted raw system logs into structured columnar binary storage (**Apache Parquet**), uncovers rare behavioral shifts using **Multi-Tier AI Anomaly Detection**, and clusters alert floods into root-cause incident tickets, measured at **88-97% alert noise reduction** on the committed LogHub datasets.

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
 │    • Evidence-grounded TF-IDF retrieval with citations  │
 │    • Live Web Dashboard running at http://localhost:8000 │
 └─────────────────────────────────────────────────────────┘
```

---

## Definitive Benchmark Results: Official LogHub Production Datasets

Evaluated across the LogHub datasets committed to `data/samples/`, so every figure
below can be reproduced from a fresh clone:
1. **Linux**: complete real-world dataset (25,567 lines, 2.38 MB)
2. **OpenStack**: complete real-world cloud infrastructure dataset (207,820 lines, 61.65 MB)

> **On HDFS.** Earlier revisions of this table reported a 1,000,000-line HDFS run.
> The 1.58 GB `HDFS.log` it was measured from is not committed to this repository,
> so those figures could not be reproduced from a clone and have been removed rather
> than left standing. Re-add the column once the dataset is fetchable via
> `scripts/download_datasets.py`.

> **How these were measured.** Single run, Python 3.12, Windows 11, consumer laptop,
> no warm cache. Throughput and elapsed time are hardware-dependent and will differ
> on other machines. Template counts, anomaly counts, incident counts and noise
> reduction are deterministic and should reproduce exactly.

### Comprehensive Performance & KPI Summary

| Metric | Linux (100% Full) | OpenStack (100% Full) |
| :--- | :---: | :---: |
| **System Category** | Operating System (Syslog/Auth) | Cloud Infrastructure (Nova/Keystone) |
| **Raw File Path** | `data/samples/Linux.log` | `data/samples/OpenStack.log` |
| **Raw File Size** | 2.38 MB | 61.65 MB |
| **Lines Evaluated** | **25,567 lines (100%)** | **207,820 lines (100%)** |
| **Detected Dialect** | `syslog` | `openstack` |
| **Drain Templates Discovered** | 452 | 122 |
| **Parse Speed** | 5,080 lines/sec | 2,324 lines/sec |
| **Total Ingestion Time** | 5.03 seconds | 89.41 seconds |
| **Raw Anomalies Flagged** | 15,361 | 5,379 |
| **Correlated Incidents Formed** | 1,811 | 137 |
| **Alert Noise Reduction (%)** | **88.21%** | **97.45%** |
| **Triage Velocity Speedup** | 106.0x | 489.3x |
| **Raw Text Size** | 2.21 MB | 58.40 MB |
| **Parquet Binary Size** | **0.75 MB** | **22.60 MB** |
| **Storage Space Saved** | **66.25% saved** | **61.30% saved** |
| **Storage Reduction Factor** | **3.0x smaller** | **2.6x smaller** |

*Reproduce with `scripts/benchmark_three_datasets.py`.*

### Known limitations

Stated plainly, because the MHP brief asks for documented limitations rather than
a clean-looking table.

- **BGL correlation is weak (~40% noise reduction).** The template miner emits a
  near-unique template for almost every BGL line (682 templates across 1,006
  anomalies), so there is little for the correlator to collapse. This is a parsing
  limitation, not a correlation one.
- **Ingestion is bounded by memory.** The pipeline holds every parsed line in RAM
  as a Pydantic object, measured at roughly 3.5 KB per line. That puts a practical
  ceiling near 1-2M lines on a 16 GB machine. Streaming ingestion is the next
  architectural step and is not implemented.
- **Retrieval is lexical, not semantic.** The index is TF-IDF over log chunks, so
  it matches wording rather than meaning. A query phrased differently from the
  underlying log text may miss.
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
- Switch between **OpenStack Cloud**, **Linux Syslog**, and **HDFS Distributed FS**.
- View real-time alert noise reduction KPIs, Drain template graphs, and incident cards.
- Investigate root causes interactively with the AI Investigation Copilot.

### 3. Run the Automated Benchmarks
```bash
python scripts/benchmark_three_datasets.py
```
Outputs comprehensive performance metrics and updates `data/benchmark_three_datasets.json`.

### 4. Run Automated Tests
```bash
python -m pytest tests/ -v
```
All **26 unit and end-to-end integration tests pass**.

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
