"""API Package"""
from backend.api.routes_ingest import router as ingest_router
from backend.api.routes_analysis import router as analysis_router
from backend.api.routes_investigate import router as investigate_router
from backend.api.routes_metrics import router as metrics_router

__all__ = ["ingest_router", "analysis_router", "investigate_router", "metrics_router"]
