@echo off
cd /d "%~dp0"
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    py -3.12 launch.py patient
    if errorlevel 1 pause
    exit /b
)
py -3.11 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    py -3.11 launch.py patient
    if errorlevel 1 pause
    exit /b
)
py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    py -3.13 launch.py patient
    if errorlevel 1 pause
    exit /b
)
echo Install Python 3.12 or 3.11.
pause
