@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PET_G_DIR=%SCRIPT_DIR%nexora_os\frontend\public\models\pet-g"
set "RUNNER=%PET_G_DIR%\run_pet_g_blender.ps1"

if not exist "%RUNNER%" (
  echo Pet G Blender runner was not found:
  echo   %RUNNER%
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%RUNNER%" %*
exit /b %ERRORLEVEL%
