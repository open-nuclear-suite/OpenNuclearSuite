# Major-item verification and validation of the Open Nuclear Suite thermal-hydraulics teaching models

**Evaluation snapshot:** 31 August 2026

**Software:** Open Nuclear Suite thermal-hydraulics simulator

**Scope:** reduced-order PWR and BWR teaching models

## Abstract

This article reports a deliberately compact verification and validation (V&V)
assessment of the simulator's major thermal-hydraulic capabilities. Numerical
verification covers conservation, equilibrium preservation, temporal and axial
mesh refinement, property handling, and automated regression. Quantitative
comparison with public data covers selected PWR and BWR rated conditions and an
independent BWR steam-flow closure. The PWR hot-channel implementation is also
checked against a published W-3 critical-heat-flux equation reference point.
Representative accident and operational transients are compared only at the
level justified by the reduced model: response direction, event ordering, and
broad normalized magnitude.

The strongest result is that the implemented equations are internally
consistent and reproduce the adopted public rated-state quantities. The BWR
energy balance independently predicts 1682.49 kg/s steam flow versus the
published 1685 kg/s value, a −0.15% difference. The transient results are not
pointwise plant validation and must not be used for licensing, safety limits,
equipment qualification, or operating procedure validation.

## 1. Model and evidence scope

The simulator combines point kinetics, lumped fuel/cladding/coolant energy
storage, reduced primary and secondary hydraulic volumes, protection logic,
pressure-dependent emergency cooling, and representative axial-channel thermal
limits. The PWR reference family uses selected public AP1000 rated quantities;
the BWR reference family uses selected Peach Bottom Unit 2 BWR/4 benchmark
quantities. This mapping establishes traceability and scale, not identity with
either plant.

Evidence is classified as follows:

| Classification | Meaning in this article |
|---|---|
| Verified | The numerical implementation satisfies an equation, conservation law, refinement test, or software regression. |
| Quantitatively compared | A model output is compared numerically with a public reference value. |
| Qualitatively benchmarked | Direction, ordering, and broad magnitude agree with published phenomenology, but facility geometry and boundary conditions are not reproduced. |
| Not validated | The available evidence does not support a transferable numerical claim. |

## 2. Major verification results

| Major item | Acceptance evidence | Result |
|---|---|---|
| Primary mass and energy accounting | PWR accident cases close aggregate and component ledgers to less than 1×10⁻⁹ inventory fraction/s and 1×10⁻⁶ MW; secondary residuals are below 1×10⁻⁶ kg/s and MW. BWR transient tests require zero instantaneous vessel-ledger residual within numerical tolerance. | Verified |
| Nominal equilibrium | PWR and BWR normal-operation cases remain within declared power, pressure, inventory, flow, and secondary-state bands for 30 s. | Verified |
| Time integration | The RK4 solution passes timestep refinement; the 0.10 s result is more than eight times closer to the 0.025 s reference than the 0.20 s result. | Verified |
| Axial hot channel | Deposited power equals coolant enthalpy gain; a 20-node solution moves toward the 80-node result and differs by less than 0.2 °C at the outlet. | Verified |
| Property and correlation guards | IF97 references, interpolation behavior, unit conversion, and published W-3 applicability limits are executable tests; out-of-range W-3 states return unavailable rather than extrapolated values. | Verified |
| Software regression | The complete discovery suite passed 156 tests in the evaluation snapshot; focused V&V gates were rerun after preparation of this article. | Verified |

These checks show that the coded model solves its declared reduced equations
consistently. They do not establish that the reduced equations contain every
important plant phenomenon.

## 3. Quantitative comparison with published data

### 3.1 PWR rated-state reference

