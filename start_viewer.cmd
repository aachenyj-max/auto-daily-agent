@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Missing Python runtime: .venv\Scripts\python.exe
  echo Create or restore the local virtual environment first.
  pause
  exit /b 1
)

start "Auto Daily Viewer Server" "%~dp0.venv\Scripts\python.exe" "%~dp0tools\serve_frontend.py"
ping 127.0.0.1 -n 3 >nul
start "" "http://127.0.0.1:8000/frontend/"

echo Read-only viewer started in a separate window.
echo This mode can browse existing reports but cannot submit generation jobs.
exit /b 0
