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

- Selectable representative PWR and independent BWR plant models

- Normal operation, SBLOCA, LBLOCA, LOFA, loss-of-heat-sink, and SBO presets
- Coupled six-group point kinetics and three-group decay heat
- Lumped fuel, cladding, primary coolant mass, and coolant energy states
- Saturated pressurizer pressure response and approximate saturation properties
- Single-phase, nucleate, transition, and film-boiling regimes
- Illustrative flow-, pressure-, and coverage-dependent CHF behavior
- Automatic reactor trip and pressure-dependent ECCS response
- Latched automatic ECCS demand with recovery hysteresis to prevent threshold chatter
- Steam-generator, AFW, PORV, spray, heater, and RHR controls
- Scripted recovery demonstrations and CSV transient logging
- Deduplicated demo action/recovery log with timestamped control movements
- Timestamped event timeline for protection, ECCS, inventory, CHF, boiling,
  thermal-limit, recovery, and scenario transitions
- Independently scaled reactor-power and decay-heat axes for readable post-trip trends
- A 20-node representative PWR hot-channel view with axial fuel-centre,
  cladding-surface, coolant, saturation, pressure, enthalpy, and quality results
- Axial actual heat flux, Tong W-3 critical heat flux, and DNBR screening curves
- Optional bidirectional axial/lumped coupling for thermal-limit trip, ECCS,
  and post-CHF heat-transfer response
- Accessible scenario summaries and extended transient CSV diagnostics
- GUI-independent physics engine integrated with projected classical RK4
- Bundled pressure-enthalpy IF97 property table with no runtime property-package dependency

## BWR extension status

The responsive PyQtGraph interface includes always-visible, mutually exclusive
**PWR** and **BWR** plant-model radio buttons. PWR
mode retains the existing transient and accident capabilities. The BWR model
is a 37-state R9 source-parameterized feature prototype with explicit core-liquid, core-vapor, downcomer-liquid,
upper-plenum, separator, and steam-dome mass and stored-energy balances. Vessel
pressure is closed against saturated-steam specific volume and total vessel geometry,
mass, and internal energy through a simultaneous saturated flash. It includes direct steam and
feedwater flows, a pump head-flow/density-driving/component-loss recirculation
momentum balance, bulk void,
void-reactivity feedback, and automatic/manual SRV discharge.

The responsive interface substitutes BWR controls and a BWR vessel mimic with
bottom-entry control-rod position when BWR is selected. Initial scenarios and
scripted demonstrations cover recirculation-pump trip, turbine trip/SRV
response, loss-of-feedwater recovery, small-break LOCA, and station blackout.
The BWR safety/support panel includes MSIVs, turbine bypass, RCIC, HPCI, ADS,
LPCI, core spray, shutdown cooling, and a vessel-break input. Injection and
depressurization are pressure dependent. RCIC/HPCI include separate steam-driver
availability and quadratic head-flow curves; LPCI/core spray flow is zero above
generic pump shutoff head. Vessel break flow uses a backpressure-aware,
isentropic homogeneous-equilibrium flashing-nozzle calculation. The equivalent
break area, discharge coefficient, runout flows, and shutoff heads are generic
teaching inputs, not qualified plant curves. Low-level automatic demand stages
high-pressure and low-pressure systems. The display distinguishes collapsed
liquid inventory from a teaching swell-adjusted indicated level and tracks
suppression-pool temperature.
Automatic protection and injection use explicit delays, latched demands, recovery
hysteresis, pressure/level permissives, operator-selectable equipment availability,
and suppression-pool suction limits. Pool mass and energy are integrated, including
SRV/RCIC steam return and safety-system withdrawal.

The generic BWR RPS has independently timed high-flux, high-pressure, low
indicated-level, and guarded fuel-thermal channels. The interface annunciates
the retained initiating cause. ECCS and ADS thresholds, delays, reset
hysteresis, and pressure permissives are declared model constants rather than
embedded literals; automatic ADS also requires an available low-pressure
injection path.

