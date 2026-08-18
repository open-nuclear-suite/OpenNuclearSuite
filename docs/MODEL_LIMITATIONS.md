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

The thermal-hydraulics model represents ECCS injection effectiveness with a
continuous classroom-scale response between 14 MPa, 8 MPa, and 2 MPa. These
reference pressures illustrate increasing injection effectiveness during
depressurization; they are not plant-specific equipment setpoints or validated
pump-performance curves.

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

Water and steam property queries use a bundled pressure-enthalpy table generated
from IAPWS-IF97 over 0.1--20 MPa and 100--3600 kJ/kg. Bilinear interpolation is
used in single-phase regions and saturation-endpoint mixture relations are used
inside the two-phase dome. This is a compact educational lookup implementation,
not the full spline-based IAPWS SBTL method. Standard-based property values do
not validate the simulator's lumped component, break-flow, boiling, CHF, ECCS,
or pressurizer models.

The optional representative hot-channel diagnostic is a one-dimensional,
single-channel reduced-order calculation with a prescribed chopped-sine axial power
shape and declared PWR-like geometry. It marches pressure and bulk enthalpy and
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