| Quantity | Public reference | Simulator | Difference | Interpretation |
|---|---:|---:|---:|---|
| Thermal power | 3415 MWth | 3415 MWth | 0% | Adopted rated scale |
| Primary pressure | 15.5 MPa | 15.5 MPa | 0% | Adopted operating reference |
| Average primary temperature | 300.75 °C | 300.75 °C | 0% | Converted from 573.9 K |
| Hot-to-cold-leg rise | 41.0 °C | 41.0 °C | 0% | Simulator initializes at 321.25/280.25 °C |
| RCP head / effective loop loss | 111.25 m | 111.25/111.25 m | 0% closure | Rated head balance; off-design curve remains generic |
| Secondary pressure | 5.76 MPa | 5.76 MPa | 0% | Adopted steam-generator reference |

The values originate from the NRC AP1000 safety-evaluation and public TRACE
analysis material. Because they are model inputs or initialization targets,
their exact reproduction is a provenance and equilibrium check—not independent
validation of an AP1000 plant model.

### 3.2 BWR rated-state and independent steam-flow closure

| Quantity | Peach Bottom-2 reference | Simulator | Difference | Interpretation |
|---|---:|---:|---:|---|
| Thermal power | 3293 MWth | 3293 MWth | 0% | Adopted rated scale |
| Total core flow | 12,915 kg/s | 12,915 kg/s | 0% | Adopted flow reference |
| Total core pressure drop | 151.685 kPa | 20.90 m liquid head equivalent | Conversion closure | Effective reduced-loop boundary |
| Core-support-plate drop | 124.105 kPa | 17.10 m liquid head equivalent | Conversion closure | Local/single-phase contribution |
| Steam flow | 1685 kg/s | 1682.49 kg/s | −0.15% | Independently derived from the energy balance and IF97 properties |
| Average exit quality | 0.129 | approximately 0.130 | approximately +0.001 | Independent thermodynamic consistency check |

The steam-flow and exit-quality comparisons are the clearest quantitative
validation evidence in the current reduced BWR model: they are outputs of the
energy/property closure rather than direct copies of the benchmark values.
They validate the rated thermodynamic closure only, not turbine-trip dynamics.

### 3.3 PWR hot-channel critical heat flux

At 15.0 MPa, 4000 kg·m⁻²·s⁻¹ mass flux, −0.10 equilibrium quality, 0.012 m
heated diameter, and 100 kW/m linear heat, the implementation produces a W-3
critical heat flux of **3.1856702574 MW/m²**. This reproduces the coded reference
evaluation of the published Tong W-3 equation and its unit conversion. The
implementation also enforces the published pressure, mass-flux, quality, and
geometry domain instead of extrapolating.

This is correlation-implementation verification. It is not a new comparison
against the original experimental database and therefore does not quantify
W-3 correlation uncertainty for this simulator's representative channel.

## 4. Major transient assessment

Six PWR cases—normal operation, small- and large-break LOCA, loss of flow, loss
of heat sink, and station blackout—and six BWR cases—normal operation,
recirculation trip, turbine trip, loss of feedwater, small-break LOCA, and
station blackout—have executable checkpoint envelopes. All declared envelopes
pass in the evaluation snapshot.

The checks support these major phenomenological claims:

| Model | Public evidence used | Supported model behavior | Evidence level |
|---|---|---|---|
| PWR LBLOCA | OECD/NEA LOFT and BEMUSE material | Rapid depressurization and inventory loss precede accumulator/low-pressure injection and recovery. | Qualitative benchmark |
| PWR SBLOCA and cooldown | OECD/NEA small-break, PKL, and related integral-test programs | Depressurization, inventory redistribution, safety injection, secondary cooldown, and decay-heat removal occur in the expected order. | Qualitative benchmark |
| BWR turbine trip | OECD/NEA Peach Bottom-2 turbine-trip benchmark | Isolation causes pressurization and void/power feedback; scram, bypass/SRV action, and reduced power follow. | Qualitative benchmark |
| BWR inventory challenges | NRC operator-fundamentals and generic safety-system descriptions | Loss of feedwater, LOCA, and blackout produce the expected ordering of level challenge, trip, steam-driven makeup, and heat rejection. | Qualitative benchmark |

