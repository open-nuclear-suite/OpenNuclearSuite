# Open Nuclear Engineering Teaching Suite

A collection of four interactive desktop simulators plus an optional hardware
control-panel edition for teaching introductory
reactor physics, core loading, and light-water-reactor thermal-hydraulics. The applications use
Python, PySide6, PyQtGraph, NumPy, and OpenGL. The former Tkinter interfaces
remain available as compatibility front ends.

> **Teaching software only.** These simplified, lumped-parameter models are not
> suitable for reactor design, licensing, safety analysis, operator training,
> accident prediction, or real plant operation. See
> [Model scope and limitations](docs/MODEL_LIMITATIONS.md).

## Included simulators

| Simulator | Topics | Entry point |
| --- | --- | --- |
| Reactor Physics and Kinetics | Point kinetics, reactivity balance, nonlinear rod worth, Xe/Sm poisoning, source-range startup, feedback, teaching-cycle exposure, load following, trips, and fault injection | `simulators/ReactorPhysicsSimulator/main.py` |
| Hardware Reactor Control Panel | Separate USB-serial integration edition for a student-built physical teaching panel; reuses the reactor physics model | `simulators/HardwareReactorControlPanel/main.py` |
| Thermal-Hydraulics and LOCA | Coolant inventory, pressure, decay heat, heat removal, ECCS, SBLOCA/LBLOCA, loss of flow, loss of heat sink, and station blackout | `simulators/ThermalHydraulicsSimulator/main.py` |
| Subchannel Laboratory | Progressive single-channel correlation comparison, boiling and void models, axial CHF margin, and statistical hot-channel factors | `simulators/SubchannelLaboratory/main.py` |
| Core Loading Simulator | 11 x 11 loading patterns, two-group diffusion, burnup, fuel management, assembly histories, and guided multi-cycle refueling | `simulators/CoreLoadingSimulator/main.py` |

The simulators provide interactive controls, trend plots, classroom scenarios,
and CSV export or logging for post-run analysis.

## Windows requirements

