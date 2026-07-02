@echo off
setlocal EnableExtensions EnableDelayedExpansion

title NEXORA OS - Windows Application Launcher

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "APP_DIR=%ROOT%\nexora_os"
set "FRONTEND_DIR=%APP_DIR%\frontend"
set "LOG_DIR=%APP_DIR%\logs"
set "PORT=7474"
set "URL=http://127.0.0.1:%PORT%"
set "DEFAULT_OLLAMA_MODEL=llama3.2:1b"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================================
echo  NEXORA OS - Windows Application Launcher
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not installed or not on PATH.
  echo Install Python 3.10+ and run this file again.
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

echo [1/9] Checking Python backend dependencies...
python -c "import fastapi, uvicorn, pydantic, psutil" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing backend dependencies...
  python -m pip install -r "%APP_DIR%\requirements.txt"
  if errorlevel 1 (
    echo [ERROR] Backend dependency installation failed.
    pause
    exit /b 1
  )
)

echo [2/9] Checking Windows desktop app runtime...
python -c "from PySide6.QtWebEngineWidgets import QWebEngineView" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing desktop app runtime. This is a one-time setup.
  python -m pip install -r "%APP_DIR%\requirements-desktop.txt"
  if errorlevel 1 (
    echo [ERROR] Desktop runtime installation failed.
    pause
    exit /b 1
  )
)

echo [3/9] Starting Ollama LLM service if available...
where ollama >nul 2>nul
if errorlevel 1 (
  echo [WARN] Ollama not found on PATH. NEXORA will run, but LLM status may be offline.
) else (
  tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul 2>nul
  if errorlevel 1 (
    start "Ollama LLM" /min ollama serve
    timeout /t 3 /nobreak >nul
  ) else (
    echo [OK] Ollama is already running.
  )
  set "OLLAMA_MODEL="
  for /f "skip=1 tokens=1" %%m in ('ollama list 2^>nul') do (
    if not defined OLLAMA_MODEL set "OLLAMA_MODEL=%%m"
  )
  if not defined OLLAMA_MODEL (
    echo [WARN] Ollama is running, but no local model is installed.
    echo        Recommended small model: %DEFAULT_OLLAMA_MODEL%
    set /p "PULL_MODEL=Download it now? This can take several minutes. [Y/N]: "
    if /I "!PULL_MODEL!"=="Y" (
      ollama pull %DEFAULT_OLLAMA_MODEL%
      if not errorlevel 1 set "OLLAMA_MODEL=%DEFAULT_OLLAMA_MODEL%"
    )
  )
  if defined OLLAMA_MODEL (
    set "NEXORA_OLLAMA_MODEL=!OLLAMA_MODEL!"
    echo [OK] NEXORA LLM model: !NEXORA_OLLAMA_MODEL!
  )
)

echo [4/9] Checking frontend dependencies...
if not exist "%FRONTEND_DIR%\node_modules" (
  pushd "%FRONTEND_DIR%"
  call npm install
  if errorlevel 1 (
    popd
    echo [ERROR] Frontend dependency installation failed.
    pause
    exit /b 1
  )
  popd
)

echo [5/9] Checking YOLO model for object detection...
if not exist "%ROOT%\models\yolov8n.pt" (
  echo [INFO] Downloading YOLO model for object detection...
  if not exist "%ROOT%\models" mkdir "%ROOT%\models"
  powershell -Command "Invoke-WebRequest -Uri 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt' -OutFile '%ROOT%\models\yolov8n.pt'"
  if errorlevel 1 (
    echo [WARN] YOLO model download failed. Object detection may not work.
  ) else (
    echo [OK] YOLO model downloaded.
  )
) else (
  echo [OK] YOLO model found at models\yolov8n.pt
)

echo [6/9] Checking Tesseract OCR for vision features...
where tesseract >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing Tesseract OCR for vision features...
  winget install --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements >nul 2>nul
  if errorlevel 1 (
    echo [WARN] Tesseract OCR installation failed. OCR may not work.
  ) else (
    echo [OK] Tesseract OCR installed.
  )
) else (
  echo [OK] Tesseract OCR is already installed.
)

echo [7/9] Building frontend if needed...
if not exist "%FRONTEND_DIR%\dist\index.html" (
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
  echo [OK] Existing frontend build found.
)

echo [8/9] Checking for existing NEXORA instance on port %PORT%...
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>nul
if not errorlevel 1 (
  echo [WARN] NEXORA is already running on port %PORT%.
  echo        Please close the existing instance first.
  pause
  exit /b 1
)

echo [9/9] Launching NEXORA Windows application...
echo.
echo A native NEXORA desktop window will open now.
echo Closing the desktop window stops the backend started by this launcher.
echo.
echo Latest configurations:
echo - Ollama LLM: Configured with llama3.2:1b
echo - YOLO Model: Downloaded to models/yolov8n.pt
echo - Tesseract OCR: Installed and configured
echo - Advanced Automation: App launch, file ops, browser automation enabled
echo - Hand Gesture Control: Motion-based camera control enabled
echo - Mouse Control: Hand gesture cursor movement and system control
echo - Instant Responses: Direct LLM integration without planning delays
echo - NEXORA Personality: System prompt for natural AI assistant behavior
echo.

cd /d "%ROOT%"
python -m nexora_os.desktop_app

echo.
echo NEXORA stopped.
pause
