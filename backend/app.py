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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ObservabilityApp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep the presentation landing state empty. Sample data is loaded only when
    # the operator explicitly chooses a supported demo dataset or uploads a log.
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
        return FileResponse(
            os.path.join(frontend_dir, "index.html"),
            headers={"Cache-Control": "no-store"},
        )

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": settings.app_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host=settings.app_host, port=settings.app_port, reload=True)
