import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from backend.ingestion.incremental import IncrementalIngestor
from backend.ai.llm_reasoner import GroundedReasoner
from backend.api.state import state
from backend.config import settings

router = APIRouter(prefix="/api", tags=["Ingestion"])
UPLOAD_LINE_LIMIT = 2_000

class SampleIngestRequest(BaseModel):
    dataset: str  # hdfs, bgl, linux, openstack, or hdfs_big, etc.
    max_lines: Optional[int] = None
    source_line_offset: int = 0

class RawIngestRequest(BaseModel):
    content: str
    dataset_name: Optional[str] = "custom_raw"
    source_id: Optional[str] = None
    source_line_offset: int = 0

def _read_file_slice(filepath: str, offset: int, limit: int):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as stream:
        for _ in range(offset):
            next(stream, None)
        return [line.rstrip("\r\n") for _, line in zip(range(limit), stream)]

@router.get("/storage/binary-stats")
def get_binary_stats():
    if not state.binary_stats:
        return {"status": "no_binary_data"}
    return {"binary_engine": state.binary_stats}


@router.get("/ai/status")
def get_ai_status():
    """Expose configuration readiness without ever exposing credentials."""
    reasoner = GroundedReasoner()
    return {
        "openai_configured": bool(reasoner.openai_api_key),
        "active_provider": "openai" if reasoner.openai_api_key else "deterministic_fallback",
        "model": reasoner.model if reasoner.openai_api_key else None,
        "max_incidents_per_ingestion": settings.llm_max_incidents_per_ingestion,
    }

@router.get("/datasets")
def list_available_datasets():
    datasets = [
        {"id": "openstack", "name": "OpenStack", "type": "Cloud Infrastructure", "scale": "Complete LogHub", "file": "OpenStack.log"},
        {"id": "linux", "name": "Linux", "type": "Operating System", "scale": "Complete LogHub", "file": "Linux.log"},
        {"id": "zookeeper", "name": "ZooKeeper", "type": "Distributed Coordination", "scale": "Complete LogHub", "file": "Zookeeper.log"},
        {"id": "hadoop", "name": "Hadoop", "type": "Big Data Compute", "scale": "Complete LogHub", "file": "Hadoop.log"},
        {"id": "spark", "name": "Apache Spark (500,000 Lines Milestone)", "type": "Distributed Analytics", "scale": "Large Scale (500k)", "file": "Spark.log"},
        {"id": "bgl", "name": "BlueGene/L Supercomputer (4.75M Lines - HPC)", "type": "Supercomputing / HPC", "scale": "Supercomputing Scale", "file": "BGL.log"},
        {"id": "hdfs", "name": "HDFS Distributed FS (1.58 GB / 11M Lines)", "type": "Distributed File System", "scale": "Enterprise Scale", "file": "HDFS.log"},
    ]
    return {"datasets": datasets}

@router.post("/ingest/sample")
def ingest_sample(req: SampleIngestRequest):
    ds = req.dataset.lower()
    if ds in ("openstack", "openstack_full"):
        filepath = os.path.join(settings.samples_dir, "OpenStack.log")
        lines_limit = req.max_lines or 207820
    elif ds in ("linux", "linux_full"):
        filepath = os.path.join(settings.samples_dir, "Linux.log")
        lines_limit = req.max_lines or 25567
    elif ds in ("zookeeper", "zookeeper_full"):
        flat_path = os.path.join(settings.samples_dir, "Zookeeper.log")
        filepath = flat_path if os.path.exists(flat_path) else os.path.join(settings.samples_dir, "Zookeeper", "Zookeeper.log")
        lines_limit = req.max_lines or 74380
    elif ds in ("hadoop", "hadoop_full"):
        filepath = os.path.join(settings.samples_dir, "Hadoop.log")
        lines_limit = req.max_lines or 394310
    elif ds in ("spark", "spark_sample"):
        filepath = os.path.join(settings.samples_dir, "Spark.log")
        lines_limit = req.max_lines or 100000
    elif ds in ("bgl", "bgl_sample", "bgl_full"):
        nested_path = os.path.join(settings.samples_dir, "BGL", "BGL.log")
        filepath = nested_path if os.path.exists(nested_path) else os.path.join(settings.samples_dir, "BGL.log")
        lines_limit = req.max_lines or 100000
    elif ds in ("hdfs", "hdfs_big", "hdfs_full"):
        filepath = os.path.join(settings.samples_dir, "HDFS.log")
        lines_limit = req.max_lines or 100000
    else:
        filepath = os.path.join(settings.samples_dir, f"{req.dataset}.log")
        if not os.path.exists(filepath):
            filepath = os.path.join(settings.samples_dir, req.dataset, f"{req.dataset}.log")
        lines_limit = req.max_lines or 50000

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Sample dataset file '{filepath}' not found.")

    batch = IncrementalIngestor.ingest(
        _read_file_slice(filepath, req.source_line_offset, lines_limit), req.dataset,
        source_id=os.path.abspath(filepath), source_line_offset=req.source_line_offset,
    )

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
async def ingest_upload(
    file: UploadFile = File(...), source_id: Optional[str] = Form(None), source_line_offset: int = Form(0, ge=0)
):
    contents = await file.read()
    text = contents.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="The uploaded file contains no log lines.")

    selected_lines = lines[source_line_offset:source_line_offset + UPLOAD_LINE_LIMIT]
    if not selected_lines:
        raise HTTPException(
            status_code=400,
            detail=f"No log lines exist at or after source line {source_line_offset + 1}.",
        )

    dataset_name = file.filename or "uploaded_file"
    previous_total = state.datasets.get(dataset_name).batch.total_lines if dataset_name in state.datasets else 0
    accepted_lines = len(selected_lines)
    batch = IncrementalIngestor.ingest(
        selected_lines, dataset_name,
        source_id=source_id or dataset_name, source_line_offset=source_line_offset,
    )
    new_lines = batch.total_lines - previous_total

    return {
        "status": "success",
        "dataset": batch.dataset_name,
        "detected_format": batch.detected_format,
        "total_lines": batch.total_lines,
        "anomalies_count": batch.metrics.anomalies_count,
        "incidents_count": batch.metrics.incidents_count,
        "noise_reduction_ratio": f"{batch.metrics.noise_reduction_ratio}%",
        "submitted_lines": len(lines),
        "accepted_lines": accepted_lines,
        "source_line_start": source_line_offset + 1,
        "source_line_end": source_line_offset + accepted_lines,
        "next_source_line": source_line_offset + accepted_lines + 1,
        "new_lines": new_lines,
        "duplicate": accepted_lines > 0 and new_lines == 0,
        "truncated": source_line_offset + accepted_lines < len(lines),
    }

@router.post("/ingest/raw")
def ingest_raw(req: RawIngestRequest):
    lines = req.content.splitlines()
    dataset_name = req.dataset_name or "custom_raw"
    batch = IncrementalIngestor.ingest(
        lines[:2000], dataset_name, source_id=req.source_id or dataset_name,
        source_line_offset=req.source_line_offset,
    )

    return {
        "status": "success",
        "dataset": batch.dataset_name,
        "detected_format": batch.detected_format,
        "total_lines": batch.total_lines,
        "anomalies_count": batch.metrics.anomalies_count,
        "incidents_count": batch.metrics.incidents_count
    }
