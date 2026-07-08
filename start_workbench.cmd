@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set "URL=http://127.0.0.1:8000/frontend/"
set "HEALTH_URL=http://127.0.0.1:8000/api/llm/status"
set "LOG_DIR=%~dp0logs"
set "OUT_LOG=%LOG_DIR%\workbench-server.log"
set "ERR_LOG=%LOG_DIR%\workbench-server.err.log"

if not exist ".venv\Scripts\python.exe" (
  echo Missing Python runtime: .venv\Scripts\python.exe
  echo Create or restore the local virtual environment first.
  pause
  exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
  echo Workbench server is already running.
  start "" "%URL%"
  exit /b 0
)

echo Starting workbench server...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -WorkingDirectory '%~dp0' -FilePath '%~dp0.venv\Scripts\python.exe' -ArgumentList 'tools\workflow_server.py' -RedirectStandardOutput '%OUT_LOG%' -RedirectStandardError '%ERR_LOG%'"

for /l %%i in (1,1,20) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
  if !errorlevel! equ 0 goto server_ready
  ping 127.0.0.1 -n 2 >nul
)

echo Workbench server did not become ready.
echo Check logs:
echo   %OUT_LOG%
echo   %ERR_LOG%
pause
exit /b 1

:server_ready
start "" "%URL%"
echo Workbench server ready: %URL%
exit /b 0
