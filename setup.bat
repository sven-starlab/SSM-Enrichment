@echo off
setlocal
cd /d "%~dp0"
echo Setting up WAV Transcript CLI on this computer...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
set "SETUP_RESULT=%ERRORLEVEL%"
echo.
if not "%SETUP_RESULT%"=="0" echo Setup failed. See the error above and setup.log in this folder.
pause
exit /b %SETUP_RESULT%
