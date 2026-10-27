@echo off
rem NSE Swing Scanner: download the latest version, then start it.
setlocal
cd /d "%~dp0"
if not exist ".git" (
  echo This folder was not downloaded with Git, so it cannot update itself.
  echo Download the latest ZIP from https://github.com/pankajmehta1827/nse-trading-scanner
  echo ^(Code ^> Download ZIP^), extract it, and double-click start.bat there.
  pause
  exit /b 1
)
git pull --ff-only
if errorlevel 1 (
  echo.
  echo The update could not be downloaded. Read the message above.
  pause
  exit /b 1
)
call start.bat %*
