@echo off
rem NSE Swing Scanner: double-click to set up (first time) and start the app.
setlocal
cd /d "%~dp0"
title NSE Swing Scanner

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Python 3.10 or newer is needed and was not found.
  call :install Python.Python.3.12 Python
  exit /b
)

where npm >nul 2>nul
if errorlevel 1 if not exist "scanner\frontend\dist\index.html" (
  echo Node.js is needed to build the page the first time and was not found.
  call :install OpenJS.NodeJS.LTS Node.js
  exit /b
)

%PY% scanner\launch.py %*
if errorlevel 1 (
  echo.
  echo The scanner stopped with a problem. Read the message above, or send a screenshot of this window.
  pause
)
exit /b

:install
where winget >nul 2>nul
if errorlevel 1 (
  echo Install %~2 from its website, then double-click start.bat again:
  if "%~2"=="Python" (echo   https://www.python.org/downloads/  -- tick "Add python.exe to PATH") else (echo   https://nodejs.org  -- choose the LTS version)
  pause
  exit /b 1
)
choice /m "Install %~2 now"
if errorlevel 2 exit /b 1
winget install -e --id %~1 --accept-package-agreements --accept-source-agreements
echo.
echo %~2 is installed. Close this window and double-click start.bat again.
pause
exit /b 0
