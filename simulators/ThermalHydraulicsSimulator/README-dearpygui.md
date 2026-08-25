# Thermal-Hydraulics Simulator — Dear PyGui front end

The canonical launcher preserves the validated projected-RK4 thermal-hydraulics
engine, IF97 property table, event logic, automatic trip/ECCS logic, and axial
hot-channel feedback. Operator actions and fixed-step scheduling pass through
the toolkit-neutral `ThermalHydraulicsGUIBackend`; Dear PyGui handles GPU
rendering and display scheduling.

## Run

```powershell
python -m pip install -r requirements-dearpygui.txt
python simulators/ThermalHydraulicsSimulator/main.py
```

By default, the front end loads the model beside its script in the current
checkout. Use `--model-dir PATH` to test a different model directory. The
former Tkinter interface remains available with `--legacy-tk`.

## Responsiveness design

- The Dear PyGui render loop runs once per display frame.
- The validated engine retains its fixed `0.05 s` physics timestep.
- Physics catches up from a wall-clock accumulator independently of rendering.
- Plots, readouts, controls, alarms, and the plant mimic refresh at 10 Hz.
- The header reports render FPS, physics steps per second, and UI update time.

The responsive interface provides Normal, SBLOCA, LBLOCA, LOFA, LOHS, and SBO
presets; primary and safety controls; automatic trip and ECCS controls; axial
hot-channel coupling; three GPU plot tabs; the plant mimic; alarms; and
performance counters.
