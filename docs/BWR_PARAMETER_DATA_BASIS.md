# BWR R9 public parameter-data basis

## Scope

R9 replaces influential generic values only where a public primary source can
be mapped honestly into the reduced-order model. The simulator remains a
representative BWR/4 teaching surrogate. Using selected Peach Bottom-2 reference
data does not make it a Peach Bottom model and does not validate its transients.

The machine-readable provenance is `bwr_parameter_basis.py`. It records the
adopted value, unit, original source quantity, conversion, and applicability.

## Adopted rated reference

The OECD/NEA Peach Bottom-2 turbine-trip benchmark supplies:

| Quantity | Source value | Model use |
|---|---:|---|
| Rated thermal power | 3293 MWth | BWR nominal thermal-power scale |
| Rated total core flow | 12,915 kg/s | Recirculation-flow reference |
| Rated steam flow | 1685 kg/s | Independent acceptance check |
| Feedwater temperature | 191.17 °C | IF97 conversion to 452.09 kJ/kg subcooling at 7 MPa |
| Total core pressure drop | 151.685 kPa | 20.90 m effective liquid head |
| Core-support-plate drop | 124.105 kPa | 17.10 m local/single-phase loss contribution |

The remaining 27.58 kPa becomes a 3.80 m aggregate bundle/two-phase friction
contribution. This subtraction is auditable but is not a separately measured
bundle-friction datum.

The model derives 1682 kg/s rated steam flow by allocating reactor power first
to feedwater sensible preheat and then to latent heat. The 0.2% difference from
the benchmark value is property-table/conversion scale. Derived flow quality is
about 0.130, consistent with the benchmark's rated average exit quality of
0.129.

The benchmark also reports 216.4 m developed head for each external
recirculation pump. That value is not used directly: the real pumps drive jet
pumps, whereas the reduced model solves one effective core loop. Inserting the
external-pump head into that balance would mix incompatible system boundaries.
The effective rated head is instead closed to measured core pressure drop.

## High-pressure makeup

Public NRC/plant records support 600 gpm RCIC and at least 5000 gpm HPCI at
required reactor-pressure head. These are approximately 37.9 and 315 kg/s for
water. The model stores zero-differential runout equivalents of 68 and 566 kg/s
so its retained quadratic curve reproduces those flows at 7 MPa. NRC NUREG-1953
reports RCIC/HPCI isolation below 75 psig steam pressure; both driver cutoffs are
therefore 0.52 MPa.

The 10 MPa shutoff head and quadratic curve shape remain generic. Consequently,
only the rated operating points and low-steam-pressure cutoff are source-backed,
not the full pump maps.

## Explicitly unresolved

- Effective recirculation pump shutoff head and speed-dependent curve: no public
  curve matching the reduced-loop boundary was located.
- Reference-leg response coefficient: NRC sources establish differential-
  pressure geometry and temperature/density errors, but not a transferable
  scalar dynamic response.
- Void reactivity coefficient: it depends on exposure, control pattern,
  thermodynamic state, and spatial void distribution; no defensible generic
  scalar was located.
- Aggregate SRV capacity: valve count, setpoints, uprates, and configuration are
  plant dependent.
- Equivalent break discharge coefficient: no transferable value specific to
  the model's homogeneous-equilibrium opening was found.
- Axial critical-power and dryout parameters require a dedicated bundle-data
  exercise rather than calibration against the R7 system transients.

These values remain visibly generic. R9 does not tune them to force old R7
trajectories.

## Sources

- OECD/NEA, *Boiling Water Reactor Turbine Trip Benchmark, Volume I*:
  https://www.oecd-nea.org/jcms/pl_13532/boiling-water-reactor-turbine-trip-tt-benchmark-volume-i
- NRC Peach Bottom inspection record identifying the 600 gpm RCIC pressure-drop
  calculation: https://adamswebsearch2.nrc.gov/webSearch2/main.jsp?AccessionNumber=ML14140A367
- NRC HPCI inspection record identifying at least 5000 gpm at required reactor
  pressure head: https://adamswebsearch2.nrc.gov/webSearch2/main.jsp?AccessionNumber=ML24180A058
- NRC, NUREG-1953: https://downloads.regulations.gov/NRC-2010-0344-0002/content.pdf
- NRC Generic Letter 84-23, BWR vessel level instrumentation:
  https://www.nrc.gov/reading-rm/doc-collections/gen-comm/gen-letters/1984/gl84023
- NRC Generic Issue 101, BWR water-level redundancy:
  https://www.nrc.gov/sr0933/section-3-new-generic-issues/issue-101-bwr-water-level-redundancy
