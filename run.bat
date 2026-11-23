@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist .venv (
    echo [run.bat] Creating virtual environment...
    py -3.12 -m venv .venv 2>nul
    if not exist .venv python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [run.bat] Dependency install failed.
    exit /b 1
)
python -m playwright install chromium
python run.py
endlocal
