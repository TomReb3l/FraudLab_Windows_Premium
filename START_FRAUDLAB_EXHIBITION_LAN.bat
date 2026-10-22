@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%LOG_DIR%" (
    echo ERROR: Cannot create LAN log directory.
    exit /b 1
)
set "LOG_FILE=%LOG_DIR%\fraudlab_lan_startup.log"
>> "%LOG_FILE%" echo ==========================================
>> "%LOG_FILE%" echo FraudLab Universal LAN Startup %date% %time%
>> "%LOG_FILE%" echo ==========================================

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Exhibition Python missing.
    >> "%LOG_FILE%" echo ERROR: Exhibition Python missing.
    exit /b 1
)
if not exist "scripts\exhibition_launcher.py" (
    echo ERROR: Official exhibition launcher missing.
    >> "%LOG_FILE%" echo ERROR: Official launcher missing.
    exit /b 1
)

echo Detecting router network and starting official supervised LAN mode...
".venv\Scripts\python.exe" -B "scripts\exhibition_launcher.py" start --no-browser --lan %*
if errorlevel 1 (
    echo ERROR: Universal LAN startup failed. Check logs\exhibition_launcher.log.
    >> "%LOG_FILE%" echo ERROR: Universal LAN startup failed.
    exit /b 1
)
".venv\Scripts\python.exe" -B "scripts\exhibition_launcher.py" status
if errorlevel 1 (
    echo ERROR: Backend health or watchdog failed. Browser was not opened.
    >> "%LOG_FILE%" echo ERROR: Backend or watchdog failed.
    exit /b 1
)

start "" "http://127.0.0.1:8000/"
if errorlevel 1 (
    echo ERROR: Default browser could not be opened.
    >> "%LOG_FILE%" echo ERROR: Browser open failed.
    exit /b 1
)
>> "%LOG_FILE%" echo Universal LAN startup passed. Local page requested.
echo Universal LAN running. Share the VISITOR URL shown above with devices on the same trusted router network.
exit /b 0
