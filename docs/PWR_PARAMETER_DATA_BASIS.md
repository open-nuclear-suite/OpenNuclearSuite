# PWR P2-2 public parameter-data basis

## Scope

P2-2 replaces influential generic values only where public primary information
maps honestly into the reduced model. The machine-readable authority is
`simulators/ThermalHydraulicsSimulator/pwr_parameter_basis.py`.

The simulator remains a representative PWR teaching surrogate. Selected AP1000
rated data provide a coherent thermodynamic and hydraulic reference family;
they do not make this an AP1000 plant model or validate its accidents.

## Adopted rated reference

| Model quantity | Adopted value | Public basis and mapping |
|---|---:|---|
| Thermal power | 3415 MWth | NRC AP1000 NSSS rating |
| Primary pressure | 15.5 MPa | NRC AP1000 RCS operating pressure |
| Average primary temperature | 300.75 °C | 573.9 K rated average minus 273.15 |
| Hot/cold leg rise | 41.0 °C | 594.4 K minus 553.4 K |
| Nominal RCP developed head | 111.25 m | 365 ft multiplied by 0.3048 |
| Effective rated loop loss | 111.25 m | Nominal closure to the adopted RCP head |
| SG secondary pressure | 5.76 MPa | Rated steam outlet pressure |
| SG secondary inventory scale | 76,965.77 kg | Reported rated SG secondary water mass |
| Effective SG sink temperature | 273.0 °C | Rounded saturation temperature at 5.76 MPa |

The reported secondary inventory is for one SG model, while the real AP1000 has
two steam generators. It is used as an effective storage scale because the
simulator has one aggregate secondary control volume; it is not claimed to be
the full-plant secondary mass.

The AP1000 uses four RCPs in two loops. Pump head is common across parallel flow
paths, so the rated 111.25 m developed head is a defensible nominal head for the
effective loop. The simulator does not adopt the per-pump flow as its normalized
flow scale, and the full curve away from rated conditions remains generic.

## LOFT sequence evidence

The OECD/NEA BEMUSE description of LOFT L2-5 reports scram at 0.24 s, pump trip
at 0.94 s, accumulator injection at 16.8 s, HPIS at 23.90 s, LPIS at 37.32 s,
and complete quench near 65 s. LOFT is a 50 MWth, short-core integral facility,
and the report explicitly cautions that its roughly 65 s quench is much shorter
than the 200–450 s typical-PWR range. P2-2 therefore retains these as sequence
evidence only. It does not replace simulator delays or normalized pump curves
with scaled-facility values.

## Explicitly unresolved

- RCP off-design and homologous curve shape; only a rated head point is adopted.
- Component-resolved loop friction and local-loss decomposition.
- Equivalent break discharge coefficient for the modeled opening.
- HPSI and LPSI runout/shutoff curves and normalized capacities.
- Accumulator inventory and geometry mapping.
- Pressurizer surge, spray, heater, and relief response represented by one time
  constant.
- Aggregate secondary pressure-energy capacitance and AFW capacity.
- Axial void-reactivity coefficient, which depends on core loading, burnup,
  boron, rod pattern, and spatial state.

These parameters remain visibly generic. No value was silently tuned to force
the pre-P2-2 P1-4 trajectories.

## Post-replacement regression

P1-4 envelopes were rerun after adopting the reference family. Only gates
directly shifted by the new basis were revised: SG reference pressure, SBLOCA
void, LOFA/SBO cladding response, LOFA pressure, and the SBO-recovery inventory
band. P2-1 timestep differences remain below 0.004, and the complete sensitivity
ranking is recorded in `PWR_UNCERTAINTY_SENSITIVITY.md`.

## Sources

- US NRC, NUREG-1793 AP1000 FSER, Chapter 1:
  https://www.nrc.gov/sites/default/files/doc_library/cdn/legacy/reading-rm/doc-collections/nuregs/staff/sr1793/initial/chapter1.pdf
- US NRC, NUREG-1793 AP1000 FSER, Chapter 5:
  https://www.nrc.gov/cdn/legacy/reading-rm/doc-collections/nuregs/staff/sr1793/initial/chapter5.pdf
- US NRC, NUREG/IA-0439, *TRACE Analysis on Heat Removal Decrease Accidents for AP1000*:
  https://www.govinfo.gov/content/pkg/GOVPUB-Y3_N88-PURL-gpo47583/pdf/GOVPUB-Y3_N88-PURL-gpo47583.pdf
- OECD/NEA, BEMUSE Phase III LOFT L2-5 uncertainty and sensitivity report:
  https://www.oecd-nea.org/upload/docs/application/pdf/2021-03/csni-r2007-4.pdf
