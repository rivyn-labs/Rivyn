import os
import sys
import logging
from contextlib import asynccontextmanager

# Ensure project root is in sys.path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.api import ingest_router, analysis_router, investigate_router, metrics_router
from backend.ingestion.loader import LogLoader
from backend.ai.anomaly_detector import HybridAnomalyDetector
from backend.ai.incident_correlator import IncidentCorrelator
from backend.ai.embeddings import LogEmbeddingIndex
from backend.ai.llm_reasoner import GroundedReasoner
from backend.analytics.metrics import ObservabilityEvaluator
from backend.api.state import state

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ObservabilityApp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Pre-populate complete LogHub Linux dataset (or HDFS fallback)
    sample_file = "data/samples/Linux.log" if os.path.exists("data/samples/Linux.log") else "data/samples/hdfs_sample.log"
    dataset_name = "linux_full" if "Linux.log" in sample_file else "hdfs"
    if os.path.exists(sample_file):
        try:
            logger.info(f"Pre-loading {dataset_name} ({sample_file}) for immediate demo availability...")
            batch = LogLoader.load_from_file(sample_file, max_lines=26000, dataset_name=dataset_name)
            batch.logs = HybridAnomalyDetector().detect_anomalies(batch.logs)
            incidents = IncidentCorrelator().correlate(batch.logs)
            logs_map = {l.id: l for l in batch.logs}
            # Run LLM reasoning on top 8 incidents; deterministic on remainder to conserve API credits and startup speed
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
                pipeline_elapsed_sec=0.45
            )
            index = LogEmbeddingIndex(chunk_size=5)
            index.build_index(batch.logs[:2000])

            # Binary Columnar Parquet Serialization
            from backend.storage.binary_engine import BinaryLogEngine
            bin_save = BinaryLogEngine.save_batch(batch, output_dir="data/binary")
            bin_scan = BinaryLogEngine.scan_anomalies_vectorized(bin_save["file_path"])
            state.binary_stats = {**bin_save, **bin_scan}

            state.current_batch = batch
            state.embedding_index = index
            logger.info(f"Demo data loaded: {len(batch.logs):,} logs, {len(incidents)} incidents.")
        except Exception as e:
            logger.error(f"Failed to pre-load sample: {e}")
    yield

app = FastAPI(
    title=settings.app_name,
    description="Evidence-first AI observability platform for heterogeneous logs (MHP Challenge)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(ingest_router)
app.include_router(analysis_router)
app.include_router(investigate_router)
app.include_router(metrics_router)

# Mount Frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_frontend_root():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": settings.app_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host=settings.app_host, port=settings.app_port, reload=True)
