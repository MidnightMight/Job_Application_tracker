@echo off
REM launch.bat — One-command launcher for Job Application Tracker (Windows)
REM Usage: double-click launch.bat  OR  run from Command Prompt

setlocal EnableDelayedExpansion

cd /d "%~dp0"

set VENV_DIR=%~dp0venv

REM ── Create virtual environment if it doesn't exist ──────────────────────
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [launcher] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create virtual environment.
        echo         Make sure Python 3 is installed and on your PATH.
        pause
        exit /b 1
    )
)

REM ── Activate the virtual environment ────────────────────────────────────
call "%VENV_DIR%\Scripts\activate.bat"

REM ── Install / upgrade dependencies ──────────────────────────────────────
echo [launcher] Installing dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

REM ── Open browser and launch server ──────────────────────────────────────
echo [launcher] Starting Job Tracker at http://localhost:5000
start "" "http://localhost:5000"
python app.py

pause
