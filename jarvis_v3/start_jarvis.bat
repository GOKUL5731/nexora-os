@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title JARVIS CORE OS v6.0
color 0C
cd /d "%~dp0"
set "PYTHONUTF8=1"

call :resolve_python
if errorlevel 1 (
    color 0C
    echo.
    echo  [ERROR] Python not found. Install Python 3.10+ or create a venv first.
    echo.
    pause
    exit /b 1
)

call :start_ollama_silent

if /i "%~1"=="--gui"      goto mode_gui
if /i "%~1"=="--hud"      goto mode_hud
if /i "%~1"=="--terminal" goto mode_terminal
if /i "%~1"=="--voice"    goto mode_voice
if /i "%~1"=="--test"     goto mode_test
if /i "%~1"=="--gpu"      goto mode_gpu

:menu
cls
color 0B
echo.
echo  ========================================================
echo   J A R V I S  C O R E  O S  v6.0
echo   Autonomous AI Operating System
echo   Phase 2 DL + Phase 3 Agents + Phase 4 AI LAB
echo  ========================================================
echo.
echo   Python : %PYTHON_CMD%
echo   Folder : %CD%
echo   Ollama : %OLLAMA_STATUS%
echo.
echo  --------------------------------------------------------
echo   [1]  CORE OS Full Dashboard  (ALL phases - RECOMMENDED)
echo   [2]  Phase 2 Only            (Deep learning + vision)
echo   [3]  Holographic HUD         (fullscreen 3D UI)
echo   [4]  Terminal Chat           (text commands)
echo   [5]  Voice Mode              (speak to JARVIS)
echo   [6]  Run Tests               (full test suite)
echo   [7]  Phase 2 Tests           (DL module self-tests)
echo   [8]  Install GPU + PyTorch   (CUDA 12.1 for RTX 4050)
echo   [9]  Start Ollama            (LLM server)
echo   [Q]  Quit
echo  --------------------------------------------------------
echo.

set /p "CHOICE=  Your choice: "

if /i "%CHOICE%"=="1" goto mode_core_os
if /i "%CHOICE%"=="2" goto mode_phase2
if /i "%CHOICE%"=="3" goto mode_hud
if /i "%CHOICE%"=="4" goto mode_terminal
if /i "%CHOICE%"=="5" goto mode_voice
if /i "%CHOICE%"=="6" goto mode_test
if /i "%CHOICE%"=="7" goto mode_phase2_test
if /i "%CHOICE%"=="8" goto mode_gpu
if /i "%CHOICE%"=="9" goto mode_ollama
if /i "%CHOICE%"=="Q" goto quit
if /i "%CHOICE%"=="q" goto quit

echo.
echo  Invalid choice. Press any key...
pause >nul
goto menu

:mode_core_os
cls
color 0B
echo.
echo  [JARVIS CORE OS] Launching full AI OS dashboard...
echo  [INFO] Initializing: Phase 2 DL + Agents + Workflows + AI LAB
echo  [INFO] First launch may take 15-20 seconds.
echo.
"%PYTHON_CMD%" -X utf8 main.py --gui
goto done

:mode_phase2
cls
color 09
echo.
echo  [JARVIS] Phase 2 - Deep Learning Layer
echo  [INFO]   CNN Vision + LSTM Behavior + GPU Memory
echo.
"%PYTHON_CMD%" -X utf8 jarvis_phase2.py
goto done

:mode_gui
cls
color 0A
echo.
echo  [JARVIS] Launching classic GUI...
echo.
"%PYTHON_CMD%" -X utf8 jarvis_phase2.py
goto done

:mode_hud
cls
color 0B
echo.
echo  [JARVIS] Launching holographic HUD...
echo  [TIP]    Type commands directly. Ctrl+Space opens dashboard. ESC exits.
echo.
"%PYTHON_CMD%" -X utf8 hud.py
goto done

:mode_terminal
cls
color 0B
echo.
echo  [JARVIS] Terminal Chat Mode
echo  [TIP]    Type 'help' for commands. Type 'exit' to quit.
echo.
"%PYTHON_CMD%" -X utf8 main.py
goto done

:mode_voice
cls
color 0D
echo.
echo  [JARVIS] Voice Mode - say "Jarvis" to activate
echo  [TIP]    Requires a microphone. Uses local STT.
echo.
"%PYTHON_CMD%" -X utf8 main.py --voice
goto done

:mode_test
cls
color 0E
echo.
echo  [JARVIS] Running full test suite...
echo.
"%PYTHON_CMD%" -X utf8 tests/test_all.py
echo.
goto done_nopause

:mode_phase2_test
cls
color 0E
echo.
echo  [JARVIS] Phase 2 Deep Learning - Self-Test (7 modules)
echo.
"%PYTHON_CMD%" -X utf8 jarvis_phase2.py --test
echo.
goto done_nopause

:mode_gpu
cls
color 09
echo.
echo  [JARVIS] GPU Setup - PyTorch CUDA for RTX 4050
echo.

rem -- Detect Python version --
for /f "tokens=2 delims= " %%v in ('"%PYTHON_CMD%" --version 2^>^&1') do set "PY_VER=%%v"
echo  Detected Python: %PY_VER%
echo.

rem -- Check if Python >= 3.13 (the pinned CUDA 12.1 wheel needs Python 3.10-3.12) --
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

