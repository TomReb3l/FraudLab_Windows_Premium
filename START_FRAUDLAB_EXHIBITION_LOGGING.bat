@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%LOG_DIR%" (
    echo ERROR: Cannot create logging directory.
    exit /b 1
)
set "LOG_FILE=%LOG_DIR%\fraudlab_startup.log"

>> "%LOG_FILE%" echo ==========================================
>> "%LOG_FILE%" echo FraudLab LOGGING Startup %date% %time%
>> "%LOG_FILE%" echo ==========================================

if not exist ".venv\Scripts\python.exe" (
    >> "%LOG_FILE%" echo ERROR: Exhibition Python missing.
    echo ERROR: Exhibition Python missing.
    exit /b 1
)
if not exist "scripts\exhibition_launcher.py" (
    >> "%LOG_FILE%" echo ERROR: Official launcher missing.
    echo ERROR: Official launcher missing.
    exit /b 1
)

>> "%LOG_FILE%" echo Starting official launcher without Edge kiosk...
".venv\Scripts\python.exe" -B "scripts\exhibition_launcher.py" start --no-browser >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    >> "%LOG_FILE%" echo ERROR: Official launcher startup failed. Browser not opened.
    echo ERROR: Official launcher startup failed. See logs\fraudlab_startup.log.
    exit /b 1
)

>> "%LOG_FILE%" echo Verifying backend health and watchdog...
".venv\Scripts\python.exe" -B "scripts\exhibition_launcher.py" status >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    >> "%LOG_FILE%" echo ERROR: Health or watchdog check failed. Browser not opened.
    echo ERROR: Backend health or watchdog failed. See logs\fraudlab_startup.log.
    exit /b 1
)

>> "%LOG_FILE%" echo Opening local exhibition page in the default browser...
start "" "http://127.0.0.1:8000/"
if errorlevel 1 (
    >> "%LOG_FILE%" echo ERROR: Browser open command failed.
    echo ERROR: Could not open the browser.
    exit /b 1
)
>> "%LOG_FILE%" echo LOGGING startup checks passed.
echo FraudLab LOGGING mode: healthy backend and watchdog; local page requested.
exit /b 0
