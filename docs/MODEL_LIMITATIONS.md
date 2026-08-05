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

## Classroom practice

Instructors should identify the assumptions relevant to each exercise, restore
the declared classroom defaults when reproducible marking is required, record
any non-default reactor pedagogical settings, compare
trends with established course material, and explain where a production
analysis code would require higher-fidelity models and validation.
