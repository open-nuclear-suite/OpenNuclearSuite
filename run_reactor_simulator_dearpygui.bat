@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" "simulators\ReactorPhysicsSimulator\main.py" --dearpygui
if errorlevel 1 pause
endlocal
