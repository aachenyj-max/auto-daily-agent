@echo off
setlocal

set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AutoDailyWorkbench.lnk"

if exist "%SHORTCUT_PATH%" (
  del "%SHORTCUT_PATH%"
  echo Removed autostart shortcut:
  echo   %SHORTCUT_PATH%
) else (
  echo Autostart shortcut not found:
  echo   %SHORTCUT_PATH%
)

exit /b 0
