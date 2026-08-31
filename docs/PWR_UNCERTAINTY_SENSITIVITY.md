# PWR P2-1 uncertainty and sensitivity screening

## Purpose and interpretation

P2-1 adds deterministic numerical-robustness and local-sensitivity tools for
the representative PWR teaching surrogate. The executable authority is
`simulators/ThermalHydraulicsSimulator/pwr_uncertainty.py`.

The analysis asks two limited questions:

1. Are the P1-4 transient endpoints materially changed by halving the normal
   0.05 s integration timestep?
2. Which declared generic parameters most affect representative responses when
   individually perturbed by plus or minus 20%?

The perturbation is an engineering screening band, not a confidence interval,
equipment tolerance, failure probability, or probabilistic safety assessment.
The calculation omits parameter interactions and model-form uncertainty.

## Numerical robustness

The largest normalized endpoint difference among power, pressure, inventory,
primary flow, void, and secondary pressure was:

| Scenario and duration | Maximum normalized difference |
|---|---:|
| SBLOCA, 30 s | 0.00263 |
| LBLOCA, 30 s | 0.00172 |
| Loss of flow, 15 s | 0.00365 |
| Loss of heat sink, 30 s | 0.00003 |
| Station blackout, 30 s | 0.00158 |

All are below the executable 0.01 gate. The harness separately integrates the
absolute aggregate mass/energy equation residuals, state-projection mass/energy
corrections, and steam-generator secondary residuals. This prevents a bounded
projection from being misreported as equation closure.

## Local sensitivity ranking

The score is the largest absolute dimensionless central sensitivity among final
power, pressure, inventory, flow, void, and secondary pressure; peak pressure
and cladding temperature; minimum inventory; and trip time.

| Rank | Parameter and representative case | Score | Interpretation |
|---:|---|---:|---|
| 1 | Effective loop-loss head — loss of flow | 0.813 | Dominates the new resolved loop-flow state |
| 2 | RCP shutoff head — loss of flow | 0.794 | Comparable loop momentum dependence |
| 3 | Break discharge coefficient — SBLOCA | 0.524 | Dominates void response and materially affects inventory |
| 4 | HPSI runout capacity — SBLOCA | 0.256 | Material makeup and void sensitivity |
| 5 | Secondary pressure-energy capacitance — SBLOCA | 0.140 | Local influence on secondary pressure only |
| 6 | LPSI runout capacity — LBLOCA | 0.116 | Material minimum-inventory sensitivity |
| 7 | Pressurizer response time — loss of heat sink | 0.008 | Small response before pressure projection dominates |
| 8 | Axial-void reactivity coefficient — SBO | 0.001 | Post-trip case weakly excites this feedback |

## Priority and architectural findings

1. Replace the effective RCP and loop-loss calibration with a defensible common
   system boundary and pump/loop data.
2. Establish break-area and discharge-coefficient provenance appropriate to the
   homogeneous reduced-order opening.
3. Replace generic HPSI/LPSI curves with sourced rated points and documented
   shutoff-head behavior.
4. Establish secondary inventory, pressure-capacitance, and AFW/steam-flow data.
5. Reassess pressurizer response with explicit relief capacity before using
   pressure-limited LOHS/SBO cases for parameter inference.
6. Screen axial reactivity with a powered rod/void maneuver; a post-trip SBO is
   insufficiently informative.

The high loop-head scores primarily affect the P1-2 resolved flow diagnostic
and steam-generator coupling. The legacy aggregate primary heat-transfer RHS
retains its calibrated pump-command response for backward compatibility. This
partial coupling is an architectural gap to resolve before interpreting the
head sensitivities as whole-plant response uncertainty.

## Post-P2-2 rerun

The table above is the post-P2-2 result. Replacing the rated thermal,
temperature, head, and steam-generator reference family reduced the break score
from 0.606 to 0.524 and HPSI from 0.274 to 0.256. The source-backed secondary
reference makes the model-specific pressure-capacitance sensitivity more
visible (0.140). RCP and loop-loss scores are unchanged because P2-2 adopted a
single rated head point but retained the generic quadratic curve and partial
aggregate-RHS coupling.
