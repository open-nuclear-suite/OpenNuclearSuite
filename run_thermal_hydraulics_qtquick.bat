@echo off
cd /d "%~dp0"
python simulators\ThermalHydraulicsSimulator\thermal_hydraulics_qtquick.py
if errorlevel 1 pause
