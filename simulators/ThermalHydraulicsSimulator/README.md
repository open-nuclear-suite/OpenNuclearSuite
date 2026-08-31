# Thermal-Hydraulics and LOCA Teaching Simulator

The concise publication-style assessment of the major model claims is
[Major-item verification and validation](../../docs/THERMAL_HYDRAULICS_VV_MAJOR_ITEMS.md).

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

Each PWR right-hand-side evaluation publishes matched primary-inventory storage
and boundary rates plus matched fuel--clad--coolant stored-energy and external
power rates. Their residuals, along with any separate correction introduced by
the bounded state projection, are available in state, scenario summaries, and
CSV logs. The energy ledger includes reactor heat generation, steam-generator
and RHR removal, injection enthalpy, and break/PORV/evaporation discharge
enthalpy. It excludes the teaching pressurizer-temperature control state,
which has no declared physical heat capacity or inventory.

The PWR primary side is also resolved into core, hot-leg, cold-leg, and
pressurizer liquid/steam inventories. Their component masses and energies are
normalized after every step to the conserved aggregate primary stores. A
first-order loop momentum balance compares RCP head and buoyancy head with
quadratic loop loss, so pump coastdown and natural-circulation contribution are
dynamic rather than instantaneous control multipliers. The steam-generator
secondary has an explicit water/steam mass store, energy store, pressure,
feedwater flow, and steam flow with independently reported balance residuals.
These states are visible in the maintained PyQtGraph readout and summary and
are included in history exports.

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

PWR reactor protection uses independent teaching-scale high-flux,
high-primary-pressure, low-inventory, low-flow, and coupled thermal-limit
channels. Setpoints and delays are declared in `PWRConstants`; each signal has
its own timer, a cleared signal resets before actuation, and the first completed
trip cause is retained. The low-flow channel has a power permissive so shutdown
natural circulation does not create a new trip demand. These are generic
classroom settings, not plant protection setpoints or voting logic.

In the hot-channel plot, **Thermal limit** is the calculated local CHF or
critical-power threshold, not a temperature. Dividing that threshold by actual
surface heat flux gives DNBR for the PWR channel and the teaching model's
diagnostic CPR margin for the BWR channel. A margin of 1.0 is the modeled limit.

PWR safety injection separates finite passive accumulator discharge, HPSI,
LPSI/reflood, and sump-recirculation paths. The pumped paths use generic
quadratic runout-to-shutoff curves; individual automatic demands have declared
delays, latches, pressure permissives, availability controls, and recovery reset
logic. Recirculation additionally requires an active break and low inventory.
In **Simplified** control mode, the single **Combined ECCS command
(simplified)** is routed through these component curves and the individual
commands are unavailable. In **Advanced** mode, the combined command is
unavailable and separate HPSI, LPSI/reflood, and sump-recirculation controls
and availability switches are exposed. Changing modes clears commands that
become inactive. Turning off **Auto ECCS logic** inhibits automatic
pumped flow without blocking available manual commands or passive accumulator
discharge.

For a normal-operation rod maneuver, the lumped PWR model applies a 30-second
effective rod-motion lag and a bounded teaching-model power-damping term. This
keeps the characteristic xenon/temperature response visible without the large,
slow oscillations produced by an instantaneous lumped reactivity step. Reactor
trips and accident scenarios bypass this maneuver damping.

The PWR model carries four normalized axial power shares and four normalized
vapor-holdup shares. Top-entry rod insertion shifts the power distribution
downward, local void feeds back on the shape, and upward transport moves vapor
holdup toward the outlet. The reconstructed four-zone void distribution has no
independent mass inventory, and axial power shares only redistribute the
existing total reactor heat. The current shape drives the 20-node PWR hot-
channel heat-flux profile and is published in the PyQtGraph readout, summary,
and CSV history exports. This is a reduced spatial teaching surrogate rather
than nodal neutronics or subchannel thermal hydraulics.

## Verification

P1-4 makes every declared PWR transient an executable regression gate. Normal
operation, SBLOCA, LBLOCA, loss of flow, loss of heat sink, and station blackout
are checked at published times against broad normalized response envelopes.
The gates cover power, pressure, inventory, loop flow, void, cladding
temperature, protection state, and applicable injection flows. Every accident
also closes the aggregate primary, resolved-component, and steam-generator
secondary conservation ledgers. The four scripted recoveries must finish in a
declared stable-shutdown class without saturating the primary-inventory upper
projection. See
[PWR_SCENARIO_CALIBRATION.md](../../docs/PWR_SCENARIO_CALIBRATION.md).

P2-1 adds a deterministic transient-analysis harness and ±20% one-at-a-time
screening of influential generic PWR parameters. It compares the normal 0.05 s
timestep with 0.025 s for every accident family and accumulates equation
residuals, state-projection corrections, and secondary balance residuals over
complete runs. The resulting ranking is a data-replacement priority, not a
probability distribution or plant uncertainty statement. See
[PWR_UNCERTAINTY_SENSITIVITY.md](../../docs/PWR_UNCERTAINTY_SENSITIVITY.md).

P2-2 replaces a coherent rated-reference family with public NRC AP1000 data:
thermal power, primary pressure and average/hot/cold temperatures, nominal RCP
and loop head, and steam-generator pressure/inventory. Machine-readable
provenance records the source quantity, conversion, applicability, and every
high-priority parameter intentionally left generic. LOFT timing is retained as
sequence evidence rather than transplanted as commercial-plant actuation data.
See [PWR_PARAMETER_DATA_BASIS.md](../../docs/PWR_PARAMETER_DATA_BASIS.md).

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
