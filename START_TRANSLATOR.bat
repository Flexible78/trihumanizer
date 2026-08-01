@echo off
setlocal
cd /d "%~dp0"

if not exist "data" mkdir "data"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py"
) else (
  set "PY=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo First start: creating the Python environment...
  %PY% -m venv .venv >"data\install.log" 2>&1
  if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -c "import flask, reportlab, bidi" >nul 2>nul
if errorlevel 1 (
  echo First start: installing required packages...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt >"data\install.log" 2>&1
  if errorlevel 1 goto :error
)

start "" /D "%CD%" ".venv\Scripts\pythonw.exe" "launcher.py"
exit /b 0

:error
echo.
echo START FAILED. Details are in data\install.log
if exist "data\install.log" type "data\install.log"
pause
exit /b 1
