# PWR P1-4 scenario calibration basis

## Scope

P1-4 revalidates the representative PWR teaching model after the conservation,
protection, safety-injection, component, loop, steam-generator, and reduced
axial-dynamics changes. The executable authority is
`simulators/ThermalHydraulicsSimulator/pwr_calibration.py`.

These are deliberately broad, normalized regression envelopes. They test
direction, ordering, rough magnitude, protection state, hydraulic actuation,
and conservation closure. They are not measured plant uncertainty bands,
licensing limits, best-estimate validation, or evidence that the simulator can
predict a real plant transient.

## Active transient gates

| Case | Checkpoints | Required response |
|---|---:|---|
| Normal operation | 30 s | Nominal power, pressure, inventory, primary flow, and secondary pressure remain stable |
| Small-break LOCA | 5, 15, 30 s | Scram, depressurization and inventory loss precede HPSI and accumulator response |
| Large-break LOCA | 5, 30 s | Rapid blowdown and pump coastdown lead to accumulator/LPSI injection and sump recirculation |
| Loss of flow | 5, 30 s | Pump coastdown and scram are followed by reduced decay power and cladding heatup |
| Loss of heat sink | 15, 30 s | Loss of secondary cooling causes primary heatup, pressurization, voiding, and inventory challenge |
| Station blackout | 15, 30 s | Scram and pump coastdown occur without active primary injection while decay heat pressurizes the system |

Every accident checkpoint also has independent tests for the aggregate primary
mass/energy ledgers, exact reconciliation of resolved component mass/energy to
those aggregate stores, and the steam-generator secondary mass/energy ledger.
All accident presets retain a named scenario-initiated trip cause.

## Recovery demonstrations

All four PWR demonstrations are classified as `stable_shutdown`, not return to
power. At 245 seconds they must have low decay power, a retained reactor trip,
bounded primary pressure and inventory, and controlled cladding temperature.
The LOCA scripts now terminate commanded injection when primary inventory has
recovered instead of continuing to the 120% numerical inventory projection.
Auxiliary feedwater heat removal now has a matching secondary steam-export path,
so its mass and energy transport remain explicit.

## Public phenomenology basis

- OECD/NEA LOFT large-break experiments establish the broad sequence of break
  opening, low-pressure scram and pump trip, rapid coolant depletion, core
  heatup, ECCS/reflood, and quench.
- OECD/NEA small-break LOCA international-standard-problem work establishes
  depressurization, inventory redistribution, loop behavior, and safety-
  injection response as the relevant system phenomena.
- OECD/NEA PKL/ROSA integral programs establish PWR secondary heat-removal,
  cooldown, reflux-condensation, and loss-of-heat-sink phenomena.
- NRC PWR generic-fundamentals material supplies the qualitative operator-level
  basis for reactor trip, pump coastdown, decay heat, inventory, pressure, and
  engineered-safeguards response.

The simulator does not reproduce the facilities' geometry, scaling, boundary
conditions, plant controls, or qualified system-code models. Consequently, no
experimental point is used as a numerical target.

## Explicit boundary-limited results

The unrecovered loss-of-heat-sink and station-blackout presets contact the
model's 17.5 MPa upper pressure projection by 30 seconds. P1-4 gates this fact
so it cannot be mistaken for an unconstrained peak-pressure prediction. Formal
calibration does not cure the absence of detailed pressurizer relief capacity,
steam-line dynamics, containment backpressure, or plant-specific control logic.

## Sources

- OECD/NEA, *CSNI Integral Test Facility Validation Matrix — LOFT large-break
  experiments*: https://www.oecd-nea.org/upload/docs/application/pdf/2020-01/csni90-181.pdf
- OECD/NEA, *Lessons learned from OECD/CSNI ISP on small break LOCA*:
  https://www.oecd-nea.org/jcms/pl_16140
- OECD/NEA, *Primary Coolant Loop Test Facility (PKL) Project*:
  https://www.oecd-nea.org/jcms/pl_25236/primary-coolant-loop-test-facility-pkl-project
- US NRC, *Generic Fundamentals Examinations for Pressurized Water Reactor*:
  https://www.nrc.gov/reactors/operator-licensing/history-rulemaking-activities/generic-fundamentals-examinations/pwr
