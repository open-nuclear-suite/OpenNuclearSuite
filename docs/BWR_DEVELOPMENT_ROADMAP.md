# BWR development roadmap and phase guardrail

This file is the persistent sequencing authority for the BWR extension. Before
adding a BWR feature, compare it with the active phase below. If a request skips
ahead, flag the deviation and decide explicitly whether to defer it or revise
the roadmap before implementation.

## Phase A — consolidation and contracts (complete)

- Use stable `BWRPlantModel`, `BWRState`, and `BWRControlInputs` names.
- Keep PWR and BWR state/control contracts separate.
- Publish feature maturity as implemented, teaching surrogate, diagnostic only,
  or not implemented.
- Publish mass- and energy-balance residuals from every completed BWR step.
- Ensure displayed flows are the exact flows used by the integrator.
- Keep documentation, state count, metadata, and tests synchronized.

Exit criterion: all items above are implemented and the complete regression
suite passes. Completed with 60 passing tests on 2026-08-28.

## Remediation R1 — thermodynamic and phase foundation (complete)

The original Phase B/C completion claims are withdrawn. Software balance
ledgers passed, but pressure, steam energy, phase inventory, void, and level
were not solved on one thermodynamic manifold.

- Conserve total vessel fluid mass and internal energy as primary quantities.
- Solve pressure, saturation state, vapor mass, liquid mass, and fixed volume
  simultaneously.
- Make void and swell consequences of phase inventory rather than independent
  relaxation states.
- Couple flashing/condensation and separator transport without an arbitrary
  steam-generation cap.
- Require closure at every RHS evaluation plus timestep-refinement tests.

Completed with a simultaneous saturated M-U-V flash, conserved phase
inventories, phase-volume-derived void, explicit core-vapor transport, closure
diagnostics, and refinement tests.

## Remediation R2 — break and injection hydraulics (complete)

- Replace pressure multipliers with explicit pump head-flow relationships.
- Separate steam-driver permissives for RCIC/HPCI from hydraulic shutoff head.
- Enforce suppression-pool suction inventory and pressure boundaries.
- Replace square-root break flow with a phase-aware, backpressure-aware critical
  discharge model and publish the choking state.
- Keep coefficients generic and clearly outside plant-qualified safety use.

Implemented basis: generic quadratic pump curves use zero-differential runout
flow and explicit vessel-to-pool shutoff head. The break uses a one-dimensional,
adiabatic, isentropic homogeneous-equilibrium flashing-nozzle calculation over
the bundled water-property table. This is a physically based classroom
screening model; discharge area, coefficient, and pump curves remain generic
inputs requiring plant data before any plant-specific use.

Completed with published head margins and break choking diagnostics, focused
transition tests, conservation regression, and the complete simulator test suite.

## Remediation R3 — fuel/cladding heat transfer and boiling crisis (complete)

- Preserve explicit fuel and cladding stored-energy balances.
- Make fuel-to-clad conductance temperature dependent within declared bounds.
- Couple clad-to-coolant heat removal to flow and boiling regime.
- Allow only guarded, in-range axial critical-power results to initiate
  transition- and film-boiling degradation.
- Publish heat-transfer regime, degradation factor, and coupling validity.
- Never interpret an out-of-range critical-power correlation as dryout physics.

Implemented basis: the axial channel and lumped vessel share a bounded teaching
boiling curve. Valid CPR at or above one retains nucleate-boiling heat transfer;
CPR from 1.0 to 0.8 smoothly enters transition boiling; lower valid CPR applies
a film-boiling/dryout conductance. Invalid correlation states are explicitly
reported as unassessed two-phase conditions without extrapolation.

Completed with axial and lumped coupling, visible regime/factor diagnostics,
validity guards, directional heating tests, and full-suite regression.

## Remediation R4 — recirculation and two-phase loop hydraulics (complete)

- Replace the single quadratic loop-loss term with auditable components.
- Represent core two-phase friction, single-phase/local losses, acceleration
  loss, pump head-flow behavior, and density-difference driving head.
- Calculate natural circulation from the momentum balance rather than imposing
  a minimum natural-circulation flow.
- Publish every head component and the two-phase friction multiplier.
- Retain generic reference calibration until plant geometry and pump data exist.