if %PY_MINOR% GEQ 13 (
    echo  [!] Python %PY_VER% is NOT supported by this CUDA 12.1 PyTorch install.
    echo      Use Python 3.10 - 3.12 for the pinned RTX 4050 wheel.
    echo.
    echo  Looking for or creating a Python 3.10-3.12 virtual environment...
    echo.

    if exist "..\jarvis_py312_venv\Scripts\python.exe" (
        set "PYTHON_CMD=%CD%\..\jarvis_py312_venv\Scripts\python.exe"
        echo  [OK] Using existing venv: ..\jarvis_py312_venv
        goto :install_torch
    )
    if exist "..\jarvis_py311_venv\Scripts\python.exe" (
        set "PYTHON_CMD=%CD%\..\jarvis_py311_venv\Scripts\python.exe"
        echo  [OK] Using existing venv: ..\jarvis_py311_venv
        goto :install_torch
    )
    if exist "..\jarvis_py310_venv\Scripts\python.exe" (
        set "PYTHON_CMD=%CD%\..\jarvis_py310_venv\Scripts\python.exe"
        echo  [OK] Using existing venv: ..\jarvis_py310_venv
        goto :install_torch
    )

    rem -- Try py launcher first (most reliable on Windows) --
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.12 -m venv ..\jarvis_py312_venv
        if exist "..\jarvis_py312_venv\Scripts\python.exe" (
            set "PYTHON_CMD=%CD%\..\jarvis_py312_venv\Scripts\python.exe"
            echo  [OK] Created venv at ..\jarvis_py312_venv using Python 3.12
            goto :install_torch
        )
        py -3.11 -m venv ..\jarvis_py311_venv
        if exist "..\jarvis_py311_venv\Scripts\python.exe" (
            set "PYTHON_CMD=%CD%\..\jarvis_py311_venv\Scripts\python.exe"
            echo  [OK] Created venv at ..\jarvis_py311_venv using Python 3.11
            goto :install_torch
        )
        py -3.10 -m venv ..\jarvis_py310_venv
        if exist "..\jarvis_py310_venv\Scripts\python.exe" (
            set "PYTHON_CMD=%CD%\..\jarvis_py310_venv\Scripts\python.exe"
            echo  [OK] Created venv at ..\jarvis_py310_venv using Python 3.10
            goto :install_torch
        )
    )

    echo  [!] Could not find Python 3.10, 3.11, or 3.12 via py launcher.
    echo.
    echo  ACTION REQUIRED:
    echo    1. Download Python 3.12 from https://www.python.org/downloads/
    echo    2. Install it (check "Add to PATH")
    echo    3. Run this option again
    echo.
    pause
    goto menu
) else (
    echo  [OK] Python %PY_VER% is compatible with PyTorch CUDA.
)

:install_torch
echo.
echo  Step 1: Upgrading pip...
"%PYTHON_CMD%" -m pip install --upgrade pip

echo.
echo  Step 2: Uninstalling any broken torch build...
"%PYTHON_CMD%" -m pip uninstall torch torchvision torchaudio -y 2>nul

echo.
echo  Step 3: Installing PyTorch 2.5.1 with CUDA 12.1...
"%PYTHON_CMD%" -m pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121

echo.
echo  Step 4: Installing Phase 2 + all JARVIS dependencies...
"%PYTHON_CMD%" -m pip install PySide6 sentence-transformers nvidia-ml-py ultralytics opencv-python matplotlib tqdm faster-whisper pyttsx3 edge-tts sounddevice soundfile psutil pywin32 pyautogui requests ollama playwright

echo.
echo  Step 5: Verifying CUDA...
"%PYTHON_CMD%" -c "import torch; v=torch.__version__; c=torch.cuda.is_available(); g=torch.cuda.get_device_name(0) if c else 'N/A'; print('PyTorch: '+v+' | CUDA: '+str(c)+' | GPU: '+g)"

echo.
echo  [NOTE] If a new venv was created, update your IDE to use:
echo    %PYTHON_CMD%
echo.
goto done

:mode_ollama
cls
color 07
echo.
echo  [JARVIS] Starting Ollama LLM server...
echo.
start "Ollama Server" cmd /k "ollama serve"
echo  Ollama started in a new window.
echo  Recommended models:
echo.
echo    ollama pull llama3.2
echo    ollama pull mistral
echo    ollama pull phi
echo    ollama pull deepseek-coder
echo.
pause
goto menu

:quit
cls
echo.
echo  Goodbye, Sir.
echo.
ping -n 2 127.0.0.1 >nul
exit /b 0

:done
echo.
color 07
echo  --------------------------------------------------------
echo   JARVIS session ended. Press any key to return...
echo  --------------------------------------------------------
pause >nul
goto menu

:done_nopause
color 07
echo  --------------------------------------------------------
echo   Done. Press any key to return to menu...
echo  --------------------------------------------------------
pause >nul
goto menu

:resolve_python
rem -- Prefer GPU-compatible JARVIS venvs over a generic/newer .venv.
if exist "..\jarvis_py312_venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\..\jarvis_py312_venv\Scripts\python.exe"
    exit /b 0
)
if exist "..\jarvis_py311_venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\..\jarvis_py311_venv\Scripts\python.exe"
    exit /b 0
)
if exist "..\jarvis_py310_venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\..\jarvis_py310_venv\Scripts\python.exe"
    exit /b 0
)
rem -- project-level venv (one directory up)
if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\..\.venv\Scripts\python.exe"
    exit /b 0
)
if exist "venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\venv\Scripts\python.exe"
    exit /b 0
)
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\.venv\Scripts\python.exe"
    exit /b 0
)
where python.exe >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python.exe"
    exit /b 0
)
where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)
exit /b 1

:start_ollama_silent
set "OLLAMA_STATUS=not installed"
where ollama >nul 2>&1
if errorlevel 1 exit /b 0

tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if not errorlevel 1 (
    set "OLLAMA_STATUS=already running"
    exit /b 0
)

start "" /min ollama serve
timeout /t 3 /nobreak >nul
set "OLLAMA_STATUS=started automatically"
exit /b 0
