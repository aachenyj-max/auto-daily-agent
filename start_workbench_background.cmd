@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set "HEALTH_URL=http://127.0.0.1:8000/api/llm/status"
set "LOG_DIR=%~dp0logs"
set "OUT_LOG=%LOG_DIR%\workbench-server.log"
set "ERR_LOG=%LOG_DIR%\workbench-server.err.log"

if not exist ".venv\Scripts\python.exe" exit /b 1
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 exit /b 0

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -WorkingDirectory '%~dp0' -FilePath '%~dp0.venv\Scripts\pythonw.exe' -ArgumentList 'tools\workflow_server.py'"

for /l %%i in (1,1,20) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
  if !errorlevel! equ 0 exit /b 0
  ping 127.0.0.1 -n 2 >nul
)

exit /b 1
