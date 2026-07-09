@echo off
setlocal

cd /d "%~dp0"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\AutoDailyWorkbench.lnk"
set "TARGET=%~dp0start_workbench_background.cmd"
set "WORKDIR=%~dp0"

if not exist "%TARGET%" (
  echo Missing script: %TARGET%
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$shortcut = $ws.CreateShortcut('%SHORTCUT_PATH%'); " ^
  "$shortcut.TargetPath = '%TARGET%'; " ^
  "$shortcut.WorkingDirectory = '%WORKDIR%'; " ^
  "$shortcut.WindowStyle = 7; " ^
  "$shortcut.Description = 'Start Auto Daily Agent workbench in background at login'; " ^
  "$shortcut.Save()"

if errorlevel 1 (
  echo Failed to install autostart shortcut.
  exit /b 1
)

echo Installed autostart shortcut:
echo   %SHORTCUT_PATH%
echo Run start_workbench_background.cmd once now if you want the server without waiting for next login.
exit /b 0
