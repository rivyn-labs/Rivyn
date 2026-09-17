import os
import time
import uuid
from typing import Callable
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from backend.ingestion.loader import LogLoader
from backend.ingestion.streaming import StreamingLogProcessor
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.ai.embeddings import LogEmbeddingIndex
from backend.ai.llm_reasoner import GroundedReasoner
from backend.analytics.metrics import ObservabilityEvaluator
from backend.storage.binary_engine import BinaryLogEngine
from backend.api.state import state
from backend.config import settings

router = APIRouter(prefix="/api", tags=["Ingestion"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_LINES = 200_000
MAX_BULK_FILE_BYTES = 26 * 1024 * 1024 * 1024
# Conservative local calibration of the current Python parser + Parquet writer.
# The bulk route is intentionally disk-first, but parsing still dominates its
# throughput; do not promise SSD-speed ingestion before native/parallel parsing.
DEFAULT_STREAMING_BYTES_PER_SECOND = 160 * 1024
DEFAULT_LINES_PER_SECOND = 750.0
MIN_ESTIMATE_SECONDS = 5.0
PROCESSING_OVERHEAD_SECONDS = 4.0

class SampleIngestRequest(BaseModel):
    dataset: str  # hdfs, bgl, linux, openstack, or hdfs_big, etc.
    max_lines: Optional[int] = None

class RawIngestRequest(BaseModel):
    content: str
    dataset_name: Optional[str] = "custom_raw"

class BulkIngestRequest(BaseModel):
    filename: str
    dataset_name: Optional[str] = None

def _process_and_store(
    batch,
    report_progress: Optional[Callable[[str, int], None]] = None,
):
    def report(stage: str, percent: int) -> None:
        if report_progress:
            report_progress(stage, percent)

    t0 = time.time()
    report("Detecting anomalies", 25)
    detector = HybridAnomalyDetector()
    batch.logs = detector.detect_anomalies(batch.logs)

    report("Grouping incidents", 48)
    correlator = IncidentCorrelator()
    incidents = correlator.correlate(batch.logs)

    report("Explaining priority findings", 68)
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

    report("Building search index", 82)
    # Build semantic embedding index
    index = LogEmbeddingIndex(chunk_size=5)
    index.build_index(batch.logs)

    report("Optimizing storage", 93)
    # Big Data Binary Columnar Serialization
    bin_save_stats = BinaryLogEngine.save_batch(
        batch, output_dir=os.path.join(settings.data_dir, "binary")
    )
    bin_scan_stats = BinaryLogEngine.scan_anomalies_vectorized(bin_save_stats["file_path"])

    state.current_batch = batch
    state.embedding_index = index
    state.binary_stats = {
        **bin_save_stats,
        **bin_scan_stats
    }
    report("Ready", 100)
    return batch


def _estimate_processing_seconds(line_count: int) -> float:
    lines_per_second = state.observed_lines_per_second or DEFAULT_LINES_PER_SECOND
    return round(max(MIN_ESTIMATE_SECONDS, (line_count / lines_per_second) + PROCESSING_OVERHEAD_SECONDS), 1)


def _bulk_import_dir() -> str:
    path = os.path.join(settings.data_dir, "imports")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_bulk_source(filename: str) -> str:
    """Resolve a bulk source without allowing arbitrary server file reads."""
    clean_name = os.path.basename(filename)
    if not clean_name or clean_name != filename:
        raise HTTPException(status_code=400, detail="Use a filename from the bulk import folder, not a path.")
    source = os.path.join(_bulk_import_dir(), clean_name)
    if not os.path.isfile(source):
        raise HTTPException(status_code=404, detail=f"Bulk file '{clean_name}' was not found in data/imports.")
    if os.path.getsize(source) > MAX_BULK_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Bulk ingestion is limited to 26 GiB per run.")
    return source


def _estimate_streaming_seconds(byte_count: int) -> float:
    return round(max(20.0, byte_count / DEFAULT_STREAMING_BYTES_PER_SECOND), 1)


def _run_upload_job(job_id: str, lines: List[str], filename: str, byte_count: int) -> None:
    job = state.ingestion_jobs[job_id]
    job["status"] = "processing"
    job["started_at"] = time.time()
    job["stage"] = "Parsing log lines"
    job["progress"] = 10

    try:
        batch = LogLoader.load_from_lines(lines[:MAX_UPLOAD_LINES], dataset_name=filename)
        job["lines_processed"] = batch.total_lines
        job["stage"] = "Preparing analysis"
        job["progress"] = 18

        def update(stage: str, progress: int) -> None:
            job["stage"] = stage
            job["progress"] = progress

        _process_and_store(batch, report_progress=update)
        elapsed = max(0.01, time.time() - job["started_at"])
        lines_per_second = batch.total_lines / elapsed
        state.observed_lines_per_second = lines_per_second
        job.update({
            "status": "complete",
            "stage": "Ready",
            "progress": 100,
            "completed_at": time.time(),
            "elapsed_seconds": round(elapsed, 2),
            "lines_per_second": round(lines_per_second, 1),
            "bytes_per_second": round(byte_count / elapsed, 1),
        })
    except Exception as exc:
        job.update({
            "status": "failed",
            "stage": "Analysis failed",
            "error": str(exc),
            "completed_at": time.time(),
        })


def _run_bulk_stream_job(job_id: str, source_path: str, dataset_name: str) -> None:
    job = state.ingestion_jobs[job_id]
    job.update({"status": "processing", "started_at": time.time(), "stage": "Preparing disk-first stream", "progress": 3})
    try:
        def update(stage: str, progress: int, lines_processed: int) -> None:
            job.update({"stage": stage, "progress": progress, "lines_processed": lines_processed})

        processor = StreamingLogProcessor()
        output_dir = os.path.join(settings.data_dir, "streaming", job_id)
        batch, binary_stats = processor.process_file(source_path, dataset_name, output_dir, progress=update)
        elapsed = max(0.01, time.time() - job["started_at"])
        state.bulk_runs[job_id] = {
            "id": job_id,
            "dataset_name": dataset_name,
            "batch": batch,
            "binary_stats": binary_stats,
        }
        job.update({
            "status": "complete",
            "stage": "Bulk dataset stored",
            "progress": 100,
            "completed_at": time.time(),
            "elapsed_seconds": round(elapsed, 2),
            "lines_processed": batch.total_lines,
            "lines_per_second": round(batch.total_lines / elapsed, 1),
            "bytes_per_second": round(job["bytes"] / elapsed, 1),
            "execution_mode": "streaming",
            "parquet_file": binary_stats["filename"],
            "dashboard_preview_rows": binary_stats["dashboard_preview_rows"],
        })
    except Exception as exc:
        job.update({
            "status": "failed",
            "stage": "Bulk ingestion failed",
            "error": str(exc),
            "completed_at": time.time(),
        })

@router.get("/storage/binary-stats")
def get_binary_stats():
    if not state.binary_stats:
        return {"status": "no_binary_data"}
    return {"binary_engine": state.binary_stats}

@router.get("/datasets")
def list_available_datasets():
    datasets = [
        {"id": "openstack", "name": "OpenStack", "type": "Cloud Infrastructure", "scale": "Complete LogHub", "file": "OpenStack.log"},
        {"id": "linux", "name": "Linux", "type": "Operating System", "scale": "Complete LogHub", "file": "Linux.log"},
        {"id": "zookeeper", "name": "ZooKeeper", "type": "Distributed Coordination", "scale": "Complete LogHub", "file": "Zookeeper.log"},
        {"id": "hadoop", "name": "Hadoop", "type": "Big Data Compute", "scale": "Complete LogHub", "file": "Hadoop.log"},
        {"id": "spark", "name": "Spark", "type": "Distributed Analytics", "scale": "Large Scale", "file": "Spark.log"},
        {"id": "bgl", "name": "BlueGene/L", "type": "Supercomputing / HPC", "scale": "Supercomputing Scale", "file": "BGL.log"},
        {"id": "hdfs", "name": "HDFS", "type": "Distributed File System", "scale": "Enterprise Scale", "file": "HDFS.log"},
    ]
    return {"datasets": datasets}


@router.get("/ingest/bulk-files")
def list_bulk_files():
    """List local large files staged under data/imports for disk-first ingest."""
    allowed = {".log", ".txt", ".csv"}
    files = []
    for entry in os.scandir(_bulk_import_dir()):
        if entry.is_file() and os.path.splitext(entry.name)[1].lower() in allowed:
            files.append({"filename": entry.name, "bytes": entry.stat().st_size})
    return {"import_directory": "data/imports", "max_bytes": MAX_BULK_FILE_BYTES, "files": sorted(files, key=lambda item: item["filename"].lower())}


@router.post("/ingest/stream-file", status_code=202)
def ingest_bulk_file(req: BulkIngestRequest, background_tasks: BackgroundTasks):
    """Start a bounded-memory Parquet ingestion for a locally staged large file."""
    source = _safe_bulk_source(req.filename)
    byte_count = os.path.getsize(source)
    job_id = str(uuid.uuid4())
    dataset_name = req.dataset_name or os.path.splitext(os.path.basename(req.filename))[0]
    state.ingestion_jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "stage": "Queued for bulk streaming",
        "progress": 0,
        "filename": os.path.basename(req.filename),
        "bytes": byte_count,
        "lines_detected": None,
        "lines_to_process": None,
        "created_at": time.time(),
        "estimated_seconds": _estimate_streaming_seconds(byte_count),
        "execution_mode": "streaming",
    }
    background_tasks.add_task(_run_bulk_stream_job, job_id, source, dataset_name)
    return {
        "status": "accepted",
        "job_id": job_id,
        "execution_mode": "streaming",
        "estimated_seconds": state.ingestion_jobs[job_id]["estimated_seconds"],
        "message": "The source stays on disk while Rivyn writes chunked Parquet row groups.",
    }


@router.get("/ingest/bulk-runs/{job_id}")
def get_bulk_run(job_id: str):
    run = state.bulk_runs.get(job_id)
    if not run:
        raise HTTPException(status_code=404, detail="Bulk run is not available. Check the ingestion job first.")
    batch = run["batch"]
    return {
        "id": job_id,
        "dataset_name": run["dataset_name"],
        "total_lines": batch.total_lines,
        "detected_format": batch.detected_format,
        "anomalies_count": batch.metrics.anomalies_count,
        "incident_preview": [incident.model_dump() for incident in batch.incidents[:12]],
        "storage": run["binary_stats"],
    }

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
async def ingest_upload(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Upload exceeds the 20 MiB demo limit. Use a smaller slice for this in-memory demo."
        )
    text = contents.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="The uploaded file contains no readable log lines.")

    job_id = str(uuid.uuid4())
    lines_to_process = min(len(lines), MAX_UPLOAD_LINES)
    state.ingestion_jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "stage": "Queued for analysis",
        "progress": 0,
        "filename": file.filename or "uploaded_file",
        "bytes": len(contents),
        "lines_detected": len(lines),
        "lines_to_process": lines_to_process,
        "created_at": time.time(),
        "estimated_seconds": _estimate_processing_seconds(lines_to_process),
    }
    background_tasks.add_task(_run_upload_job, job_id, lines, file.filename or "uploaded_file", len(contents))
    return {
        "status": "accepted",
        "job_id": job_id,
        "estimated_seconds": state.ingestion_jobs[job_id]["estimated_seconds"],
        "lines_to_process": lines_to_process,
    }


@router.get("/ingest/jobs/{job_id}")
def get_ingest_job(job_id: str):
    job = state.ingestion_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found.")

    snapshot = dict(job)
    started_at = snapshot.get("started_at") or snapshot["created_at"]
    elapsed = snapshot.get("elapsed_seconds") or round(max(0.0, time.time() - started_at), 2)
    snapshot["elapsed_seconds"] = elapsed
    if snapshot["status"] in {"queued", "processing"}:
        snapshot["remaining_seconds"] = round(max(0.0, snapshot["estimated_seconds"] - elapsed), 1)
    else:
        snapshot["remaining_seconds"] = 0.0
    return snapshot

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
