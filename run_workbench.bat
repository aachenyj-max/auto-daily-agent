@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set "URL=http://127.0.0.1:8000/frontend/"
set "HEALTH_URL=http://127.0.0.1:8000/api/llm/status"

if not exist ".venv\Scripts\python.exe" (
  echo Missing Python runtime: .venv\Scripts\python.exe
  echo Create or restore the local virtual environment first.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
  echo Workbench server is already running.
  start "" "%URL%"
  exit /b 0
)

echo Starting workbench server in a dedicated window...
start "Auto Daily Workbench Server" cmd /k ".venv\Scripts\python.exe tools\workflow_server.py"

for /l %%i in (1,1,30) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
  if !errorlevel! equ 0 goto server_ready
  timeout /t 1 /nobreak >nul
)

echo Workbench server did not become ready.
echo Check the "Auto Daily Workbench Server" window for the Python error output.
pause
exit /b 1

:server_ready
start "" "%URL%"
echo Workbench server ready: %URL%
exit /b 0
