@echo off
setlocal EnableExtensions

title Build NEXORA OS Windows EXE

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

echo ============================================================
echo  Build NEXORA OS Windows EXE
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not installed or not on PATH.
  pause
  exit /b 1
)

echo [1/3] Installing PyInstaller and desktop runtime...
python -m pip install pyinstaller -r "%ROOT%\nexora_os\requirements-desktop.txt"
if errorlevel 1 (
  echo [ERROR] Install failed.
  pause
  exit /b 1
)

echo [2/3] Building frontend assets...
pushd "%ROOT%\nexora_os\frontend"
if not exist node_modules call npm install
call npm run build
if errorlevel 1 (
  popd
  echo [ERROR] Frontend build failed.
  pause
  exit /b 1
)
popd

echo [3/3] Packaging executable...
python -m PyInstaller ^
  --noconfirm ^
  --windowed ^
  --name "NEXORA OS" ^
  --add-data "%ROOT%\nexora_os\frontend\dist;nexora_os\frontend\dist" ^
  --add-data "%ROOT%\nexora_os\requirements.txt;nexora_os" ^
  "%ROOT%\nexora_os\desktop_app.py"

echo.
echo Built app folder:
echo %ROOT%\dist\NEXORA OS
echo.
pause
