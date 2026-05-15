@echo off
SETLOCAL EnableDelayedExpansion
title JARVIS vNext — Installer
color 0B

echo.
echo  =====================================================
echo   J A R V I S  vNext — Windows Installer
echo  =====================================================
echo.

REM ── Check Python ──────────────────────────────────────
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo  [ERROR] Python not found. Install Python 3.10+ from python.org
    pause & exit /b 1
)
FOR /F "tokens=2" %%v IN ('python --version 2^>^&1') DO SET PY_VER=%%v
echo  [OK] Python %PY_VER%

REM ── Create venv ───────────────────────────────────────
IF NOT EXIST "venv\" (
    echo  Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo  [OK] Virtual environment active

REM ── Core pip upgrade ─────────────────────────────────
python -m pip install --upgrade pip --quiet

REM ── Install requirements ─────────────────────────────
echo  Installing Python packages...
pip install -r requirements.txt --quiet
IF ERRORLEVEL 1 (
    echo  [WARN] Some packages may have failed. Continuing...
)

REM ── PyAudio via pipwin ───────────────────────────────
echo  Installing PyAudio (microphone support)...
pip install pipwin --quiet
pipwin install pyaudio --quiet 2>nul
IF ERRORLEVEL 1 (
    echo  [WARN] PyAudio failed. Voice input disabled unless installed manually.
)

REM ── Playwright ───────────────────────────────────────
echo  Installing Playwright browser (chromium)...
python -m playwright install chromium --quiet 2>nul
IF ERRORLEVEL 1 (
    echo  [WARN] Playwright install failed. Browser control disabled.
)

REM ── Check Ollama ─────────────────────────────────────
echo.
echo  Checking Ollama...
ollama --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo  [ACTION NEEDED] Ollama not found.
    echo  Download from: https://ollama.com/download
    echo  After install, run:
    echo    ollama pull llama3.2
    echo    ollama pull deepseek-coder
    echo    ollama pull mistral
) ELSE (
    echo  [OK] Ollama found. Pulling models ^(this may take a while^)...
    start "Ollama" ollama serve
    timeout /t 3 /nobreak >nul
    ollama pull llama3.2
    ollama pull deepseek-coder
)

REM ── Create directories ────────────────────────────────
mkdir logs 2>nul
mkdir database 2>nul
mkdir screenshots 2>nul
mkdir backups 2>nul
mkdir plugins 2>nul
echo  [OK] Directories created

REM ── Done ─────────────────────────────────────────────
echo.
echo  =====================================================
echo   Installation complete!
echo  =====================================================
echo.
echo   To launch JARVIS:
echo     venv\Scripts\activate
echo     python jarvis_gui.py       ^<-- Futuristic UI
echo     python main.py             ^<-- Terminal mode
echo     python main.py --voice     ^<-- Voice mode
echo.
pause
