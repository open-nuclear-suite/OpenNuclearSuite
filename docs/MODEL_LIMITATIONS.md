# Model scope and limitations

## Intended use

The simulators are qualitative classroom tools. They are intended to help
students explore relationships among reactor power, reactivity, thermal
feedback, decay heat, coolant conditions, heat removal, engineered safety
features, and selected accident scenarios.

## Prohibited uses

Do not use either simulator for:

- reactor design or plant modification;
- licensing, regulatory submissions, or safety analysis;
- best-estimate or conservative accident analysis;
- operator qualification or real-time operational decisions;
- emergency planning, consequence prediction, or public-safety decisions;
- validation of plant procedures, limits, setpoints, or equipment performance.

## Technical limitations

The applications use simplified, lumped-parameter representations and
pedagogically adjusted constants and time scales. The reactor simulator's
instructor presets intentionally change selected prompt-kinetics, iodine/xenon,
and load-follow timescales; the active configuration is part of the teaching
model and does not represent a validated plant. Its advanced profile adds
normalized Pm/Sm poisoning, a nonlinear rod-worth curve, source-range
instrumentation, separated feedback terms, and teaching-scaled exposure. These
remain lumped demonstrations rather than validated cross sections, spatial
neutronics, depletion, detector response, or plant data. The applications do not reproduce the full
geometry, spatial physics, multi-dimensional fluid behavior, detailed
two-phase-flow regimes, component-specific performance, protection-system
logic, uncertainty treatment, or validated plant data required for engineering
analysis.

Scenario results should therefore be interpreted as qualitative trends. A
plausible-looking numerical value is not evidence of physical accuracy.
R7 adds active, broad regression envelopes for six generic BWR scenarios and
numerical recovery-demo end states. These test direction, ordering, rough
magnitude, protection state, and internal conservation consistency after the
R1-R6 remediations. They are teaching-model regression gates, not comparison
against plant measurements, uncertainty-qualified validation, licensing
criteria, or evidence that untested transients are reliable.

The optional Representative LWR kinetics preset declares 100% normalized
power as 3000 MWth, uses a realistic-scale prompt generation time with
internally substepped RK4 integration, and couples power to a conservative
three-node MW/MJ thermal-energy balance. Its effective fuel, cladding, and
coolant heat capacities and conductances are declared teaching parameters
selected to reproduce the stated full-power equilibrium. They are not derived
from a particular plant. Coolant inventory and transport delay, poison
coefficients, component curves, protection delays, and setpoints remain
illustrative unless separately documented and calibrated. Dimensional units
and algebraic energy conservation do not establish plant validation.

The PWR thermal-hydraulics model separates accumulator, HPSI, LPSI/reflood, and
sump-recirculation injection paths. Generic quadratic HPSI/LPSI/recirculation
pump curves enforce declared shutoff pressures; the passive accumulator has a
finite normalized inventory and pressure-driven discharge. Automatic pump
demands have separate delays, latches, pressure permissives, availability, and
recovery reset logic. Simplified mode provides a mutually exclusive **Combined
ECCS command (simplified)** routed through the same component curves; Advanced
mode instead exposes the individual pumped paths and their availability.
Capacities,
setpoints, delays, accumulator volume, containment collection, sump inventory,
boration, train redundancy, electrical divisions, and switchover logic are not
calibrated to a plant. Reflood is not spatially resolved, and recirculation is a
net injection surrogate rather than a closed containment mass balance.

During normal-operation PWR rod maneuvers, a 30-second effective rod-motion lag
and bounded proportional power-damping term reduce the exaggerated slow
oscillation of the lumped point-kinetics/thermal-feedback model. This is a
teaching-model stabilizer, not a modeled rod-drive control system or calibrated
plant controller. Trips, non-normal scenarios, and break transients bypass it.

