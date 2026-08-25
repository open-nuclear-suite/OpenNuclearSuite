# Thermal Hydraulics GUI comparison

These front ends use the same `ThermalHydraulicsGUIBackend`, fixed `0.05 s`
physics step, and 10 Hz display-data refresh. The full-featured PyQtGraph
version is the canonical launcher; Dear PyGui remains available with
`main.py --dearpygui` for comparison.

## Install

```powershell
python -m pip install -r requirements-gui-comparison.txt
```

## Qt Quick + Qt Graphs

```powershell
python simulators/ThermalHydraulicsSimulator/thermal_hydraulics_qtquick.py
```

This version uses the Qt Quick GPU scene graph and Qt Graphs. Its Hot Channel
button opens a genuine native secondary QML `Window` that shares the live
backend.

## PySide6 Widgets + PyQtGraph

```powershell
python simulators/ThermalHydraulicsSimulator/thermal_hydraulics_pyqtgraph.py
```

This version uses conventional native widgets and PyQtGraph with OpenGL
enabled. It includes the complete operator controls, scenario tools, event and
alarm displays, plant mimic, CSV export, engineering plots, and native hot
channel window from the Dear PyGui interface.

For a useful comparison, drag sliders continuously at normal and high
simulation load, resize the splitter and main window, open and move Hot
Channel, switch scenarios, and watch plot smoothness for at least 30 seconds.