The BWR readout exposes recirculation pump and buoyancy heads together with
core two-phase friction, other single-phase/local loss, acceleration loss, and
the active two-phase friction multiplier. Natural-circulation flow is solved by
the momentum balance rather than imposed as a fixed minimum.

Four dynamic axial zones redistribute total core power and vapor holdup without
duplicating vessel mass or energy. Local void is reconstructed from the conserved
phase inventories, contributes through an importance-weighted void-reactivity
signal, and shifts with flow-dependent upward transport. Bottom-entry rod
insertion and local void feedback reshape axial power. That shape is interpolated
into the 24-node critical-power inspector, and axial power/void shares are visible
in the main BWR readout.

All scripted demonstrations show a declared target end state plus a timestamped
stabilization log of the actual control and safety-system movements. "Recovery"
means reaching that target controlled condition; only the recirculation-trip
demonstration targets a return to power operation.

BWR mode also provides a separate 24-node axial-channel inspector. It marches
pressure and enthalpy, reports equilibrium quality and void, calculates fuel
and cladding temperature profiles, and displays a guarded CISE-style X-L
critical-power trend. Pressure loss includes friction, spacer, gravity, and
acceleration terms. Valid in-range CPR drives a bounded nucleate/transition/
film-boiling heat-transfer factor in both the axial temperature display and the
lumped cladding stored-energy balance; out-of-range CPR remains explicitly
uncoupled. The method and applicability guards are documented in the
[BWR critical-power method](../../docs/BWR_CRITICAL_POWER_METHOD.md). It remains
a teaching screening method rather than a licensed fuel-design limit.

Capability maturity is explicit rather than implied:

| BWR capability | Status |
|---|---|
| Vessel balances and direct cycle | Implemented |
| Recirculation head balance and reference-leg lag | Implemented |
| Safety latches/delays/availability and suppression-pool balance | Implemented |
| Void feedback, component curves, and level calibration | Teaching surrogate |
| Axial-channel inspector | Diagnostic only |
| Upper-plenum/separator storage | Implemented |
| Separator transport and level indication | Teaching surrogate |
| Guarded open X-L critical-power screening | Diagnostic only |
| Fuel-vendor/validated safety-limit MCPR | Not implemented |

The sequencing authority and exit criteria are recorded in the
[BWR development roadmap](../../docs/BWR_DEVELOPMENT_ROADMAP.md). Each completed
BWR step also publishes mass- and energy-balance residuals, and displayed flows
come from the same final right-hand-side evaluation used by the integrator.
The recirculation slider commands pump speed rather than core flow; the interface
shows pump, buoyancy, and friction heads alongside geometry-derived collapsed and
reference-leg-adjusted indicated levels.

R7 revalidated broad regression envelopes for normal operation, recirculation
trip, turbine trip, loss of feedwater, small-break LOCA, and station blackout;
see the [BWR scenario calibration basis](../../docs/BWR_SCENARIO_CALIBRATION.md).
The three recovery demonstrations also have executable numerical end-state
gates. These are generic teaching-surrogate checks, not plant validation.

R8 adds deterministic timestep and plus/minus 20% local-sensitivity screening.
After R9 replaced the supported hydraulic data, reference-leg/level trip timing
and void reactivity are the largest remaining screened dependencies. See
[BWR uncertainty and sensitivity screening](../../docs/BWR_UNCERTAINTY_SENSITIVITY.md).

R9 replaces the supported rated-state, effective core pressure-drop, RCIC/HPCI
operating-point, and steam-driver cutoff inputs with public OECD/NEA and NRC
data. Unsupported coefficients remain explicitly generic; see the
[BWR public parameter-data basis](../../docs/BWR_PARAMETER_DATA_BASIS.md).

## Numerical and property foundation