The selectable 37-state BWR R9 source-parameterized feature prototype separately integrates reduced-order core
liquid, core vapor, downcomer liquid, upper-plenum liquid, separator liquid, and
steam-dome mass and stored energy. At every RHS evaluation a saturated flash
solves pressure and phase split from total vessel mass, internal energy, and
fixed volume. It includes
direct steam/feedwater boundary flows, a residence-time separator surrogate, an
integrated pump/head-flow and density-driven recirculation momentum balance, a core-vapor-volume void estimate, teaching-scale void
reactivity, and simplified SRV capacity. These control volumes and coefficients
are representative rather than plant-specific. The displayed liquid inventory
is a geometry-derived collapsed level, not a calibrated narrow- or wide-range
instrument indication. The indicated level adds geometry-derived core swell and
a first-order reference-leg temperature correction, but is not calibrated to
plant sensing lines. Separator carryover/carry-under efficiency, detailed pump
and plant-specific component curves, dynamic containment pressure and detailed suppression-pool hydraulics,
and validated fuel-vendor safety-limit MCPR methods are not modeled. The
BWR safety-support extension includes delayed, latched teaching-scale RCIC, HPCI, ADS, LPCI,
core-spray, MSIV, bypass, break-flow, shutdown-cooling, swell-indication, and
suppression-pool mass/energy and suction-limit surrogates. Equipment availability
can be selected independently. Generic quadratic pump curves now enforce
vessel-to-pool differential-pressure shutoff, with separate steam-driver
permissives for RCIC/HPCI. Break discharge uses a backpressure-aware isentropic
homogeneous-equilibrium flashing-nozzle model. The HEM assumption omits phase
slip and thermal nonequilibrium and may bias critical flux; break geometry,
discharge coefficient, runout capacities, and shutoff heads are not calibrated.
These remain screening models, not plant-specific setpoints, logic diagrams,
level instruments, containment response, or validated ECCS performance. The PWR
hot-channel model is not reused in BWR mode. A separate quasi-steady 24-node
BWR channel reports axial equilibrium quality, homogeneous void, temperatures,
and diagnostic CPR from the guarded open X-L method documented in
`docs/BWR_CRITICAL_POWER_METHOD.md`. It does not represent a bundle-specific
GEXL correlation, detailed spacer or part-length-rod effects, bypass flow,
channel-box heat transfer, uncertainty, or a safety limit. A valid in-range CPR
now drives a bounded nucleate/transition/film-boiling conductance in the lumped
cladding energy balance. The conductance curve is a teaching surrogate, not a
validated post-dryout or reflood correlation; invalid CPR remains uncoupled and
is reported as an unassessed two-phase condition. Capability
maturity and the ordered follow-on work are maintained in
`docs/BWR_DEVELOPMENT_ROADMAP.md`.

The recirculation loop separates core two-phase friction, other
single-phase/local loss, acceleration head, hydrostatic driving head, and pump
head. Its Lottes-Flinn multiplier and homogeneous mixture acceleration term are
open reduced-order methods, but component reference losses, effective elevation,
flow area, and pump curve are generic calibrations. The model does not resolve
individual jet pumps, recirculation loops, separator pressure drop, flow-regime
slip, cavitation, or density-wave instability.

The BWR protection model independently times high flux, high vessel pressure,
low indicated level, and guarded thermal-limit channels and retains the first
trip cause. ECCS/ADS initiation, delays, pressure permissives, availability, and
reset hysteresis are explicit. It does not model redundant sensor divisions,
one-out-of-two-twice voting, bypasses, surveillance tolerances, instrument drift,
high-drywell-pressure initiation, electrical divisions, or plant-specific
technical-specification setpoints.

R6 adds four dynamic axial power-shape and four vapor-holdup shares. They capture
upward void propagation, bottom-entry rod shaping, spatial void feedback, and a
moving axial heat-flux peak at low computational cost. They are normalized
redistributions of lumped totals, not independent nodal mass/energy balances.
There is no radial coupling, neutron diffusion, xenon dynamics, channel-to-channel
flow redistribution, crossflow, or validated stability decay-ratio prediction.
Four nodes are a fixed teaching resolution and do not establish spatial grid
convergence.

BWR scenario calibration uses broad normalized envelopes derived from public
OECD/NEA and NRC descriptions. It verifies response direction, ordering, and
representative magnitude, not pointwise agreement with a particular plant.
The provenance and acceptance ranges are documented in
`docs/BWR_SCENARIO_CALIBRATION.md` and encoded in `bwr_calibration.py`. R7
revalidated all declared transient envelopes after the R1-R6 physics changes.

R8 local sensitivity scores use deterministic plus/minus 20% one-at-a-time
screening perturbations. They are not probability distributions, confidence
intervals, component tolerances, global sensitivities, or uncertainty bounds.
They may miss parameter interactions, nonlinear thresholds, and sensitivities
outside the selected transient/time window. Their sole purpose is numerical
robustness checking and prioritizing parameter evidence for R9.

R9 adopts selected public BWR/4 rated quantities and high-pressure makeup
operating points. The real external recirculation-pump head is not applied to
the reduced effective loop because the actual pumps drive jet pumps. Pump-curve
shape, reference-leg dynamics, void reactivity, SRV aggregation, and break
coefficient remain generic where no transferable public basis was established.
Mixed source-backed and generic parameters do not constitute a plant model.

The thermal-hydraulics model conserves a lumped primary coolant inventory and
stored energy: break, PORV, vapor, and ECCS flows transport simplified
enthalpy, and vaporization uses an effective latent heat. Pressure is obtained
from a compact saturation table through a single saturated-pressurizer state.
The boiling model distinguishes single-phase convection, nucleate boiling,
transition boiling, and film boiling using a transparent CHF surrogate based
on pressure, flow, and core coverage. These additions improve internal
consistency and classroom trends, but they are not validated water-property,
critical-flow, CHF/DNB, reflood, or component models. The single primary volume
cannot reproduce loop seals, counter-current flow, spatial core uncovery,
break-location effects, or multidimensional behavior.

