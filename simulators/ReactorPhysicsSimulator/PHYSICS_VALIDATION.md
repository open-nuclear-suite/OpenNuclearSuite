# Reactor simulator physics verification and validation

Tested on 2026-08-07. Run the reproducible suite from the repository root:

```powershell
python -m unittest discover -s simulators/ReactorPhysicsSimulator -p "test_*.py" -v
```

## Meaning of verification and validation

Verification asks whether the implemented equations are solved consistently
with their specification. Validation asks whether model behavior is adequate
for its declared use. This simulator is deliberately time-scaled and
lumped-parameter teaching software, so it cannot be validated as a predictor
of an actual reactor or plant transient.

The validation claim tested here is narrower: the model reproduces the
declared qualitative relationships used in introductory teaching, preserves
equilibria, and responds in the expected direction when a controlled variable
changes.

## Verification evidence

| Subsystem | Independent check | Acceptance criterion | Result |
| --- | --- | --- | --- |
| Delayed precursors | Evaluate all six precursor derivatives at initialization | Absolute residual below `1e-15` | Pass |
| Critical kinetics | Source-free, zero-reactivity 100 s transient | Power remains within `1e-10` of initial value | Pass |
| Reactor period | Independent six-group inhour root for a `+20 pcm` step | Simulated asymptotic growth rate within `0.2%` | Pass; approximately `0.11%` difference |
| Time integration | Repeat a 20 s transient at `dt = 0.04, 0.02, 0.01, 0.005 s` | Error decreases under refinement; production-step relative difference below `1e-7` | Pass |
| Representative LWR equilibrium | Source-free critical state with `Lambda = 2.0e-5 s` and a 3000 MWth reference | Normalized power and dimensional heat remain at 100% / 3000 MWth | Pass |
| Representative LWR integration | Initialize the independent positive inhour eigenmode for a `+20 pcm` insertion | RK4/substep growth rate within `0.2%` of the inhour root | Pass |
| Representative LWR SCRAM | Initiate a full SCRAM from equilibrium | Rod bank moves at the declared finite insertion rate rather than instantaneously | Pass |
| Representative LWR thermal equilibrium | Independently evaluate deposition, node-to-node transfer, and heat removal at rated conditions | 2910, 2970, and 3000 MW transfers with stationary node temperatures | Pass |
| Representative LWR energy conservation | Reduce the heat sink for one isolated thermal step and compare stored energy with generated minus removed heat | Agreement within floating-point tolerance and zero algebraic balance residual | Pass |
| Rod worth | Monotonicity, symmetry, and finite-difference derivative | Curve monotonic and antisymmetric; analytic and numerical slopes agree within `1e-7 pcm/%` | Pass |
| Xe/I and Sm/Pm | Evaluate four equilibrium equations directly | Absolute residual below `1e-15` | Pass |
| Decay heat | Compare initialized groups with their equilibrium definition | Machine-precision agreement and total heat equals initial power | Pass |
| Thermal nodes | Independently calculate coolant, clad, and fuel equilibrium temperatures | Machine-precision agreement | Pass |
| Exposure | Independently evaluate the declared linear excess-reactivity law | Agreement to 14 decimal places | Pass |
| CSV provenance | Compare generated row keys with the declared schema | No missing or extra columns | Pass |

## Educational validation evidence

- After a power reduction, iodine and promethium decrease while xenon and
  samarium initially increase.
- Increasing fuel or moderator temperature inserts negative reactivity.
- Reduced moderator density inserts negative reactivity under the configured
  coefficient.
- A stronger external source produces a higher neutron level while the startup
  state remains subcritical.
- BOC exposure advances only in the explicitly selected compressed teaching
  cycle and reduces the declared excess-reactivity term.
- The classroom-default implementation was separately compared with the
  pre-extension simulator for a seeded 60 s transient. Power, precursors,
  poisons, temperatures, rod position, and total reactivity agreed within
  `1e-12`.
- Twenty-seven combinations of kinetics preset, poison timescale, startup
  state, and cycle state completed a 60 s finite-value matrix test.

## Important limitations and unresolved validation gaps

No comparison has been made with measured reactor data, a licensed kinetics
code, evaluated nuclear-data libraries, or a plant-specific safety-analysis
model. The following are illustrative rather than physically validated:

- effective prompt-generation times and compressed poison half-times;
- normalized poison yields, burnout constants, and poison worths;
- integral rod-worth shape and total worth;
- moderator-density and void feedback coefficients;
- source detector thresholds and source-strength units;
- one-EFPD-per-second cycle compression, excess-reactivity curve, and boron
  target;
- lumped three-node temperatures and protection thresholds.
- the 3000 MWth Representative LWR rating, which is a declared teaching
  reference and is not tied to a specific plant design;
- conversion of the declared effective thermal inventories and conductances,
  or normalized poison parameters, into plant-specific equipment performance.

Consequently, passing these tests supports classroom consistency and numerical
correctness only. It does not support reactor design, licensing, operator
training, safety analysis, or prediction of real transient magnitudes or time.