The GUI delegates continuous state evolution to `thermal_hydraulics_engine.py`.
The engine evaluates a side-effect-free right-hand side four times per classical
RK4 step; trips, controls, event logging, and history updates occur only after
the completed step. State projection preserves the declared classroom bounds
for power, temperatures, inventory, void fraction, and pressurizer state.

Runtime water properties come from `data/if97_ph_table.npz`, covering
0.1--20 MPa and 100--3600 kJ/kg. The table was generated with CoolProp's
`IF97::Water` backend from the IAPWS-IF97 industrial formulation. The simulator
uses bilinear pressure-enthalpy interpolation in single-phase regions and
quality-based mixture relations inside the saturation dome. Out-of-domain
queries fail explicitly rather than silently extrapolating.

CoolProp is a generation-only dependency. End users need only the normal
NumPy-based runtime requirements. Developers can regenerate the checked-in
table with:

```powershell
python simulators/ThermalHydraulicsSimulator/tools/generate_if97_tables.py
```

Property provenance follows IAPWS R7-97(2012). The runtime design is informed
by the IAPWS G13-15 table-lookup guideline, but uses compact bilinear
interpolation rather than claiming a complete SBTL implementation.
See [PROPERTY_TABLES.md](PROPERTY_TABLES.md) for the precise grid, reproduction
instructions, interpolation policy, and verification tolerances.

## Representative hot channel

The **HOT CHANNEL** button opens two axial profiles, a transient response plot,
a screen-reader-friendly text summary, and a vertically and horizontally
scrollable numerical table. Fuel
centre temperature has its own left scale; clad, bulk-coolant, and saturation
temperatures use an independently autoscaled right axis so their axial curvature
remains visible. The reduced-order channel uses a
3.66 m heated length divided into 20 control volumes, a 12.60 mm square pitch,
a 9.50 mm rod outside diameter, 0.38 kg/s nominal channel flow, a normalized
chopped-sine axial power shape, and a 1.15 radial hot-channel factor. It marches
pressure and coolant enthalpy from the inlet and queries the bundled IF97 table
at each node. Declared fuel, gap, cladding, and coolant thermal resistances then
produce cladding-surface and fuel-centre temperatures.

With **Couple axial hot channel** selected, the channel receives current power,
pressure, coolant temperature, inventory, pump, LOCA-break, and ECCS conditions.
Its held peak cladding temperature and minimum valid DNBR feed back to the
lumped model's automatic-trip, automatic-ECCS, and boiling heat-transfer paths.
The channel is refreshed every 0.25 simulation seconds and its feedback is held
constant through each RK4 step, preserving a side-effect-free integrator. The
checkbox can disable this feedback for teaching comparisons while leaving the
diagnostic display active. Geometry and heat-transfer coefficients remain
representative teaching inputs, not a particular fuel design. Equilibrium
two-phase properties are reported with a warning. A second plot compares actual
surface heat flux with the Tong W-3 uniform-flux CHF estimate and shows local
DNBR on its own right axis. The numerical table reports equilibrium quality,
actual heat flux, CHF, and DNBR at every node. The minimum in-range DNBR and its
axial position are included in the text summary.

After a reactor trip, the heat-flux and DNBR axes retain their last pre-trip
reference scales. Falling actual heat flux therefore remains comparable with
its full-power value instead of being enlarged by autoscaling; very large DNBR
values are clipped rather than forcing useful curves off scale. The transient
plot records peak fuel-centre, peak clad-surface, and coolant-outlet temperatures
over the latest 40 simulation seconds. The summary also states whether peak
cladding temperature is rising, falling, or approximately steady.

The complete hot-channel window has an outer vertical scrollbar so the table
remains reachable on shorter displays. The mouse wheel, Page Up, Page Down,
Home, and End keys scroll the window; the table retains its own horizontal and
vertical scrollbars.

