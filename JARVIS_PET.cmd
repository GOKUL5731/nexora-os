@echo off
setlocal EnableExtensions

call "%~dp0run_pet.cmd" %*
exit /b %ERRORLEVEL%
