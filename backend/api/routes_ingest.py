import os
import time
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.ai.embeddings import LogEmbeddingIndex
from backend.ai.llm_reasoner import GroundedReasoner
from backend.analytics.metrics import ObservabilityEvaluator
from backend.storage.binary_engine import BinaryLogEngine
from backend.api.state import state

router = APIRouter(prefix="/api", tags=["Ingestion"])

class SampleIngestRequest(BaseModel):
    dataset: str  # hdfs, bgl, linux, openstack, or hdfs_big, etc.
    max_lines: Optional[int] = None

class RawIngestRequest(BaseModel):
    content: str
    dataset_name: Optional[str] = "custom_raw"

def _process_and_store(batch):
    t0 = time.time()
    detector = HybridAnomalyDetector()
    batch.logs = detector.detect_anomalies(batch.logs)

    correlator = IncidentCorrelator()
    incidents = correlator.correlate(batch.logs)

    logs_map = {l.id: l for l in batch.logs}
    reasoner = GroundedReasoner()
    for i, inc in enumerate(incidents):
        if i < 8:
            reasoner.explain_incident(inc, logs_map)
        else:
            evidence_logs = [logs_map[lid] for lid in inc.evidence_log_ids if lid in logs_map]
            if evidence_logs:
                reasoner._explain_deterministic(inc, evidence_logs)

    batch.incidents = incidents
    batch.metrics = ObservabilityEvaluator.calculate_metrics(
        batch.logs,
        incidents,
        len(batch.templates),
        pipeline_elapsed_sec=time.time() - t0
    )

    # Build semantic embedding index
    index = LogEmbeddingIndex(chunk_size=5)
    index.build_index(batch.logs)

    # Big Data Binary Columnar Serialization
    bin_save_stats = BinaryLogEngine.save_batch(batch, output_dir="data/binary")
    bin_scan_stats = BinaryLogEngine.scan_anomalies_vectorized(bin_save_stats["file_path"])

    state.current_batch = batch
    state.embedding_index = index
    state.binary_stats = {
        **bin_save_stats,
        **bin_scan_stats
    }
    return batch

@router.get("/storage/binary-stats")
def get_binary_stats():
    if not state.binary_stats:
        return {"status": "no_binary_data"}
    return {"binary_engine": state.binary_stats}

@router.get("/datasets")
def list_available_datasets():
    datasets = [
        {"id": "openstack", "name": "OpenStack Cloud (207,820 Lines - Complete LogHub)", "type": "Cloud Infrastructure", "scale": "Complete LogHub (100%)", "file": "OpenStack.log"},
        {"id": "linux", "name": "Linux Syslog (25,567 Lines - Complete LogHub)", "type": "Operating System", "scale": "Complete LogHub (100%)", "file": "Linux.log"},
        {"id": "hdfs", "name": "HDFS Distributed FS (1.58 GB / 11M Lines - LogHub)", "type": "Distributed File System", "scale": "Enterprise Scale", "file": "HDFS.log"},
    ]
    return {"datasets": datasets}

@router.post("/ingest/sample")
def ingest_sample(req: SampleIngestRequest):
    ds = req.dataset.lower()
    if ds in ("openstack", "openstack_full"):
        filepath = "data/samples/OpenStack.log"
        lines_limit = req.max_lines or 207820
    elif ds in ("linux", "linux_full"):
        filepath = "data/samples/Linux.log"
        lines_limit = req.max_lines or 25567
    elif ds in ("hdfs", "hdfs_big", "hdfs_full"):
        filepath = "data/samples/HDFS.log"
        lines_limit = req.max_lines or 100000
    else:
        # Check direct path or filename
        filepath = f"data/samples/{req.dataset}.log"
        lines_limit = req.max_lines or 5000

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Sample dataset file '{filepath}' not found.")

    batch = LogLoader.load_from_file(filepath, max_lines=lines_limit, dataset_name=req.dataset)
    _process_and_store(batch)

    return {
        "status": "success",
        "dataset": batch.dataset_name,
        "detected_format": batch.detected_format,
        "total_lines": batch.total_lines,
        "anomalies_count": batch.metrics.anomalies_count,
        "incidents_count": batch.metrics.incidents_count,
        "noise_reduction_ratio": f"{batch.metrics.noise_reduction_ratio}%",
        "triage_speedup": f"{batch.metrics.triage_speedup_ratio}x",
        "binary_storage": state.binary_stats
    }

@router.post("/ingest/upload")
async def ingest_upload(file: UploadFile = File(...)):
    contents = await file.read()
    text = contents.decode("utf-8", errors="ignore")
    lines = text.splitlines()

    batch = LogLoader.load_from_lines(lines[:2000], dataset_name=file.filename or "uploaded_file")
    _process_and_store(batch)

    return {
        "status": "success",
        "dataset": batch.dataset_name,
        "detected_format": batch.detected_format,
        "total_lines": batch.total_lines,
        "anomalies_count": batch.metrics.anomalies_count,
        "incidents_count": batch.metrics.incidents_count,
        "noise_reduction_ratio": f"{batch.metrics.noise_reduction_ratio}%"
    }

@router.post("/ingest/raw")
def ingest_raw(req: RawIngestRequest):
    lines = req.content.splitlines()
    batch = LogLoader.load_from_lines(lines[:2000], dataset_name=req.dataset_name or "custom_raw")
    _process_and_store(batch)

    return {
        "status": "success",
        "dataset": batch.dataset_name,
        "detected_format": batch.detected_format,
        "total_lines": batch.total_lines,
        "anomalies_count": batch.metrics.anomalies_count,
        "incidents_count": batch.metrics.incidents_count
    }
