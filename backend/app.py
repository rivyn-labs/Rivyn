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
from backend.api.routes_ingest import router as ingest_router
from backend.api.routes_analysis import router as analysis_router
from backend.api.routes_investigate import router as investigate_router
from backend.api.routes_metrics import router as metrics_router
from backend.ingestion.incremental import IncrementalIngestor
from backend.api.state import state

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ObservabilityApp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Pre-populate complete LogHub Linux dataset (or HDFS fallback)
    linux_sample = os.path.join(settings.samples_dir, "Linux.log")
    sample_file = linux_sample if os.path.exists(linux_sample) else os.path.join(settings.samples_dir, "hdfs_sample.log")
    dataset_name = "linux_full" if "Linux.log" in sample_file else "hdfs"
    if os.path.exists(sample_file):
        try:
            logger.info(f"Pre-loading {dataset_name} ({sample_file}) for immediate demo availability...")
            with open(sample_file, "r", encoding="utf-8", errors="ignore") as stream:
                lines = [line.rstrip("\r\n") for _, line in zip(range(26000), stream)]
            batch = IncrementalIngestor.ingest(
                lines, dataset_name, source_id=os.path.abspath(sample_file),
                output_dir=os.path.join(settings.data_dir, "binary"),
            )
            logger.info(f"Demo data loaded: {len(batch.logs):,} logs, {len(batch.incidents)} incidents.")
        except Exception as e:
            logger.error(f"Failed to pre-load sample: {e}")
    yield

app = FastAPI(
    title=settings.app_name,
    description="Rivyn turns raw logs into clear next moves.",
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