Implemented basis: the core friction term uses the open Lottes-Flinn liquid-only
two-phase multiplier, other loop losses retain a single-phase quadratic form,
and acceleration head follows the homogeneous mixture specific-volume rise.
Natural-circulation driving head follows the core/downcomer density difference.
The recirculation pump uses a quadratic head-flow/speed curve calibrated to the
existing nominal operating point.

Completed with component diagnostics in the interface, monotonicity and nominal
closure tests, natural-circulation coastdown regression, and the full suite.

## Remediation R5 — protection, actuation, and permissives (complete)

- Replace shared/hard-coded trip logic with declared generic BWR channels.
- Give high flux, high pressure, low indicated level, and guarded thermal-limit
  signals independent timers.
- Latch reactor trip and publish the initiating channel rather than merely
  reporting a generic trip flag.
- Drive ECCS initiation from indicated level and declared delays/setpoints.
- Require an available low-pressure injection path before automatic ADS.
- Keep recovery reset hysteresis explicit and configurable.

Implemented basis: all generic teaching setpoints, delays, pressure permissives,
and reset settings are fields of `BWRConstants`. RPS channels are independently
timed and their first completed cause is retained for annunciation. RCIC, HPCI,
LPCI, core spray, and ADS use the modeled indicated-level channel; pump curves
remain the final hydraulic flow permissive.

Completed with independent-channel timing and reset tests, ADS availability
tests, visible cause annunciation, scenario regression, and the full suite.

## Remediation R6 — reduced axial spatial dynamics (complete)

- Add dynamic axial power-shape and vapor-holdup distributions at interactive cost.
- Redistribute existing total power and core vapor rather than adding duplicate
  mass or energy inventories.
- Reconstruct local void from conserved core liquid/vapor phase inventories.
- Use an importance-weighted axial void signal for reactivity feedback.
- Represent bottom-entry control-rod and local void effects on axial power shape.
- Feed the dynamic power shape into the 24-node critical-power inspector.
- Publish axial power, axial void, and limiting-zone diagnostics.

Implemented basis: four normalized axial power shares and four normalized vapor
holdup shares add eight dynamic states, increasing the BWR contract from 29 to
37 states. Vapor holdup follows upward cumulative generation with a flow-scaled
transport time; power shape follows bottom-entry rod attenuation and local void
feedback. These normalized states cannot alter total vessel mass or energy.

Completed with normalization, spatial-feedback, rod-shape, moving-peak,
deposited-power, timestep-refinement, scenario-envelope, and full-suite tests.

## Remediation R7 — post-remediation transient revalidation (complete)

- Re-run all generic BWR scenarios after the R1-R6 model-basis changes.
- Correct scenario controls that bypassed modeled system behavior.
- Reinstate broad, source-grounded timing and response envelopes.
- Gate protection sequence, injection/discharge flows, pool heating, and the
  instantaneous vessel conservation ledgers.
- Numerically verify each scripted recovery against its declared end-state
  class: return to controlled power or stable shutdown.

Implemented basis: normal operation, recirculation trip, turbine trip, loss of
feedwater, small-break LOCA, and station blackout are active regression cases.
The turbine-trip definition closes feedwater with steam isolation; the
small-break case relies on modeled steam-driven makeup and does not force HPCI.
Legacy Phase-F envelopes are retained for traceability but are no longer gates.

Completed with transient checkpoint, conservation, safety-system sequencing,
recovery end-state, and full-suite regression tests. These are generic teaching
surrogate acceptance bands, not plant validation or safety-analysis criteria.

## Remediation R8 — uncertainty and sensitivity screening (complete)

- Add a reusable deterministic transient-analysis harness.
- Accumulate absolute mass/energy ledger residuals over complete events.
- Compare the normal 0.05 s integration timestep with 0.025 s for every R7
  transient family.
- Apply declared plus/minus 20% one-at-a-time screening perturbations to major
  generic hydraulic, level, neutronic, and safety-system parameters.
- Rank parameter-data replacement priorities without interpreting screening
  bands as statistical or plant uncertainty.

