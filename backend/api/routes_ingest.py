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
from backend.api.state import state

router = APIRouter(prefix="/api", tags=["Ingestion"])

class SampleIngestRequest(BaseModel):
    dataset: str  # hdfs, bgl, linux, openstack
    max_lines: Optional[int] = 500

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
    for inc in incidents:
        reasoner.explain_incident(inc, logs_map)

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

    state.current_batch = batch
    state.embedding_index = index
    return batch

@router.get("/datasets")
def list_available_datasets():
    samples_dir = "data/samples"
    datasets = [
        {"id": "hdfs", "name": "HDFS (Hadoop Distributed File System)", "type": "Distributed File System", "labeled": True},
        {"id": "linux", "name": "Linux Syslog (SSH Auth Failures)", "type": "Operating System", "labeled": False},
        {"id": "bgl", "name": "BGL (BlueGene/L Supercomputer)", "type": "HPC Supercomputer", "labeled": True},
        {"id": "openstack", "name": "OpenStack (Cloud VM Orchestration)", "type": "Cloud Infrastructure", "labeled": True},
    ]
    return {"datasets": datasets}

@router.post("/ingest/sample")
def ingest_sample(req: SampleIngestRequest):
    filepath = f"data/samples/{req.dataset}_sample.log"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Sample dataset '{req.dataset}' not found.")

    batch = LogLoader.load_from_file(filepath, max_lines=req.max_lines, dataset_name=req.dataset)
    _process_and_store(batch)

    return {
        "status": "success",
        "dataset": batch.dataset_name,
        "detected_format": batch.detected_format,
        "total_lines": batch.total_lines,
        "anomalies_count": batch.metrics.anomalies_count,
        "incidents_count": batch.metrics.incidents_count,
        "noise_reduction_ratio": f"{batch.metrics.noise_reduction_ratio}%",
        "triage_speedup": f"{batch.metrics.triage_speedup_ratio}x"
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
