# Open Nuclear Engineering Teaching Suite

A pair of interactive desktop simulators for teaching introductory reactor
physics and light-water-reactor thermal-hydraulics. Both applications use
Python, Tkinter, NumPy, and Matplotlib.

> **Teaching software only.** These simplified, lumped-parameter models are not
> suitable for reactor design, licensing, safety analysis, operator training,
> accident prediction, or real plant operation. See
> [Model scope and limitations](docs/MODEL_LIMITATIONS.md).

## Included simulators

| Simulator | Topics | Entry point |
| --- | --- | --- |
| Reactor Physics and Kinetics | Point kinetics, reactivity, boron, iodine/xenon, decay heat, thermal feedback, load following, trips, and fault injection | `simulators/reactor_teaching_simulator.py` |
| Thermal-Hydraulics and LOCA | Coolant inventory, pressure, decay heat, heat removal, ECCS, SBLOCA/LBLOCA, loss of flow, loss of heat sink, and station blackout | `simulators/thermal_hydraulics_simulator.py` |

Both simulators provide interactive controls, trend plots, classroom scenarios,
and CSV export or logging for post-run analysis.

## Windows requirements

- Windows 10 or Windows 11
- Python 3.9 or newer from [python.org](https://www.python.org/downloads/windows/)
- A local Windows desktop session capable of opening GUI windows

During Python installation, select **Add python.exe to PATH** and keep the
optional Tcl/Tk component enabled. The standard Windows installer includes
Tkinter, which both simulators use for their interfaces.

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
python simulators/reactor_teaching_simulator.py
```

or:

```cmd
python simulators/thermal_hydraulics_simulator.py
```

After setup, Windows users can instead double-click
`run_reactor_simulator.bat` or `run_thermal_hydraulics_simulator.bat`.

The applications are independent; close one before launching the other if
screen space or system memory is limited.

## First use

1. Start a simulator and wait for the splash screen to close.
2. Select a preset or adjust the available controls.
3. Start or run the simulation and observe the indicators and trend plots.
4. Use CSV export/logging when you want to analyze a run in a spreadsheet.
5. Treat numerical values as qualitative teaching outputs, not engineering
   predictions.

## Repository layout

```text
.
|-- .github/
|   |-- CODEOWNERS
|   `-- workflows/
|       `-- python-checks.yml
|-- assets/
|   `-- UTM.logo.png
|-- docs/
|   `-- MODEL_LIMITATIONS.md
|-- simulators/
|   |-- reactor_teaching_simulator.py
|   `-- thermal_hydraulics_simulator.py
|-- .gitignore
|-- AUTHORS.md
|-- CITATION.cff
|-- CONTRIBUTING.md
|-- LICENSE
|-- README.md
|-- run_reactor_simulator.bat
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
- **Logo is missing**: keep `assets/UTM.logo.png` in its documented location.
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

**Mohsin Mohd Sies**  
Nuclear Engineering Program  
Faculty of Chemical and Energy Engineering  
Universiti Teknologi Malaysia  
Email: [mohsin.sies@gmail.com](mailto:mohsin.sies@gmail.com)  
GitHub: [open-nuclear-suite](https://github.com/open-nuclear-suite)

For academic collaboration, teaching feedback, or questions about the
simulators, please contact the author.

## Citation

If you use this software in teaching, research, or published work, please cite
it using the metadata in [CITATION.cff](CITATION.cff). GitHub will also display
a **Cite this repository** option.

## License

Copyright (c) 2026 Mohsin Mohd Sies. This project is distributed under the
[MIT License](LICENSE).
