# Contributing

Thank you for helping improve the Open Nuclear Engineering Teaching Suite.

## Development setup

Use Windows Command Prompt (`cmd.exe`) for the documented development workflow:

```cmd
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m compileall -q simulators
```

Run both simulator entry points from the repository root before submitting a
change.

## Change guidelines

- Keep the applications independently runnable.
- Preserve the prominent teaching-only safety disclaimer.
- Document model or parameter changes, including their pedagogical purpose.
- Do not present simplified outputs as validated engineering results.
- Avoid committing generated CSV files, local environments, or cache files.
- Test GUI changes manually on Windows 10 or Windows 11.
- Update the README when setup, dependencies, controls, or file locations
  change.

## Pull requests

Describe the reason for the change, the simulator affected, how it was tested,
and any effect on classroom exercises or model behavior. Screenshots are useful
for visible interface changes.
