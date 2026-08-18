@echo off
REM One-command setup + run for the Disaster Intelligence API (Windows).
REM
REM Usage: double-click start.bat, or run it from Command Prompt.
REM
REM Safe to re-run any time — it skips steps that are already done.

cd /d "%~dp0"

if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -q -r requirements.txt

echo.
echo Starting server...
echo   API:        http://127.0.0.1:8000
echo   Docs (UI):  http://127.0.0.1:8000/docs
echo   Press Ctrl+C to stop.
echo.

uvicorn app.main:app --reload
