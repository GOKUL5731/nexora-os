@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title JARVIS Phase 2 - Deep Learning Intelligence Layer
color 0B
cls

cd /d "%~dp0"
set "PYTHONUTF8=1"

call :resolve_python
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found. Install Python 3.10-3.12 or create a venv first.
    pause
    exit /b 1
)

echo.
echo  ========================================================
echo   JARVIS Phase 2 - Deep Learning Intelligence Layer
echo   CNN Vision + LSTM Behavior + Multimodal Memory
echo   Hardware: RTX 4050 GPU Accelerated
echo  ========================================================
echo.
echo   Python: %PYTHON_CMD%
echo.

echo  SELECT MODE:
echo  ============
echo  [1] Launch GUI with Phase 2 (Vision + Learning + Memory tabs)
echo  [2] CLI with Phase 2 active
echo  [3] Run Phase 2 self-tests (all 7 modules)
echo  [4] Phase 2 status report
echo  [5] Install Phase 2 dependencies (PyTorch CUDA + DL libs)
echo  [6] Exit
echo.
set /p MODE="Enter choice [1-6]: "

if "%MODE%"=="1" goto GUI
if "%MODE%"=="2" goto CLI
if "%MODE%"=="3" goto TEST
if "%MODE%"=="4" goto STATUS
if "%MODE%"=="5" goto INSTALL
if "%MODE%"=="6" exit /b 0

echo.
echo Invalid choice.
goto END

:GUI
echo.
echo [Phase 2] Launching JARVIS Dashboard with DL layer...
"%PYTHON_CMD%" -X utf8 jarvis_phase2.py
goto END

:CLI
echo.
echo [Phase 2] Starting CLI mode with deep learning active...
"%PYTHON_CMD%" -X utf8 jarvis_phase2.py --cli
goto END

:TEST
echo.
echo [Phase 2] Running self-tests for all 7 modules...
echo  Testing: CNN, VisionTrainer, RNN, Memory, SelfLearn, Prediction, Decision
"%PYTHON_CMD%" -X utf8 jarvis_phase2.py --test
goto END

:STATUS
echo.
echo [Phase 2] Phase 2 status report...
"%PYTHON_CMD%" -X utf8 jarvis_phase2.py --status
goto END

:INSTALL
echo.
echo [Phase 2] Installing Phase 2 dependencies...
echo.
call :ensure_gpu_python
if errorlevel 1 goto END

echo.
echo Step 1: Upgrading pip
"%PYTHON_CMD%" -m pip install --upgrade pip

echo.
echo Step 2: Removing any broken PyTorch build
"%PYTHON_CMD%" -m pip uninstall torch torchvision torchaudio -y 2>nul

echo.
echo Step 3: PyTorch 2.5.1 with CUDA 12.1 support (RTX 4050)
"%PYTHON_CMD%" -m pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo.
    echo [ERROR] PyTorch CUDA install failed.
    goto END
)

echo.
echo Step 4: Deep Learning libraries
"%PYTHON_CMD%" -m pip install -r requirements_phase2.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Phase 2 dependency install failed.
    goto END
)

echo.
echo Step 5: Verifying CUDA
"%PYTHON_CMD%" -c "import torch; print(f'PyTorch: {torch.__version__} | CUDA: {torch.cuda.is_available()} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
echo.
echo Installation complete! Run option [3] to verify all modules.
goto END

:END
echo.
pause
exit /b 0

:resolve_python
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

:ensure_gpu_python
for /f "tokens=2 delims= " %%v in ('"%PYTHON_CMD%" --version 2^>^&1') do set "PY_VER=%%v"
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

echo Detected Python: %PY_VER%
if "%PY_MAJOR%"=="3" (
    if %PY_MINOR% GEQ 10 (
        if %PY_MINOR% LEQ 12 (
            echo [OK] Python %PY_VER% is compatible with the pinned CUDA wheel.
            exit /b 0
        )
    )
)

echo [!] Python %PY_VER% is not compatible with the pinned CUDA 12.1 PyTorch wheel.
echo     Looking for or creating Python 3.10-3.12 venv...

if exist "..\jarvis_py312_venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\..\jarvis_py312_venv\Scripts\python.exe"
    echo [OK] Using existing venv: ..\jarvis_py312_venv
    exit /b 0
)
if exist "..\jarvis_py311_venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\..\jarvis_py311_venv\Scripts\python.exe"
    echo [OK] Using existing venv: ..\jarvis_py311_venv
    exit /b 0
)
if exist "..\jarvis_py310_venv\Scripts\python.exe" (
    set "PYTHON_CMD=%CD%\..\jarvis_py310_venv\Scripts\python.exe"
    echo [OK] Using existing venv: ..\jarvis_py310_venv
    exit /b 0
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -m venv ..\jarvis_py312_venv
    if exist "..\jarvis_py312_venv\Scripts\python.exe" (
        set "PYTHON_CMD=%CD%\..\jarvis_py312_venv\Scripts\python.exe"
        echo [OK] Created venv: ..\jarvis_py312_venv
        exit /b 0
    )

    py -3.11 -m venv ..\jarvis_py311_venv
    if exist "..\jarvis_py311_venv\Scripts\python.exe" (
        set "PYTHON_CMD=%CD%\..\jarvis_py311_venv\Scripts\python.exe"
        echo [OK] Created venv: ..\jarvis_py311_venv
        exit /b 0
    )

    py -3.10 -m venv ..\jarvis_py310_venv
    if exist "..\jarvis_py310_venv\Scripts\python.exe" (
        set "PYTHON_CMD=%CD%\..\jarvis_py310_venv\Scripts\python.exe"
        echo [OK] Created venv: ..\jarvis_py310_venv
        exit /b 0
    )
)

echo [ERROR] Could not find Python 3.10, 3.11, or 3.12.
echo         Install Python 3.12 from https://www.python.org/downloads/ and run this again.
exit /b 1
