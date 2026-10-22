#!/usr/bin/env bash
set -e

# Change to script directory
cd "$(dirname "$0")"

echo "================================================================="
echo "                LectureNotes AI -- Launching"
echo "================================================================="

# 1. Virtual environment
if [ ! -d ".venv" ]; then
    echo "[*] Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

echo "[*] Activating virtual environment..."
source .venv/bin/activate

# 2. Dependencies
echo "[*] Installing dependencies..."
pip install -r requirements.txt

# 3. Environment configuration
if [ ! -f ".env" ]; then
    echo "[*] Initializing .env from .env.example..."
    cp .env.example .env
fi

# 4. Diagnostic
python -m backend.check_system

# 5. Open browser if supported
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8000 &
elif command -v open > /dev/null; then
    open http://localhost:8000 &
fi

# 6. Run server
echo "[*] Starting FastAPI application on http://localhost:8000..."
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
