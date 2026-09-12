# AETHER Observability: Architecture & System Design

## Overview

AETHER is an **evidence-first, model-assisted** AI observability platform developed for **MHP Challenge 1: AI-Powered Observability**. 

The core design principle addresses the fundamental limitation identified by MHP:
> *"An LLM cannot use evidence it never sees. Raw logs sit outside the model, go stale quickly, and are too large to paste into every prompt. Deterministic steps must retain control over parsing, retrieval, and scoring before generation."*

---

## High-Level Architecture Diagram

```
                 +-----------------------------------------------+
                 |              Heterogeneous Logs               |
                 |      (HDFS, BGL, Linux, OpenStack, Custom)    |
                 +-----------------------+-----------------------+
                                         |
                                         v
   +---------------------------------------------------------------------------+
   |                       Workstream 1: Ingestion & Parsing                   |
   |                                                                           |
   |  [LogStructureDetector]   Detects format dialect & delimiters             |
   |  [DataGovernor]           Redacts credentials & PII (Compliance check)    |
   |  [TimestampParser]        Normalizes multi-format dates to ISO/epoch      |
   |  [EntityExtractor]        Mines Block IDs, IPs, Request IDs, Hosts        |
   |  [DrainParser]            Online tree clustering into stable templates    |
   +-------------------------------------+-------------------------------------+
                                         |
                                         v NormalizedLog Stream
   +---------------------------------------------------------------------------+
   |                       Workstream 2: AI Analytics Layer                    |
   |                                                                           |
   |  [HybridAnomalyDetector]  Combines semantic keywords, severity weights,   |
   |                           template frequency rarity & time-burst z-scores |
   |  [SequenceMiner]          Discovers state transitions & broken chains     |
   |  [IncidentCorrelator]     Clusters temporal co-occurrences & topologies   |
   |  [LogEmbeddingIndex]      TF-IDF / N-gram cosine semantic passage index   |
   |  [GroundedReasoner]       Ranked root cause, confidence & citations       |
   +-------------------------------------+-------------------------------------+
                                         |
                                         v Correlated Incidents & Metrics
   +---------------------------------------------------------------------------+
   |                  Workstream 3 & 4: Interface & Integration                |
   |                                                                           |
   |  [FastAPI REST API]       Endpoints for ingest, incidents, query, metrics |
   |  [Incident Board UI]      Dark-mode dashboard, timeline, log explorer     |
   |  [Investigation Copilot]  Natural-language Q&A grounded on log citations  |
   |  [KPI Evaluator]          Noise reduction %, triage speedup, precision@k  |
   +---------------------------------------------------------------------------+
```

---

## Detailed Pipeline Stages

### Stage 1: Observe & Ingest (Workstream 1)
- **Log Dialect Classification**: Analyzes log samples across regex signatures to classify dialects (HDFS, Linux syslog, BGL supercomputer, OpenStack cloud, JSON, or generic custom logs).
- **Data Governance & Redaction**: Cleans passwords, tokens, private keys, and emails to satisfy compliance before storage.
- **Timestamp Normalization**: Parses ISO-8601, syslog month-day formats, HDFS `YYMMDD HHMMSS`, BGL dotted strings, and epoch seconds into UTC ISO strings and floating point epochs.
- **Entity Extraction**: Unpacks domain identifiers (`blk_<id>`, `req-<id>`, node names, IP addresses) for graph linking.
- **Drain Template Clustering**: Replaces dynamic variables with wildcards `<*>` using fixed-depth tree traversal, converting thousands of raw messages into a concise set of stable templates.

### Stage 1.5: Big Data Binary Columnar Engine (`backend/storage/binary_engine.py`)
- **Apache Arrow / Parquet Serialization**: Serializes millions of normalized log events into compressed binary columnar format with Snappy compression.
- **Dictionary Encoding**: Encodes high-cardinality repetitive strings (`level`, `service`, `host`, `template_id`) into compact 1-byte integers, achieving **65%–70% compression** compared to raw ASCII text.
- **Zero-Copy Memory Mapping (`mmap`)**: Slices and scans millions of log lines without loading the entire dataset into RAM, preventing Out-Of-Memory (OOM) errors.
- **Vectorized C-Speed Anomaly Scanning**: Executes boolean filters and anomaly threshold scans using PyArrow compute kernels, scanning over **150,000+ rows/second** at sub-30ms latency.

### Stage 2: Detect & Score (Workstream 2)
- **Hybrid Scoring**:
  $$\text{Composite Score} = \min(1.0, \text{Severity} + \text{Keyword Boost} + \text{Rarity} + \text{Temporal Burst})$$
  - **Severity**: Direct multipliers for `CRITICAL` (0.95), `FATAL` (0.90), `ERROR` (0.80), `WARN` (0.55).
  - **Semantic Keywords**: Detects failure indicators (`exception`, `fail`, `timeout`, `panic`, `dropped`).
  - **Template Rarity**: Inverse template probability across the batch.
  - **Temporal Burst Rate**: Z-score of log arrival density in sliding 30-second buckets.

### Stage 3: Correlate & Reduce Noise (Workstream 2)
- **Incident Correlator**: Groups anomalous events within sliding 60-second temporal windows or sharing identical entities (e.g. same block ID or compute node).
- **Noise Reduction**: Eliminates alert storming by converting hundreds of disparate log errors into a compact set of high-level incidents (typically >90% noise reduction).

### Stage 4: Grounded Reasoning & Explainability (Workstream 2)
- **Semantic Vector Index**: Builds sliding-window log chunks indexed via TF-IDF vector embeddings for sub-millisecond semantic retrieval.
- **Evidence-First Hypothesis Generation**: Generates incident titles, failure summaries, root causes with exact `[Line X @ Timestamp]` citations, confidence scores, and concrete remediation actions.
- **Abstention Support**: Lowers confidence or abstains when evidence is insufficient, preventing AI hallucinations.

### Stage 5: Experience & Action (Workstream 3 & 4)
- **Incident Board**: Displays ranked incident cards with severity indicators and remediation recommendations.
- **Interactive Timeline**: Visualizes event density over time with highlighted anomaly spikes.
- **Log Stream Table**: Filterable and searchable log view with template IDs and anomaly scores.
- **Grounded Copilot**: Interactive natural-language chat that answers engineer queries citing exact log evidence.
