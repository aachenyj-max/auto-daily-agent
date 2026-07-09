@echo off
setlocal

cd /d "%~dp0"
set "URL=http://127.0.0.1:8000/frontend/"

if not exist ".venv\Scripts\python.exe" (
  echo Missing Python runtime: .venv\Scripts\python.exe
  echo Create or restore the local virtual environment first.
  pause
  exit /b 1
)

echo Opening workbench page: %URL%
start "" "%URL%"
echo Starting local workbench server...
echo Keep this window open while using the site.
echo Close this window to stop the server.
echo.

".venv\Scripts\python.exe" tools\workflow_server.py
