@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "APP_DIR=%ROOT%\nexora_os"
set "VENV_DIR=%ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "CHECK_ONLY=0"
if /I "%~1"=="--check" set "CHECK_ONLY=1"

title Jarvis Floating Pet

echo ============================================================
echo  Jarvis Floating Pet
echo ============================================================
echo Project: %ROOT%
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not installed or not on PATH.
  echo Install Python 3.10+ and run this file again.
  pause
  exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.10 or newer is required.
  python --version
  pause
  exit /b 1
)

if not exist "%VENV_PY%" (
  echo [INFO] Creating virtual environment at "%VENV_DIR%"...
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo [1/3] Checking desktop runtime...
"%VENV_PY%" -c "from PySide6.QtWidgets import QApplication" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing desktop runtime...
  "%VENV_PY%" -m pip install -r "%APP_DIR%\requirements-desktop.txt"
  if errorlevel 1 (
    echo [ERROR] Desktop runtime installation failed.
    pause
    exit /b 1
  )
) else (
  echo [OK] Desktop runtime ready.
)

echo [2/3] Checking optional backend dependencies...
"%VENV_PY%" -c "import psutil" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing backend dependencies used for status telemetry...
  "%VENV_PY%" -m pip install -r "%APP_DIR%\requirements.txt"
  if errorlevel 1 (
    echo [WARN] Backend dependency install failed. Pet can still run, but status may stay offline.
  )
) else (
  echo [OK] Telemetry dependencies ready.
)

echo [3/3] Launching the pet...
echo Tip: drag the pet to move it. Right-click for menu. Double-click to open Jarvis.
echo.

cd /d "%ROOT%"
if "%CHECK_ONLY%"=="1" (
  "%VENV_PY%" -m nexora_os.pet_app --smoke-test --screenshot "%ROOT%\logs\jarvis-pet-smoke.png"
) else (
  "%VENV_PY%" -m nexora_os.pet_app
)
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo [ERROR] Jarvis pet exited with code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%