No transient is claimed as pointwise validated. The simulator does not match
the facilities' geometry, nodalization, acoustic steam lines, containment,
control-system timing, initial-condition uncertainty, or three-dimensional
neutronics. For example, published LOFT L2-5 timing is retained as sequence
evidence, not copied into generic commercial-PWR setpoints. Likewise, the
Peach Bottom turbine-trip benchmark explicitly calls for system and spatial
models beyond this simulator's lumped resolution.

## 5. Acceptance statement

The major-item V&V evidence supports use of the PWR and BWR models for
conceptual education, qualitative transient exploration, software exercises,
and comparison of control or safety-system trends. It supports the following
bounded claim:

> The simulator is numerically verified against its declared reduced-order
> equations, reproduces selected public PWR and BWR rated-state references, and
> demonstrates qualitatively correct major transient sequences within explicit
> regression envelopes.

It does **not** support claims of plant-specific predictive accuracy, licensing
validation, safety-analysis-code qualification, operator-procedure validation,
or prediction of peak pressure, peak cladding temperature, minimum DNBR/CPR,
quench time, or emergency-system performance for a real reactor.

## 6. Reproducibility

From `simulators/ThermalHydraulicsSimulator`, run:

```text
python -m unittest discover -p "test_*.py"
```

The machine-readable parameter provenance and transient acceptance envelopes
are in `pwr_parameter_basis.py`, `bwr_parameter_basis.py`,
`pwr_calibration.py`, and `bwr_calibration.py`. Detailed assumptions and
unresolved parameters are recorded in the companion parameter-basis,
calibration, uncertainty, and model-limitations documents.

## References

1. U.S. Nuclear Regulatory Commission, *Final Safety Evaluation Report Related to Certification of the AP1000 Standard Design*, NUREG-1793, [report index](https://www.nrc.gov/reading-rm/doc-collections/nuregs/staff/sr1793/initial/index).
2. U.S. Nuclear Regulatory Commission, *TRACE Analysis on Heat Removal Decrease Accidents for AP1000*, NUREG/IA-0439, [report PDF](https://www.govinfo.gov/content/pkg/GOVPUB-Y3_N88-PURL-gpo47583/pdf/GOVPUB-Y3_N88-PURL-gpo47583.pdf).
3. OECD Nuclear Energy Agency, *Boiling Water Reactor Turbine Trip Benchmark, Volume I: Final Specifications*, NEA/NSC/DOC(2001)1, [report PDF](https://cms.oecd-nea.org/upload/docs/application/pdf/2019-12/nsc-doc2001-1.pdf).
4. OECD Nuclear Energy Agency, *Boiling Water Reactor Turbine Trip Benchmark, Volume II: Summary Results of Exercise 1*, NEA/NSC/DOC(2004)21, [report page](https://www.oecd-nea.org/jcms/pl_13810/boiling-water-reactor-turbine-trip-tt-benchmark-volume-ii).
5. OECD Nuclear Energy Agency, *BEMUSE Phase III: Uncertainty and Sensitivity Analyses of the LOFT L2-5 Experiment*, NEA/CSNI/R(2007)4, [report PDF](https://www.oecd-nea.org/upload/docs/application/pdf/2021-03/csni-r2007-4.pdf).
6. OECD Nuclear Energy Agency, *CSNI Integral Test Facility Validation Matrix—LOFT Large Break Experiments*, [report PDF](https://www.oecd-nea.org/upload/docs/application/pdf/2020-01/csni90-181.pdf).
7. OECD Nuclear Energy Agency, *Primary Coolant Loop Test Facility (PKL) Project*, [programme description](https://www.oecd-nea.org/jcms/pl_25236/primary-coolant-loop-test-facility-pkl-project).
8. L. S. Tong, *Boiling Crisis and Critical Heat Flux*, TID-25887, [public report](https://www.osti.gov/servlets/purl/4629988).