- Windows 10 or Windows 11
- Python 3.9 or newer from [python.org](https://www.python.org/downloads/windows/)
- A local Windows desktop session capable of opening GUI windows

During Python installation, select **Add python.exe to PATH** and keep the
optional Tcl/Tk component enabled. The standard Windows installer includes
Tkinter, which the simulators use for their interfaces.

## Installation

Open **Command Prompt** (`cmd.exe`), then clone the repository and enter its
directory:

```cmd
git clone https://github.com/open-nuclear-suite/OpenNuclearSuite.git
cd OpenNuclearSuite
```

Create a virtual environment:

```cmd
py -m venv .venv
```

Activate it in Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

Install the dependencies:

```cmd
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Alternatively, run the provided setup helper from Command Prompt:

```cmd
setup_windows.bat
```

## Running the simulators

From the repository root in the same activated Command Prompt window:

```cmd
python simulators/ReactorPhysicsSimulator/main.py
```

or:

```cmd
python simulators/ThermalHydraulicsSimulator/main.py
```

or:

```cmd
python simulators/SubchannelLaboratory/main.py
```

or:

```cmd
python simulators/CoreLoadingSimulator/main.py
```

After setup, Windows users can instead double-click
`run_reactor_simulator.bat`, `run_thermal_hydraulics_simulator.bat`,
`run_subchannel_laboratory.bat`, or
`run_core_loading_simulator.bat`.

The optional physical-panel edition has its own dependency and launcher:

> [!CAUTION]
> **The suggested physical hardware build and reference firmware have not been
> assembled, commissioned, or tested by this project.** Treat them only as an
> unverified student-project proposal. Never connect them to real reactor,
> laboratory, process-control, protection, or safety equipment.

```cmd
python -m pip install -r simulators\HardwareReactorControlPanel\requirements-hardware.txt
run_hardware_reactor_simulator.bat --no-hardware
```

See the [hardware panel build guide](simulators/HardwareReactorControlPanel/PHYSICAL_PANEL_BUILD_GUIDE.md)
before constructing or connecting a mockup.

The applications are independent; close one before launching the other if
screen space or system memory is limited.

## Building standalone Windows executables

From PowerShell on Windows, run:

```powershell
.\build_standalone_windows.ps1
```

The script creates one-file, windowed executables for the three simulators and
the explicitly labelled untested hardware-panel edition under
`release\Open-Nuclear-Engineering-Teaching-Suite-2.1.0-Windows`. The release
also includes the license, citation metadata, Windows instructions, and
SHA-256 checksums. End users do not need Python installed.

For faster startup, build folder-based editions instead:

```powershell
.\build_onedir_windows.ps1
```

These are created under
`release\Open-Nuclear-Engineering-Teaching-Suite-2.1.0-Windows-Onedir`.
Each simulator's executable must remain beside its `_internal` folder, but it
starts faster because bundled components do not need to be unpacked on every
launch. The build also creates a ZIP of the complete folder-based release for
distribution.

## First use

1. Start a simulator and wait for the splash screen to close.
2. Select a preset or adjust the available controls.
3. Start or run the simulation and observe the indicators and trend plots.
4. Use CSV export/logging when you want to analyze a run in a spreadsheet.
5. Treat numerical values as qualitative teaching outputs, not engineering
   predictions.

The reactor simulator starts with validated classroom defaults. Its instructor
panel can select bounded timescales and an optional advanced core-physics
profile. The original classroom model remains the startup default. Non-default
model settings are displayed continuously and recorded in CSV
exports; see the [reactor simulator README](simulators/ReactorPhysicsSimulator/README.md).

## Repository layout

```text
.
|-- .github/
|   |-- CODEOWNERS
|   `-- workflows/
|       `-- python-checks.yml
|-- docs/
|   `-- MODEL_LIMITATIONS.md
|-- simulators/
|   |-- CoreLoadingSimulator/
|   |   |-- main.py
|   |   |-- core_loading_thorium_poc_fixed.py
|   |   |-- test_core_model.py
|   |   `-- README.md
|   |-- ReactorPhysicsSimulator/
|   |   |-- main.py
|   |   |-- reactor_teaching_simulator.py
|   |   |-- test_pedagogical_settings.py
|   |   `-- README.md
|   |-- ThermalHydraulicsSimulator/
|   |   |-- main.py
|   |   |-- thermal_hydraulics_simulator.py
|   |   |-- test_thermal_hydraulics_physics.py
|   |   `-- README.md
|   |-- SubchannelLaboratory/
|   |   |-- main.py
|   |   |-- single_channel.py
|   |   |-- chf_correlations.py
|   |   |-- pyqtgraph_handler.py
|   |   |-- test_single_channel.py
|   |   `-- README.md
|-- .gitignore
|-- AUTHORS.md
|-- CITATION.cff
|-- CONTRIBUTING.md
|-- LICENSE
|-- README.md
|-- run_core_loading_simulator.bat
|-- run_reactor_simulator.bat
|-- run_subchannel_laboratory.bat
|-- run_thermal_hydraulics_simulator.bat
|-- SECURITY.md
|-- setup_windows.bat
`-- requirements.txt
```

## Troubleshooting

- **`'py' is not recognized`**: reinstall Python from python.org and select
  **Add python.exe to PATH**, or reopen Command Prompt after installation.
- **`ModuleNotFoundError`**: activate the virtual environment and rerun
  `python -m pip install -r requirements.txt`.
- **`No module named tkinter`**: modify or reinstall Python and ensure the
  **tcl/tk and IDLE** optional feature is selected.
- **No window appears**: run on a local desktop session rather than a headless
  service, notebook, or remote session without desktop access.
- **Small display**: use the scrollable panes and maximize the application
  window.
- **A launcher closes immediately**: open Command Prompt, change to the
  repository directory, and run the `.bat` file there so its error message
  remains visible.

To leave the virtual environment when finished:

```cmd
deactivate
```

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow. Please
report security issues according to [SECURITY.md](SECURITY.md).

## Author and contact

**maxisnote20**

Email: [maxisnote20@gmail.com](mailto:maxisnote20@gmail.com)
GitHub: [open-nuclear-suite](https://github.com/open-nuclear-suite)

For academic collaboration, teaching feedback, or questions about the
simulators, please contact the author.

## Citation

If you use this software in teaching, research, or published work, please cite
it using the metadata in [CITATION.cff](CITATION.cff). GitHub will also display
a **Cite this repository** option.

## License

Copyright (c) 2026 maxisnote20. This project is distributed under the
[MIT License](LICENSE).
