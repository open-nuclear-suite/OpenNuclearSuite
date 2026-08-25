# Reactor Physics and Kinetics Simulator

The canonical reactor teaching application for exploring point kinetics,
reactivity control, delayed neutrons, iodine/xenon poisoning, decay heat,
thermal feedback, load following, protection trips, and classroom fault
diagnosis.

Run from the repository root with:

```powershell
python simulators/ReactorPhysicsSimulator/main.py
```

The default interface uses native PySide6 widgets and GPU-accelerated
PyQtGraph plots. It keeps physics integration on the model's fixed 0.02 s
timestep, refreshes controls and plots at 10 Hz, and schedules display frames
independently. The complete Dear PyGui interface remains available for
comparison with `--dearpygui`, and the original Tkinter interface with
`--legacy-tk`.

Install the desktop dependencies with:

```powershell
python -m pip install -r requirements.txt
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
| Prompt kinetics | Classroom (`Lambda = 0.080 s`), Intermediate (`0.020 s`), Advanced (`0.005 s`), or Representative LWR (`2.0e-5 s`, 3000 MWth reference) |
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

## SCRAM response

Normal operation retains the selected classroom or representative kinetics
preset. A SCRAM switches the shutdown transient to a representative `2e-5 s`
prompt-neutron generation time and inserts an independent protection-bank
worth to `-5000 pcm` over one second. Six delayed-neutron groups produce the
post-trip fission-power tail, while the existing decay-heat groups remain
independent and continue to generate heat after neutron power collapses.

The partial-SCRAM fault limits protection-bank insertion and the stuck-rod
fault prevents it, so fault demonstrations continue to affect shutdown
performance. These are transparent representative teaching parameters, not a
plant-specific protection-system or shutdown-margin model.

## Representative LWR kinetics and power profile

The optional **Representative LWR** kinetics preset retains normalized power
internally while declaring 100% power as 3000 MWth. The operator readout and
CSV export therefore report both percent power and MWth. It uses fourth-order
Runge-Kutta integration with automatic internal substeps selected from the
fast prompt-mode timescale.

The same profile replaces the legacy temperature-target response with an
explicit three-node MW/MJ energy balance. Its declared effective parameters
are:

| Quantity | Teaching reference |
| --- | ---: |
| Fuel heat capacity | 160 MJ/K |
| Cladding heat capacity | 180 MJ/K |
| Coolant heat capacity | 900 MJ/K |
| Fuel / clad / direct-coolant deposition | 97% / 2% / 1% |
| Fuel-to-clad conductance at rated flow | 20.786 MW/K |
| Clad-to-coolant conductance at rated flow | 37.125 MW/K |
| Heat-removal conductance at rated flow and sink | 50 MW/K |

At the declared 565/425/345/285 C full-power equilibrium, the model transfers
2910 MW from fuel to clad, 2970 MW from clad to coolant, and removes 3000 MW.
Flow changes scale the two internal conductances and the heat-removal path;
heat-sink changes scale the heat-removal path. CSV output records all three
heat flows and a numerical energy-balance residual.

This is a reference model, not a plant specification. The effective thermal
inventories and conductances are transparent teaching parameters selected to
reproduce the declared equilibrium; they are not taken from a particular 3000
MWth plant. Poison yields, flow and heat-sink percentages, equipment curves,
and trip setpoints remain classroom models. Dimensional units and conservation
do not make the resulting temperatures or equipment response plant-valid.

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

The operator-facing control-rod scale reports **percent inserted**: 0% means
fully withdrawn and 100% means fully inserted. The internal physics retains its
withdrawn-position coordinate to preserve the established rod-worth equations.
CSV output retains `rod_position_pct` for backward compatibility and adds
`rod_insertion_pct` with the operator-facing convention.

The BOC/MOC/EOC exposure demonstration intentionally advances one effective
full-power day per full-power simulated second. This compression is for a
laboratory-period demonstration and is not plant time.

## Numerical note

The model uses explicit Euler integration with `dt = 0.02 s`. Near the initial
critical state, the fast prompt-mode eigenvalue is approximately
`-beta / Lambda`, giving the scalar stability condition `dt < 2 Lambda / beta`.
All three legacy bounded kinetics presets retain ample linear stability margin
at the current timestep during normal operation. SCRAM transients use the same
RK4 automatic-substep policy as the Representative LWR preset so the faster
shutdown-only prompt timescale is resolved safely. Any future custom mode
would require separate numerical validation and a conservative timestep
policy.

The Representative LWR preset is intentionally different: its realistic-scale
prompt generation time makes a single 0.02 s explicit-Euler step unsuitable.
The simulator consequently subdivides each outer step and integrates the six-
group equations with RK4. Normal runs use approximately 33 kinetics substeps
per outer step. The legacy presets retain their original Euler implementation
to preserve classroom-default regression behavior.

## Scope

This is a simplified, lumped-parameter classroom model with deliberately
adjusted constants and timescales. The advanced profile does not constitute a
spatial core calculation or a validated depletion model. It is not suitable
for reactor design, licensing, safety analysis,
operator qualification, accident prediction, or real plant operation.
