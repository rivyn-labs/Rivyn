from fastapi import APIRouter
from backend.api.state import state
from backend.analytics.benchmark import BenchmarkRunner

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])

@router.get("/kpis")
def get_kpis():
    if not state.current_batch:
        return {"status": "no_data"}
    return {
        "dataset": state.current_batch.dataset_name,
        "metrics": state.current_batch.metrics.model_dump()
    }

@router.get("/benchmark")
def run_benchmark():
    """
    Runs automated evaluation across all 4 LogHub benchmark datasets
    (HDFS, BGL, Linux, OpenStack).
    """
    results = BenchmarkRunner.run_all(max_lines=300)
    return {"benchmark_results": results}