The W-3 implementation follows the equation and published applicability ranges
reproduced in the US technical report
[TID-25887](https://www.osti.gov/servlets/purl/4629988): 1000--2300 psia,
1--5 million lb/(h ft2), equilibrium quality -0.25--0.15, and hydraulic
diameter 0.2--0.7 inches. The code returns an unavailable value rather than
extrapolating outside those limits. It is a transparent screening calculation;
non-uniform-flux, spacer-grid, heated-perimeter, bundle-specific, and statistical
design-limit corrections are not applied. Crossflow and subchannel mixing also
remain outside the model.

The **SCENARIO SUMMARY** button gives a text report of elapsed time, coupling
state, peak lumped and axial temperatures, minimum inventory and pressure,
minimum in-range W-3 DNBR, trip state, and event count. CSV logs include those
axial metrics plus valid-node count, effective ECCS fraction, and break, PORV,
and evaporation inventory-loss rates.

## Runtime responsiveness

Physics integration is separated from display work. The main dashboard redraws
at no more than 10 Hz and the heavier hot-channel plots/table at no more than
4 Hz; numerical substeps continue at their configured timestep. Above 1x speed,
the diagnostic axial-channel interval is scaled with simulation speed so it
remains capped near four solves per wall-clock second instead of consuming the
GUI event loop at 5x or 10x. Axial states
that temporarily leave the property/correlation domain during a severe LOCA are
cached as unavailable and retried at the normal 0.25 s channel interval instead
of on every RK4 substep. History and event collections remain bounded at 1600
samples and 250 events respectively.

The process controls remain manual. **Auto ECCS logic** / **Auto BWR safety
systems** and **Auto reactor trip** enable protection responses rather than a
full-power automatic plant controller. The BWR main-steam and feedwater demand
sliders do, however, retain simplified fast inner pressure and vessel-inventory
regulators. These represent normal valve/flow control loops and allow a control-
rod maneuver to reach a stable part-power state instead of creating a spurious
pressure and level mismatch. In BWR mode, an unchecked availability box blocks
both automatic and manual flow from that system; its command slider is disabled
to show that the command cannot take effect.

In the hot-channel plot, **Thermal limit** is the calculated local CHF or
critical-power threshold, not a temperature. Dividing that threshold by actual
surface heat flux gives DNBR for the PWR channel and the teaching model's
diagnostic CPR margin for the BWR channel. A margin of 1.0 is the modeled limit.

Automatic ECCS demand is latched while a LOCA remains active. It can increase
from 35% to 85% or 100% as conditions deteriorate, but it does not repeatedly
switch off when inventory crosses a single threshold. Automatic clearing
requires the break to be isolated and generous recovery margins in pressure,
inventory, cladding temperature, and DNBR. Turning off **Auto ECCS logic** still
clears the automatic demand immediately.

## Verification

Run the focused physics regression checks from the repository root:

```powershell
python -m unittest discover -s simulators/ThermalHydraulicsSimulator -p "test_*.py" -v
```

The tests cover IF97 generation references, off-grid interpolation error,
nominal equilibrium, saturation-table consistency, coolant
mass/energy synchronization, ECCS enthalpy transport, CHF transition under
loss of flow, RK4 timestep refinement, and event-timeline transition and
duplicate-suppression behavior. Hot-channel checks cover exact axial energy
balance, temperature ordering, power/flow sensitivities, and grid refinement.
Chunk 3 checks additionally cover a W-3 reference point and unit conversion,
correlation-domain rejection, axial DNBR resolution, and the expected reduction
in minimum DNBR as power increases.
Chunk 4 checks exercise axial-to-lumped CHF/ECCS feedback, ECCS inlet cooling,
LOCA flow bypass, CSV schema integrity, scenario bounds, RK4 timestep
refinement, axial-grid refinement, and exact hot-channel enthalpy balance.

## Scope

This is a qualitative classroom model, not a design, licensing, operations, or
safety-analysis code. See [`../../docs/MODEL_LIMITATIONS.md`](../../docs/MODEL_LIMITATIONS.md)
for its assumptions and prohibited uses.
