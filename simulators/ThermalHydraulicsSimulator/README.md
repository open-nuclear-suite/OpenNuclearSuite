# Thermal-Hydraulics and LOCA Teaching Simulator

An interactive lumped-parameter teaching application for exploring coupled
reactor power, decay heat, primary coolant inventory and energy, pressurizer
pressure, boiling regimes, CHF, heat removal, ECCS, and selected LWR accident
scenarios.

Run from the repository root with:

```powershell
python simulators/ThermalHydraulicsSimulator/main.py
```

Windows users can instead run `run_thermal_hydraulics_simulator.bat` from the
repository root.

## Main capabilities

- Normal operation, SBLOCA, LBLOCA, LOFA, loss-of-heat-sink, and SBO presets
- Coupled six-group point kinetics and three-group decay heat
- Lumped fuel, cladding, primary coolant mass, and coolant energy states
- Saturated pressurizer pressure response and approximate saturation properties
- Single-phase, nucleate, transition, and film-boiling regimes
- Illustrative flow-, pressure-, and coverage-dependent CHF behavior
- Automatic reactor trip and pressure-dependent ECCS response
- Steam-generator, AFW, PORV, spray, heater, and RHR controls
- Scripted recovery demonstrations and CSV transient logging
- Timestamped event timeline for protection, ECCS, inventory, CHF, boiling,
  thermal-limit, recovery, and scenario transitions

## Verification

Run the focused physics regression checks from the repository root:

```powershell
python -m unittest discover -s simulators/ThermalHydraulicsSimulator -p "test_*.py" -v
```

The tests cover nominal equilibrium, saturation-table consistency, coolant
mass/energy synchronization, ECCS enthalpy transport, CHF transition under
loss of flow, and event-timeline transition and duplicate-suppression behavior.

## Scope

This is a qualitative classroom model, not a design, licensing, operations, or
safety-analysis code. See [`../../docs/MODEL_LIMITATIONS.md`](../../docs/MODEL_LIMITATIONS.md)
for its assumptions and prohibited uses.