Completed with numerical-refinement, closure, directional-sensitivity, invalid-
parameter, and full-suite regression tests. The dominant screened dependencies
are recirculation pressure-loss calibration and reference-leg/level response.
The detailed ranking and R9 order are recorded in
`docs/BWR_UNCERTAINTY_SENSITIVITY.md`.

## Remediation R9 — parameter-data replacement (complete within public-data scope)

- Replace influential generic parameter families with defensible public data
  where applicable to a representative, non-plant-specific teaching model.
- Record provenance, units, conversions, applicability, and retained tuning.
- Re-run R7 envelopes and R8 sensitivities after each parameter-family change.
- Retain an explicitly generic value when suitable public data are unavailable;
  do not manufacture precision or tune silently to the present regression.

The R8 ranking sets the starting order: recirculation hydraulics, level/reference
leg response, void reactivity, safety-system curves, break inputs, then dedicated
heat-transfer/critical-power parameter evidence.

Implemented basis: OECD/NEA Peach Bottom-2 rated power, core flow, feedwater
temperature, steam flow, total core pressure drop, and support-plate pressure
drop now define the representative rated state and effective-loop loss split.
Public NRC records define RCIC/HPCI rated-flow points and their low-steam-pressure
driver cutoff. The saturated-vessel energy balance explicitly accounts for
feedwater preheat before vaporization.

The effective pump shutoff curve, reference-leg dynamic coefficient, void
reactivity coefficient, aggregate SRV curve, break coefficient, and dryout data
remain generic because no transferable public basis was established. This is an
intentional R9 result, not unfinished silent calibration. Full provenance,
conversions, applicability limits, and the post-R9 sensitivity rerun are in
`docs/BWR_PARAMETER_DATA_BASIS.md` and
`docs/BWR_UNCERTAINTY_SENSITIVITY.md`.

## Original Phase B — thermodynamic and vessel foundation (superseded)

- Close steam mass, energy, volume, pressure, and saturation state consistently.
- Add upper-plenum and separator storage/transport states.
- Define geometric liquid volumes and collapsed level.
- Add transient conservation and timestep-refinement acceptance criteria.

Exit criterion completed with explicit upper-plenum/separator storage, a
geometry-coupled saturated vessel pressure solve, geometry-derived collapsed
level, published thermodynamic residuals, and refinement tests.

## Original Phase C — recirculation and level physics (superseded by R1/R4/R5)

- Replace commanded flow fraction with pump/buoyancy/pressure-loss balance.
- Add loop momentum or a documented quasi-steady head solution.
- Derive swell and instrument levels from vessel volumes and reference legs.

Exit criterion completed with an integrated pump/buoyancy/quadratic-loss loop
momentum balance, natural-circulation coastdown, geometry-derived swell, and a
dynamic reference-leg temperature correction.

## Phase D — protection and safety systems (superseded by R2/R5/R7)

- Add availability/failure states, delays, latching, reset hysteresis, permissives,
  suction sources, and documented pressure-flow curves.
- Couple RCIC steam use and suppression-pool inventory/energy consistently.

Exit criterion completed with delayed and latched demands, ten-second recovery
hysteresis, pressure/level permissives, operator-selectable availability,
suppression-pool suction limits, and combined vessel/pool conservation ledgers.

## Phase E — axial channel and critical-power diagnostic (superseded by R3/R6)

- Adopt a documented open critical-power method with applicability guards.
- Add channel pressure-loss feedback and bundle/channel factors.
- Keep axial results diagnostic until correlation and coupling tests pass.

Exit criterion completed with a documented, guarded CISE-style X-L screening
method, iterated friction/gravity/acceleration pressure loss, declared bundle
and channel factors, and enforced diagnostic-only isolation from protection.

## Phase F — scenario regression envelopes (completed and revalidated by R7)

- Benchmark generic transients against published references.
- Define pressure, level, flow, void, power, timing, and end-state envelopes.
- Distinguish return-to-power from stable-shutdown demonstrations.

Exit criterion completed with public-source provenance, machine-readable
normalized envelopes, timed scenario regression tests, and explicit recovery
classes/end-state envelopes. R7 re-established these gates after R1-R6 and
added numerical demo end-state tests. The result remains a generic feature
prototype, not a plant-specific validated safety-analysis model.
