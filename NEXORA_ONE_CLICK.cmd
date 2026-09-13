@echo off
setlocal EnableExtensions EnableDelayedExpansion

title JARVIS Command Center - One Click Windows App

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "APP_DIR=%ROOT%\nexora_os"
set "FRONTEND_DIR=%APP_DIR%\frontend"
set "LOG_DIR=%APP_DIR%\logs"
set "VENV_DIR=%ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "PORT=7474"
set "URL=http://127.0.0.1:%PORT%"
set "DEFAULT_OLLAMA_MODEL=llama3.1:8b"
set "CHECK_ONLY=0"
if /I "%~1"=="--check" set "CHECK_ONLY=1"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================================
echo  JARVIS Command Center - One Click Windows Application
echo ============================================================
echo.
echo Project: %ROOT%
echo UI:      Native Windows desktop window
echo Backend: %URL%
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

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js/npm is not installed or not on PATH.
  echo Install Node.js 18+ and run this file again.
  pause
  exit /b 1
)

echo [1/8] Preparing isolated Python environment...
if not exist "%VENV_PY%" (
  echo [INFO] Creating virtual environment at "%VENV_DIR%"...
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ERROR] Failed to create the virtual environment.
    pause
    exit /b 1
  )
)
"%VENV_PY%" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] The virtual environment is missing pip.
  pause
  exit /b 1
)

echo [2/8] Checking Python backend dependencies...
"%VENV_PY%" -c "import fastapi, uvicorn, pydantic, psutil, PIL, cv2, speech_recognition, pyaudio, pyttsx3, pytesseract, pyautogui, mss" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing or repairing backend dependencies...
  "%VENV_PY%" -m pip install -r "%APP_DIR%\requirements.txt"
  if errorlevel 1 (
    echo [ERROR] Backend dependency installation failed.
    echo [HINT] Voice microphone support requires PyAudio. On Windows, install Microsoft C++ Build Tools if pip cannot find a PyAudio wheel for your Python version.
    pause
    exit /b 1
  )
) else (
  echo [OK] Backend dependencies ready.
)

echo [3/8] Checking Windows desktop runtime...
"%VENV_PY%" -c "from PySide6.QtWebEngineWidgets import QWebEngineView" >nul 2>nul
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

echo [4/8] Validating installed Python packages...
"%VENV_PY%" -m pip check
if errorlevel 1 (
  echo [ERROR] Python dependency validation failed.
  pause
  exit /b 1
)

echo [5/8] Starting local LLM service if Ollama is installed...
where ollama >nul 2>nul
if errorlevel 1 (
  echo [WARN] Ollama not found on PATH. JARVIS will still open, but LLM status may be offline.
) else (
  tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Starting Ollama in the background...
    start "JARVIS Ollama LLM" /min ollama serve
    timeout /t 3 /nobreak >nul
  ) else (
    echo [OK] Ollama is already running.
  )
  if not defined NEXORA_OLLAMA_MODEL set "NEXORA_OLLAMA_MODEL=%DEFAULT_OLLAMA_MODEL%"
  if not defined JARVIS_OLLAMA_MODEL set "JARVIS_OLLAMA_MODEL=!NEXORA_OLLAMA_MODEL!"
  echo [OK] Preferred local model: !NEXORA_OLLAMA_MODEL!
  echo [INFO] Ensuring model !NEXORA_OLLAMA_MODEL! is pulled...
  ollama list | find /I "!NEXORA_OLLAMA_MODEL!" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Downloading model !NEXORA_OLLAMA_MODEL! - this may take a while...
    ollama pull !NEXORA_OLLAMA_MODEL!
  ) else (
    echo [OK] Model !NEXORA_OLLAMA_MODEL! is already pulled.
  )
)

echo [6/8] Checking frontend dependencies...
if not exist "%FRONTEND_DIR%\node_modules" (
  pushd "%FRONTEND_DIR%"
  if exist package-lock.json (
    call npm ci
  ) else (
    call npm install
  )
  if errorlevel 1 (
    popd
    echo [ERROR] Frontend dependency installation failed.
    pause
    exit /b 1
  )
  popd
) else (
  echo [OK] Frontend dependencies ready.
)

echo [7/8] Building official Command Center UI when source is newer...
"%VENV_PY%" -c "from pathlib import Path; import sys; f=Path(r'%FRONTEND_DIR%'); dist=f/'dist'/'index.html'; files=[p for p in (f/'src').rglob('*') if p.is_file()] + [f/'index.html', f/'package.json', f/'package-lock.json', f/'vite.config.ts']; newest=max([p.stat().st_mtime for p in files if p.exists()], default=0); sys.exit(0 if dist.exists() and dist.stat().st_mtime >= newest else 1)" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Building frontend assets...
  pushd "%FRONTEND_DIR%"
  call npm run build
  if errorlevel 1 (
    popd
    echo [ERROR] Frontend build failed.
    pause
    exit /b 1
  )
  popd
) else (
  echo [OK] Current frontend build is up to date.
)

echo [8/8] Checking optional vision assets...
if exist "%ROOT%\models\yolov8n.pt" (
  echo [OK] YOLO object detection model found.
) else (
  echo [WARN] YOLO model missing at "%ROOT%\models\yolov8n.pt".
  echo        Vision will still open; object detection may be degraded.
)
where tesseract >nul 2>nul
if errorlevel 1 (
  echo [WARN] Tesseract OCR not found on PATH. OCR may be degraded.
) else (
  echo [OK] Tesseract OCR found.
)

echo Launching JARVIS as a Windows application...
echo.
echo Do not close this launcher while using JARVIS.
echo Closing the desktop window stops the backend started by this launcher.
echo This does not open an external web browser.
echo.

if "%CHECK_ONLY%"=="1" (
  echo [OK] Launcher preflight completed. Skipping desktop launch because --check was provided.
  exit /b 0
)

cd /d "%ROOT%"
"%VENV_PY%" -m nexora_os.desktop_app
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
  echo JARVIS stopped.
) else (
  echo [ERROR] JARVIS exited with code %EXIT_CODE%.
  echo Check logs:
  echo   %LOG_DIR%\desktop_backend.err.log
  echo   %LOG_DIR%\desktop_backend.out.log
)
pause
exit /b %EXIT_CODE%
