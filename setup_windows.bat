@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher was not found.
    echo Install Python 3.9 or newer from https://www.python.org/downloads/windows/
    echo Select "Add python.exe to PATH" during installation.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python virtual environment...
    py -m venv .venv
    if errorlevel 1 exit /b 1
)

echo Installing simulator dependencies...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Setup complete.
echo Run run_reactor_simulator.bat, run_thermal_hydraulics_simulator.bat,
echo or run_core_loading_simulator.bat.
endlocal
