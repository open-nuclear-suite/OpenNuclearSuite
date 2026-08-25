# Reactor Simulator — Dear PyGui front end

This optional comparison front end keeps the validated OpenNuclearSuite
`ReactorModel` physics and routes operator actions through the same
toolkit-neutral `ReactorGUIBackend` as the canonical PyQtGraph interface.
Dear PyGui handles GPU rendering and display scheduling.

## Run

```powershell
python -m pip install -r requirements-dearpygui.txt
python simulators/ReactorPhysicsSimulator/main.py --dearpygui
```

By default, the front end loads the model beside its script in the current
checkout. Use `--model-dir PATH` to test a different model directory. The
former Tkinter interface remains available with `--legacy-tk`.

## Responsiveness design

- The Dear PyGui render loop runs once per display frame.
- The validated model retains its fixed `0.02 s` physics timestep.
- Physics catches up from a wall-clock accumulator without tying itself to UI
  refreshes.
- Plots, readouts, sliders, and the system mimic refresh at 10 Hz.
- The header reports render FPS, physics steps per second, and UI update time.

The responsive handler includes the canonical run, mode, rod, flow, heat-sink,
power-target, boron, detector-noise, manual-reactivity, step, CSV-export, SCRAM,
and complete fault-injection controls.
