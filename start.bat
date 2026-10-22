@echo off
setlocal enabledelayedexpansion

title LectureNotes AI Launcher

echo =================================================================
echo                 LectureNotes AI -- Launching
echo =================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Python is not found in your PATH.
    echo     Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: 2. Create virtual environment if missing
if not exist ".venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment in .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [-] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [+] Virtual environment created.
)

:: 3. Activate virtual environment
echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat

:: 4. Install / Verify dependencies
echo [*] Checking and installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] Warning: Some dependencies may not have installed cleanly.
)

:: 5. Create .env from .env.example if missing
if not exist ".env" (
    echo [*] Creating .env from .env.example...
    copy .env.example .env >nul
    echo [+] Created .env configuration file.
)

:: 6. Run System Hardware Diagnostic
echo.
python -m backend.check_system
echo.

:: 7. Open browser after short delay
echo [*] Starting web app at http://localhost:8000 ...
start "" http://localhost:8000

:: 8. Launch FastAPI backend server via uvicorn
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
