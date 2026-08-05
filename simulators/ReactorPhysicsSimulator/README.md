# Reactor Physics and Kinetics Simulator

The canonical reactor teaching application for exploring point kinetics,
reactivity control, delayed neutrons, iodine/xenon poisoning, decay heat,
thermal feedback, load following, protection trips, and classroom fault
diagnosis.

Run from the repository root with:

```powershell
python simulators/ReactorPhysicsSimulator/main.py
```

Windows users can instead run `run_reactor_simulator.bat` from the repository
root.

For the reproducible equation benchmarks, acceptance criteria, results, and
remaining physical-validation gaps, see
[PHYSICS_VALIDATION.md](PHYSICS_VALIDATION.md).

## Instructor pedagogical settings

The existing classroom-scaled behavior remains the validated default. While
the simulation is paused, open **Instructor: Pedagogical Settings** to select:

| Setting | Available values |
| --- | --- |
| Prompt kinetics | Classroom (`Lambda = 0.080 s`), Intermediate (`0.020 s`), Advanced (`0.005 s`) |
| I-135/Xe-135 timescale | Laboratory demo (`60/90 s` half-times), Extended exercise (`300/450 s`), Reference trend (`21600/32400 s`) |
| Load-follow period | `60-600 s` |
| Core-physics detail | Classroom model (default) or Advanced core physics |
| Initial condition | Full-power equilibrium or subcritical startup |
| Exposure state | Steady classroom, beginning, middle, or end of cycle |

Applying a setting resets the run so delayed-neutron precursor and isotope
states are initialized consistently. The active settings remain visible in the
operator panel and are stored in every exported CSV row. Use **Restore
validated defaults** to return to the standard classroom configuration.

These controls change the model equations and must not be confused with a
wall-clock animation-speed control. Decay-heat timescales remain fixed, and
unbounded custom kinetic constants are intentionally unavailable.

## Advanced core physics profile

The optional advanced profile adds detail without replacing the default model:

- a smooth integral rod-worth curve and position-dependent differential worth;
- a complete reactivity balance separating rod, manual, Doppler, moderator
  temperature, moderator density, void, boron, Xe-135, Sm-149, and cycle terms;
- separate I-135/Xe-135 production and removal with optional Pm-149/Sm-149
  poisoning;
- source-, intermediate-, and power-range instrumentation with logarithmic
  neutron level and an adjustable external source;
- separate fuel Doppler, moderator-temperature, density, and illustrative void
  feedback;
- beginning-, middle-, and end-of-cycle presets with teaching-scaled exposure,
  excess-reactivity loss, and an illustrative boron-letdown target.

Open **Core Physics Diagnostics** for three focused views: reactivity balance
(including a live integral/differential rod-worth plot),
poisons and exposure, and startup instrumentation. This keeps the normal
operator panel uncluttered. The diagnostics are observational except for the
external-source control, which is enabled only under Advanced core physics.

The BOC/MOC/EOC exposure demonstration intentionally advances one effective
full-power day per full-power simulated second. This compression is for a
laboratory-period demonstration and is not plant time.

## Numerical note

The model uses explicit Euler integration with `dt = 0.02 s`. Near the initial
critical state, the fast prompt-mode eigenvalue is approximately
`-beta / Lambda`, giving the scalar stability condition `dt < 2 Lambda / beta`.
All three bounded kinetics presets retain ample linear stability margin at the
current timestep. Any future custom mode would require separate numerical
validation and a conservative timestep policy.

## Scope

This is a simplified, lumped-parameter classroom model with deliberately
adjusted constants and timescales. The advanced profile does not constitute a
spatial core calculation or a validated depletion model. It is not suitable
for reactor design, licensing, safety analysis,
operator qualification, accident prediction, or real plant operation.
