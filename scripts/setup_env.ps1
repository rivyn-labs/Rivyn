# Environment Setup Script for Windows PowerShell
Write-Host "[*] Setting up Python virtual environment..." -ForegroundColor Cyan
python -m venv .venv
& .venv\Scripts\Activate.ps1

Write-Host "[*] Installing dependencies from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "[*] Fetching LogHub sample datasets..." -ForegroundColor Cyan
python scripts/download_datasets.py

Write-Host "[*] Running test suite..." -ForegroundColor Cyan
python -m pytest tests/ -v

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Setup complete! Start the application with:" -ForegroundColor Yellow
Write-Host "   python backend/app.py" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