The PWR component resolution remains reduced order. Core, hot-leg, cold-leg,
and pressurizer liquid/steam stores are constrained partitions of the existing
aggregate primary mass and energy, not independent compressible control-volume
solutions. The loop momentum equation uses one effective flow path, quadratic
loss, a speed-squared pump head, and a temperature-difference buoyancy term; it
does not resolve individual loops, pump homologous curves, reverse flow, loop
seals, or two-phase momentum. The steam-generator secondary is one equilibrium
mass/energy store with a fixed nominal vapor fraction and an effective pressure
capacitance. It does not resolve tube rows, shrink/swell, separator carryover,
steam-line dynamics, or detailed feedwater and turbine systems.

The P1-4 PWR scenario envelopes are regression and phenomenology checks, not
validation bands, uncertainty intervals, licensing acceptance criteria, or
predictions for a specific plant. In particular, the unrecovered loss-of-heat-
sink and station-blackout presets reach the model's 17.5 MPa pressure projection
by 30 seconds. The tests deliberately expose and retain that boundary contact;
they do not establish a realistic peak pressure. Recovery scripts use simple
inventory-dependent injection termination and generic operator-action timing.

P2-1 parameter perturbations are deterministic local screens. The ±20% band is
not a measured tolerance, confidence interval, failure probability, or joint
uncertainty distribution. One-at-a-time derivatives omit parameter interaction,
threshold discontinuities, nonlinear tails, and model-form uncertainty. A low
score can also mean that the selected transient does not excite the parameter.

P2-2 uses selected AP1000 rated data as a coherent public reference family, but
the simulator is not an AP1000 model. The one reported SG secondary inventory
is an effective reduced-model scale; the full plant has two SGs. A rated RCP
head closes the nominal effective loop, but component pressure losses and the
off-design/homologous pump curve remain generic. Active HPSI/LPSI are retained
as teaching surrogates even though the AP1000 safety architecture is passive.

Water and steam property queries use a bundled pressure-enthalpy table generated
from IAPWS-IF97 over 0.1--20 MPa and 100--3600 kJ/kg. Bilinear interpolation is
used in single-phase regions and saturation-endpoint mixture relations are used
inside the two-phase dome. This is a compact educational lookup implementation,
not the full spline-based IAPWS SBTL method. Standard-based property values do
not validate the simulator's lumped component, break-flow, boiling, CHF, ECCS,
or pressurizer models.

The optional representative hot-channel diagnostic is a one-dimensional,
single-channel reduced-order calculation with a four-zone dynamic axial power
shape mapped onto its declared PWR-like geometry. The normalized shape responds
to top-entry rod insertion and reconstructed local void, but it only redistributes
existing total power. Four normalized vapor-holdup shares reconstruct local void
from the aggregate void state; they do not add coolant mass or energy. The model
does not solve axial neutron diffusion, xenon dynamics, crossflow, or independent
zone conservation equations. The hot channel marches pressure and bulk enthalpy and
uses fixed effective fuel, gap, cladding, and coolant heat-transfer parameters.
Its axial temperature profile is recalculated quasi-steadily and does not carry
separate fuel/cladding thermal-capacitance states at every axial node. The trend
display therefore shows successive boundary-condition snapshots, not a resolved
axial heat-storage or reflood transient.
It does not model subchannel crossflow or mixing, grid-spacer effects, lateral
conduction, detailed fuel-temperature-dependent conductivity, local flow-regime
closures, or reflood. When enabled, its feedback to the lumped transient is
limited to held thermal-limit signals: peak axial cladding temperature and
minimum valid DNBR can actuate the teaching trip/ECCS logic and strengthen the
lumped post-CHF heat-transfer degradation. This is not a conservative safety
system model or a replacement for coupled conservation equations. Its optional Tong W-3
CHF/DNBR calculation is evaluated only inside the correlation's published
pressure, mass-flux, equilibrium-quality, and hydraulic-diameter ranges; other
nodes are explicitly marked unavailable. The implementation uses the
uniform-flux form and does not include non-uniform-flux, spacer-grid,
heated-perimeter, bundle-specific, uncertainty, or statistical design-limit
corrections. Axial temperatures, equilibrium quality, CHF, and DNBR are teaching
trends, not safety limits or predictions for a specific fuel assembly.

## Classroom practice

Instructors should identify the assumptions relevant to each exercise, restore
the declared classroom defaults when reproducible marking is required, record
any non-default reactor pedagogical settings, compare
trends with established course material, and explain where a production
analysis code would require higher-fidelity models and validation.
