@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" stop_app.py
) else (
  python stop_app.py
)
timeout /t 2 >nul
exit /b 0
