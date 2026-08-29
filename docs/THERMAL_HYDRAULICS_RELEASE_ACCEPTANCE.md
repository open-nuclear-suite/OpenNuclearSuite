# Thermal-hydraulics R9 release-candidate acceptance

## Candidate identity

- Prepared: 2026-08-29
- Branch: `main`
- Starting repository revision: `deacfa8`
- Candidate state: consolidated release commit; no release tag created
- Automated result: 111 tests passing
- Baseline snapshots: `docs/baselines/thermal_hydraulics_r9_baseline.csv`

`CODEX_HANDOFF.md` is an unrelated pre-existing untracked file and is excluded
from this release candidate. A future commit should stage explicit paths rather
than using an indiscriminate `git add .`.

## Included work

- Independent selectable PWR/BWR model boundary and responsive PyQtGraph UI.
- BWR-specific controls, mimic, rod indication, hot-channel inspector, scenarios,
  demonstrations, action log, and safety-system availability controls.
- R1-R6 thermodynamic, hydraulic, heat-transfer, protection, and reduced axial
  remediations.
- R7 transient and recovery endpoint regression gates.
- R8 timestep, conservation-residual, and local-sensitivity screening.
- R9 public parameter provenance and source-backed rated-state, effective core
  pressure-loss, and RCIC/HPCI operating-point replacements.

The candidate remains a teaching surrogate and is prohibited for design,
licensing, operator qualification, or safety analysis.

## Automated reproduction

From `simulators/ThermalHydraulicsSimulator`:

```powershell
python -m py_compile bwr_plant_model.py bwr_calibration.py bwr_uncertainty.py bwr_parameter_basis.py plant_models.py thermal_hydraulics_gui_backend.py
python -m unittest discover
```

Expected result: 111 tests, all passing. The CSV is a reproducibility snapshot,
not an additional acceptance envelope; authoritative ranges remain in
`bwr_calibration.py`.

## Acceptance follow-up — 2026-08-29

- High-speed axial diagnostics are wall-clock limited above 1x so 5x/10x no
  longer multiply the most expensive GUI-side calculation rate.
- Instrumentation noise and simulation speed now remain the final two controls
  in Safety / Support for both plant models.
- Unavailable BWR injection systems now disable their corresponding manual
  command sliders as well as inhibiting modeled automatic and manual flow.
- A 15% BWR rod insertion now reaches a damped part-power equilibrium instead
  of developing a spurious minute-scale overpower oscillation. Simplified inner
  pressure/level regulation and a BWR-specific fuel thermal time constant are
  covered by a dedicated rod-step regression gate.

These items remain subject to the interactive checks below on the target display.

## Step 2 — interactive acceptance checklist

Launch from the repository root:

```powershell
python simulators/ThermalHydraulicsSimulator/main.py
```

Record pass/fail and any observation for each item:

- [ ] Application opens without an exception and remains responsive at idle.
- [ ] PWR and BWR radio buttons are both visible and mutually exclusive.
- [ ] Resizing the left pane makes its sliders and labels expand/shrink without
      clipping, overlap, or inaccessible controls.
- [ ] PWR mode exposes its existing primary, secondary, and safety controls.
- [ ] BWR mode exposes recirculation, feedwater, main-steam/MSIV, bypass, SRV,
      RCIC, HPCI, ADS, LPCI, core-spray, shutdown-cooling, and break controls.
- [ ] Switching PWR → BWR → PWR resets to a valid equilibrium and does not mix
      plant-specific controls, scenarios, histories, or mimic labels.
- [ ] The BWR mimic visibly contains bottom-entry control rods and their motion
      follows the rod command/scram state.
- [ ] The BWR hot-channel inspector opens and displays axial power, void,
      pressure loss, heat flux, CPR validity, temperatures, and limiting zone.
- [ ] Each plant's scenario selector contains only scenarios valid for that
      plant and each selected scenario begins without a UI exception.
- [ ] Run all three BWR demonstrations; the recovery display lists each staged
      operator/automatic action without duplicate entries.
- [ ] Recirculation recovery finishes in return-to-power mode without a trip.
- [ ] Turbine-trip recovery finishes with pressure controlled and reactor shut down.
- [ ] Loss-of-feedwater recovery restores full feedwater and ends with inventory
      recovering in stable-shutdown mode.
- [ ] Safety-system availability toggles visibly inhibit their corresponding
      modeled flows.
- [ ] At 5× and 10× speed, slider dragging, pane resizing, plots, readouts, and
      mimic animation remain acceptably responsive.
- [ ] Pause/resume, reset, CSV logging, hot-channel window close/reopen, and
      application shutdown work without hangs or tracebacks.

## Acceptance disposition

Do not commit or tag until the interactive checklist is completed. If it passes,
the recommended commit title is:

`Add source-parameterized BWR thermal-hydraulics teaching model`

If an item fails, record the exact plant, scenario/demo, elapsed simulation time,
speed multiplier, window size, and visible symptom before changing the candidate.
