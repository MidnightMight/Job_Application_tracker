@echo off
REM launch.bat — One-command launcher for Job Application Tracker (Windows)
REM Usage: double-click launch.bat  OR  run from Command Prompt / PowerShell

setlocal EnableDelayedExpansion

cd /d "%~dp0"

set VENV_DIR=%~dp0venv

REM ── Respect PORT env var (default 5000) ─────────────────────────────────
if not defined PORT set PORT=5000

REM ── Find a usable Python 3 interpreter ──────────────────────────────────
REM   Priority: py launcher (standard on Windows) → python3 → python
set PYTHON=

for %%C in (py python3 python) do (
    if not defined PYTHON (
        where %%C >nul 2>&1
        if not errorlevel 1 (
            REM Verify it is Python 3
            for /f %%V in ('%%C -c "import sys; print(sys.version_info.major)" 2^>nul') do (
                if "%%V"=="3" set PYTHON=%%C
            )
        )
    )
)

if not defined PYTHON (
    echo.
    echo [ERROR] Python 3 was not found on your PATH.
    echo.
    echo  Options to install Python 3 on Windows:
    echo    1. Microsoft Store  ^(search "Python 3"^) — easiest, no PATH setup needed
    echo    2. python.org       ^(https://www.python.org/downloads/^)
    echo       Tick "Add Python to PATH" during install.
    echo    3. winget:  winget install Python.Python.3
    echo.
    pause
    exit /b 1
)

REM Show which Python is being used
for /f "tokens=*" %%V in ('%PYTHON% --version 2^>^&1') do echo [launcher] Using Python: %%V

REM ── Create virtual environment if it doesn't exist ──────────────────────
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [launcher] Creating virtual environment in .\venv ...
    %PYTHON% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not create virtual environment.
        echo         Try: %PYTHON% -m pip install virtualenv
        echo         Or reinstall Python from https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
)

REM ── Activate the virtual environment ────────────────────────────────────
call "%VENV_DIR%\Scripts\activate.bat"

REM ── Install / upgrade dependencies ──────────────────────────────────────
echo [launcher] Installing / verifying dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

REM ── Open browser and start server ───────────────────────────────────────
echo [launcher] Starting Job Tracker at http://localhost:%PORT%
echo [launcher] Close this window or press Ctrl+C to stop the server.
echo.
start "" "http://localhost:%PORT%"
python app.py

pause
