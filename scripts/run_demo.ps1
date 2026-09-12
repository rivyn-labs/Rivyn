# Run script for AETHER AI-Powered Observability
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Starting AETHER AI Observability Platform (MHP Case 1) " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# Check if sample datasets exist
if (-not (Test-Path "data/samples/hdfs_sample.log")) {
    Write-Host "[*] Downloading LogHub sample datasets..." -ForegroundColor Green
    python scripts/download_datasets.py
}

Write-Host "[*] Launching FastAPI Server on http://localhost:8000..." -ForegroundColor Green
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
