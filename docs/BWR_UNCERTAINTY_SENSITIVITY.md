# BWR R8 uncertainty and sensitivity screening

## Purpose and interpretation

R8 adds deterministic numerical-robustness and local-sensitivity tools for the
generic BWR teaching surrogate. It answers two limited questions:

1. Are the R7 transient results materially changed by halving the integration
   timestep?
2. Which declared generic parameters most strongly influence representative
   transient outputs when individually perturbed by plus or minus 20%?

The perturbation is a screening band, not a confidence interval, equipment
tolerance, failure probability, or statement about actual plant uncertainty.
One-at-a-time derivatives do not capture parameter interactions or nonlinear
tails. The results prioritize R9 data replacement; they do not validate the
simulator.

The executable authority is `bwr_uncertainty.py`. It records final power,
pressure, inventory and flow; peak pressure and cladding temperature; minimum
inventory; trip time; and time-integrated absolute mass/energy ledger
residuals. Non-finite trajectories and unknown parameters fail explicitly.

## Numerical robustness

The standard 0.05 s timestep was compared with 0.025 s. Maximum normalized
endpoint differences over the R7 transient checkpoints were:

| Scenario | Power | Pressure | Inventory | Flow |
|---|---:|---:|---:|---:|
| Recirculation trip, 15 s | 0.00081 | 0.00042 | 0.00011 | 0.00019 |
| Turbine trip, 15 s | 0.00009 | <0.00001 | <0.00001 | 0.00003 |
| Loss of feedwater, 30 s | 0.01218 | <0.00001 | <0.00001 | <0.00001 |
| Small-break LOCA, 30 s | 0.00056 | 0.00051 | 0.00012 | 0.00002 |
| Station blackout, 30 s | 0.00132 | 0.00066 | 0.00016 | 0.00041 |

The larger loss-of-feedwater power difference is caused by a discrete trip
event near the 30 s sampling point, not drift in pressure or inventory.
Accumulated absolute model mass and energy residuals are also regression-gated.

## Local sensitivity ranking

The score is the largest absolute dimensionless central sensitivity among the
recorded response metrics. It measures response change per fractional parameter
change near the current nominal point.

| Rank | Parameter and representative case | Score | Interpretation |
|---:|---|---:|---|
| 1 | Core two-phase friction reference head — recirculation trip | 1.142 | Dominates power/flow coastdown; highest R9 data priority |
| 2 | Reference-leg level sensitivity — loss of feedwater | 0.683 | Alters low-level trip timing and hence sampled power |
| 3 | Void reactivity coefficient — recirculation trip | 0.101 | Moderate power sensitivity; needs defensible neutronic basis |
| 4 | RCIC capacity — small-break LOCA | 0.032 | Measurable inventory response in this short generic case |
| 5 | SRV capacity — turbine trip | 0.019 | Small local influence within the modeled automatic pressure band |
| 6 | Break discharge coefficient — small-break LOCA | 0.010 | Small local endpoint influence for this opening and time window |

Low local sensitivity does not prove a parameter unimportant in other break
sizes, longer events, threshold crossings, or combined failures.

## R9 parameter-data replacement order

1. Recirculation-loop geometry, core two-phase pressure-loss basis, and pump
   head-flow data.
2. Reactor-water-level reference-leg geometry, temperature response, instrument
   scaling, and generic protection threshold provenance.
3. Void reactivity coefficient and its state dependence.
4. RCIC/HPCI, SRV, and low-pressure ECCS pressure-flow/capacity data.
5. Break area/discharge inputs and applicability evidence for the homogeneous
   equilibrium discharge method.
6. Heat-transfer and axial critical-power parameters, using dedicated dryout
   cases because the R7 scenarios do not sufficiently excite them.

R9 should replace one parameter family at a time and rerun R7 and R8 after each
change. If public data are unavailable, the parameter must remain explicitly
generic rather than being tuned silently to preserve an existing trajectory.

## Post-R9 rerun

After the source-backed rated core-flow/pressure-loss and high-pressure makeup
changes, the local ranking became:

| Rank | Parameter and representative case | Score |
|---:|---|---:|
| 1 | Reference-leg level sensitivity — loss of feedwater | 2.328 |
| 2 | Void reactivity coefficient — recirculation trip | 0.180 |
| 3 | Core friction remainder — recirculation trip | 0.134 |
| 4 | SRV capacity — turbine trip | 0.021 |
| 5 | Break discharge coefficient — small-break LOCA | 0.011 |
| 6 | RCIC curve capacity — small-break LOCA | 0.004 |

Replacing the former 40 m core-friction tuning with the measured pressure-drop
decomposition reduced its sensitivity score from 1.142 to 0.134. RCIC capacity
sensitivity also fell after mapping the sourced rated operating point. The
reference-leg score increased because the 30 s loss-of-feedwater sample lies
near a discrete low-level trip: it identifies protection timing as the dominant
remaining uncertainty, not a smooth uncertainty interval on power.
