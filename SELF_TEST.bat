@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run START_TRANSLATOR.bat once before SELF_TEST.bat.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" tests\self_test.py
pause
