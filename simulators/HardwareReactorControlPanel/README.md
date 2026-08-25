# Hardware-Ready Reactor Control Panel

> [!CAUTION]
> **UNTESTED HARDWARE PROTOTYPE — DO NOT ASSUME THE SUGGESTED BUILD IS SAFE OR FUNCTIONAL.**
>
> The physical panel, wiring proposal, component selection, Arduino firmware,
> calibration procedure, and end-to-end serial integration have **not** been
> assembled, commissioned, or tested by this project. They may contain
> electrical, mechanical, firmware, calibration, and human-factors errors. Use
> only an isolated SELV educational mockup after an independent engineering and
> safety review. Never connect any part of this design to reactor, laboratory,
> industrial process-control, protection, or safety equipment.

This is a separate hardware integration edition of the Reactor Physics and
Kinetics Simulator. Its default interface now subclasses the responsive 2.0
PySide6/PyQtGraph reactor window and uses the same GUI-neutral backend, fixed
physics timestep, GPU plots, diagnostics, settings, faults, and SCRAM model.
Physical panel I/O remains isolated on a serial worker thread and panel
commands are translated through a tested backend adapter.

The former Tkinter hardware interface remains available with `--legacy-tk`.

> **Educational use only.** This project is not a reactor protection system,
> safety instrument, plant simulator, or design for connection to real plant
> equipment.

## Quick start

Install the normal project requirements, then the optional serial dependency:

```powershell
python -m pip install -r requirements.txt -r simulators/HardwareReactorControlPanel/requirements-hardware.txt
python simulators/HardwareReactorControlPanel/main.py --no-hardware
python simulators/HardwareReactorControlPanel/main.py --port COM5
```

Windows users may run `run_hardware_reactor_simulator.bat --port COM5`.
If exactly one USB serial device is attached, the port is auto-detected. With
zero or multiple candidates, pass `--port` explicitly. The canonical launcher
`run_reactor_simulator.bat` remains unchanged.

The reference Arduino Mega firmware is in `firmware/reference_panel`. See
[PHYSICAL_PANEL_BUILD_GUIDE.md](PHYSICAL_PANEL_BUILD_GUIDE.md) for the complete
student project plan, wiring, commissioning, and acceptance tests.

## Protocol summary

The link is USB serial at 115200 baud using one UTF-8 JSON object per line.
Every message has protocol version `v: 1`. Inputs are allow-listed and clamped.

```json
{"v":1,"type":"button","name":"scram","value":"pressed","seq":12}
{"v":1,"type":"analog","name":"rod_insertion_pct","value":52.4,"seq":13}
{"v":1,"type":"mode","name":"control_mode","value":"manual","seq":14}
```

The simulator sends a `state` record at 5 Hz containing values and annunciator
states. See `protocol.py` and `hardware_state()` for the authoritative schema.
`rod_insertion_pct` uses the operator convention: 0% fully withdrawn and 100%
fully inserted. The old `rod_position_pct` input remains accepted for prototype
compatibility and is interpreted as percent withdrawn.
