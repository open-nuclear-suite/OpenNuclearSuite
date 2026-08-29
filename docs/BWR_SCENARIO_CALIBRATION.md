# BWR scenario calibration basis

Phase F originally calibrated the generic teaching model to broad, normalized
response envelopes. R7 has revalidated those regressions after the R1-R6
physics changes. This does not turn the simulator into a plant-specific
safety-analysis code or claim pointwise validation against Peach Bottom data.

The machine-readable authority is `bwr_calibration.py`. Each sampled variable
has a lower and upper bound, a sampling time, a public source, and a short
phenomenological basis. Regression tests fail if a trajectory leaves its
declared envelope.

| Case | Sample | Calibrated response |
|---|---:|---|
| Normal | 30 s | Power, pressure, inventory, and flow remain near nominal |
| Recirculation trip | 5/15 s | Flow coasts down before protection suppresses power and SRVs limit pressure |
| Turbine trip | 5/15 s | Isolation pressurizes the vessel; scram and SRVs suppress power and control pressure |
| Loss of feedwater | 15/30 s | Inventory falls before protection suppresses power |
| Small-break LOCA | 5/15/30 s | Break discharge, scram, steam-driven makeup, and pool heatup occur in sequence |
| Station blackout | 5/15/30 s | Scram, pump coastdown, RCIC response, inventory challenge, and pool heatup occur in sequence |

The OECD/NEA Peach Bottom 2 turbine-trip benchmark is the primary reference for
the pressure/void/power coupling. NRC operator-fundamentals and generic-issue
material provide the qualitative recirculation-trip and safety-response basis.
The simulator does not reproduce the benchmark's plant geometry, control
systems, acoustic steam-line pressure wave, or 3-D neutronics, so its numerical
envelopes are intentionally broad and normalized.

## R7 acceptance scope

All six declared cases are active regression gates. The checks cover response
ordering, broad magnitude, protection state, selected system flows, indicated
level, and suppression-pool heating. Each transient also has a zero-residual
check on the model's instantaneous vessel mass and energy ledgers. The former
Phase-F envelopes remain in the source as explicitly named legacy records so
that the changed model basis is auditable.

The turbine-trip and small-break definitions were corrected during R7. Turbine
isolation no longer leaves full feedwater forced on, and the small-break case no
longer forces HPCI flow irrespective of its pressure/permissive logic. These are
scenario-input corrections, not calibration parameters.

Recovery demonstrations now have executable numerical end-state gates. The
recirculation case is `return_to_power`: recirculation is restored promptly and
the model must settle near its original controlled power without a trip.
Turbine-trip and loss-of-feedwater cases are `stable_shutdown`: low decay power,
latched trip, controlled vessel pressure, and bounded inventory/flow. Recovery
means reaching the declared safe operating class; it does not generally mean
returning to full power.

The envelopes are intentionally wider than run-to-run numerical variation.
They do not include measurement uncertainty, plant tolerances, limiting single
failures, operator procedure timing, or regulatory acceptance criteria. Passing
them establishes consistency of this teaching surrogate only.

Sources:

- https://www.oecd-nea.org/jcms/pl_13532/boiling-water-reactor-turbine-trip-tt-benchmark-volume-i
- https://www.oecd-nea.org/jcms/pl_32222
- https://www.nrc.gov/sr0933/section-3-new-generic-issues/issue-151-reliability-anticipated-transient-without-scram-recirculation-pump-trip-bwrs
- https://www.nrc.gov/reactors/operator-licensing/history-rulemaking-activities/generic-fundamentals-examinations/bwr/bwr-files/292all.pdf
