@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python environment is missing. Run setup.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo Python environment is broken or belongs to another PC. Run setup.bat again.
    pause
    exit /b 1
)
if not exist "audio\samples" mkdir "audio\samples"
".venv\Scripts\python.exe" ".\py\app.py" --input ".\audio\samples" --config ".\config.ini" --output-dir ".\output"
set "RUN_RESULT=%ERRORLEVEL%"
if not "%RUN_RESULT%"=="0" echo Transcription failed. Review the error above. If dependencies are missing, run setup.bat.
pause
exit /b %RUN_RESULT%
