@echo off
cd /d "%~dp0"
python simulators\ThermalHydraulicsSimulator\thermal_hydraulics_pyqtgraph.py
if errorlevel 1 pause
