# Team Workstreams & Ownership (4-Member Team)

This document defines the clear division of responsibilities, codebase ownership, and branch conventions for the four team members collaborating on the **MHP AI-Powered Observability** project.

---

## Team Member Ownership Matrix

| Member | Primary Workstream | Key Modules / Directories | Git Branch |
| :--- | :--- | :--- | :--- |
| **Member 1** | **Ingestion, Parsing & Governance** | `backend/ingestion/`, `backend/parsing/`, `backend/normalization/` | `feature/ws1-ingestion-parsing` |
| **Member 2** | **AI Analytics, Anomalies & Reasoning**| `backend/ai/` | `feature/ws2-ai-reasoning` |
| **Member 3** | **Incident Board UI & Visualization** | `frontend/` | `feature/ws3-ui-dashboard` |
| **Member 4** | **Integration, Evaluation & Demo** | `backend/app.py`, `backend/api/`, `backend/analytics/`, `tests/`, `scripts/` | `feature/ws4-integration-demo` |

---

## Detailed Task Breakdown

### Team Member 1: Log Ingestion, Parsing & Data Governance
* **Log Ingestion**: File streaming, multipart uploads, raw string ingestion (`loader.py`).
* **Dialect Detection**: Automatic classification of HDFS, Linux syslog, BGL, OpenStack, JSON, and Generic logs (`detector.py`).
* **Timestamp Normalizer**: Multi-format parsing (ISO-8601, syslog month-day, HDFS `YYMMDD`, BGL, Epoch) with monotonic fallback (`timestamp_parser.py`).
* **Template Mining**: Fixed-depth Drain tree clustering algorithm abstracting parameters to `<*>` (`drain_parser.py`).
* **Entity Extraction**: Mining block IDs, request IDs, IPs, users, compute nodes (`entity_extractor.py`).
* **Data Governance & Compliance**: Redaction of credentials, tokens, and PII (`redactor.py`).

### Team Member 2: AI Analytics, Anomaly Detection & Reasoning
* **Hybrid Anomaly Detector**: Scoring composite signals (keywords, severity weights, template rarity, temporal burst z-scores) (`anomaly_detector.py`).
* **Sequence Miner**: Entity session transition analysis and abnormal loop discovery (`sequence_miner.py`).
* **Vector Embeddings**: Sliding-window chunking, TF-IDF cosine semantic search (`embeddings.py`).
* **Incident Correlator**: Clustering temporal co-occurrence and entity affinity into unified incidents (`incident_correlator.py`).
* **Grounded Reasoner**: Evidence-first root cause analysis, confidence scoring with abstention, and remediation plans (`llm_reasoner.py`).

### Team Member 3: Visualization & Incident Board UI
* **Dashboard Layout**: Sleek dark-mode interface with Porsche/MHP styling (`index.html`, `style.css`).
* **KPI Header**: Real-time display of Noise Reduction, Correlated Incidents, Triage Speedup, and Discovered Templates.
* **Incident Board**: Ranked cards with severity badges, confidence meters, root causes, and remediation actions.
* **Timeline Chart**: Visual event density bars highlighting anomaly spikes.
* **Log Stream Table**: Searchable, filterable table with level badges, template tags, and anomaly scores.
* **Interactive AI Copilot**: Natural-language chat interface returning grounded evidence citations.

### Team Member 4: Integration, Evaluation & Hackathon Demo
* **FastAPI Application**: Unifying ingestion, AI analysis, metrics, and static asset serving (`app.py`, `backend/api/`).
* **KPI Metrics**: Computation of Noise Reduction Ratio, Precision@K, and Triage Speedup (`metrics.py`).
* **Automated Benchmarks**: Multi-dataset evaluation across all 4 LogHub test sets (`benchmark.py`).
* **Pytest Suite**: Complete unit and integration test coverage (`tests/`).
* **Demo Scenarios & Scripts**: One-click startup scripts (`run_demo.ps1`) and pitch flow.

---

## Git Workflow & Conventions

1. **Main Branch**: `main` is protected and always in a working, deployable state.
2. **Feature Branches**:
   - `feature/ws1-ingestion-parsing`
   - `feature/ws2-ai-reasoning`
   - `feature/ws3-ui-dashboard`
   - `feature/ws4-integration-demo`
3. **Commit Messages**: Follow standard conventional commits:
   - `feat(ingestion): ...`
   - `feat(ai): ...`
   - `feat(ui): ...`
   - `test(e2e): ...`
   - `docs: ...`
