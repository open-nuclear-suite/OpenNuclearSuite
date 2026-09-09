# Subchannel Thermal-Hydraulics Laboratory

This progressive teaching application begins with a steady, one-dimensional
heated channel. It is deliberately separate from the lumped LOCA simulator so
that channel, assembly, and later inter-assembly formulations can evolve without
changing the existing accident-training model.

Run from the repository root:

```powershell
python simulators/SubchannelLaboratory/main.py
```

The first implementation chunk provides:

- axial mass/energy conservation and homogeneous-equilibrium hydraulic loss;
- cellwise friction, signed elevation, acceleration, and total pressure-drop
  components with cumulative plots and an editable flow inclination;
- selectable homogeneous-mixture, Lockhart-Martinelli/Chisholm, Friedel, and
  steam-water-specific Martinelli-Nelson two-phase friction models with
  multipliers, phase Reynolds numbers, domain warnings, and boundary handling;
- selectable Blasius, Haaland, and Churchill friction correlations;
- selectable Dittus-Boelter and Gnielinski heat-transfer correlations;
- selectable uniform, sinusoidal, chopped-cosine, adjustable-offset cosine,
  adjustable-skew sine, and piecewise-linear axial heat-rate shapes, all
  normalized to preserve the requested total deposited power;
- heat-flux-intersection ONB selection with Jens-Lottes, Thom, or Chen
  nucleate-boiling wall-temperature models;
- the existing range-guarded Tong W-3 teaching CHF calculation;
- selectable, range-guarded Biasi CHF with simultaneous W-3/Biasi plot comparison
  and correlation-specific limiting-node markers;
- selectable, range-guarded Bowring CHF in its modified local-quality form;
- selectable, range-guarded base EPRI-1 rod-bundle CHF using inlet quality and
  local heat flux; cold-wall, grid, and nonuniform-power corrections remain off;
- selectable Groeneveld 2006 CHF lookup-table prediction with bounded trilinear
  interpolation, inspectable brackets/weights, and explicit K1, K2, and K4
  correction-factor controls (K1 enabled by default);
- deterministic power and flow hot-channel factors;
- reproducible statistical sampling of power, flow, pitch, and rod diameter;
- axial saturation temperature, equilibrium quality, void fraction, flow-regime,
  and W-3 validity displays;
- linearly interpolated ONB and bulk-saturation elevations with non-boiling,
  subcooled-boiling, and bulk two-phase heated lengths;
- selectable homogeneous, Zivi, Smith, and Zuber-Findlay drift-flux void models
  with slip ratio, phase velocities, model validity, and phase-boundary guards;
- selectable representative Zircaloy-4, 304 stainless steel, generic FeCrAl,
  and effective SiC cladding conductivities with inner-cladding temperatures;
- editable heated and unheated channel lengths, axial node count, pin pitch,
  rod/cladding diameters, and surface roughness;
- an orthographic white-background 3-D wireframe with axial mesh planes,
  regime-coloured centreline segments, selected-node highlighting, engineering
  dimensions drawn in the scene, and isometric/top/front/side presets;
- a plot-linked node inspector reporting velocity, mass flux, Reynolds,
  Prandtl and Nusselt numbers, friction factor, cumulative pressure drop,
  quality, void fraction, and DNBR.
- a progressive learning-stage selector that defaults to the single-channel
  model and exposes the center plus four common-plenum cardinal neighbors next;
- a selectable N/E/S/W/C channel map with prescribed per-channel power and solved flow
  multipliers, axial coolant-temperature and DNBR comparison plots, and explicit
  limiting-channel/limiting-node identification;
- a corresponding orbitable 3-D rod array showing the original center channel
  with north, east, south, and west channel cells, their axial regime tracks,
  the selected channel and node, and the limiting channel.

The total illustrated channel length is the heated length plus the declared
unheated inlet and outlet lengths. The present conservation and pressure-drop
decomposition is applied to the heated section; the unheated lengths currently
provide geometric context for the 3-D view and are not component-loss models.
Two-phase cells use the selected void/slip model to obtain mixture density,
phase velocities, elevation head, and momentum-flux acceleration. The friction
term is selectable between a teaching mixture-density form,
Lockhart-Martinelli/Chisholm, Friedel, or steam-water Martinelli-Nelson
multipliers. Local form losses remain a future chunk.

Martinelli-Nelson uses bounded bilinear interpolation of its published
pressure-quality multiplier table from 0.101 to 22.1 MPa. The selected-node
inspector reports the pressure and quality bracket used, and values outside the
table are not extrapolated; the solver continues with its homogeneous fallback
and a visible validity warning.
- PySide6 controls and plots managed by a reusable PyQtGraph handler.

Correlation calculations are labelled **valid** only inside their implemented
published ranges. Values may still be displayed outside a range for comparison,
but the UI reports the extrapolation. Tong W-3 remains unavailable rather than
being extrapolated.

Viscosity, thermal conductivity, and saturated surface tension are interpolated
from bounded tables generated through CoolProp's `IF97::Water` backend. Runtime
use does not require CoolProp. Two-phase correlations request explicit
saturated-liquid or saturated-vapor phase properties rather than an undefined
mixture viscosity.

Calculation results also carry structured provenance records for transport
properties, friction, single-phase heat transfer, nucleate boiling, CHF, void
fraction, and pressure drop. These records are intended for a later UI feature
that explains the active model when a user clicks or hovers over a calculated
value.

The run controls provide mutually exclusive **Deterministic** and
**Statistical** modes with one **Run selected mode** button. Sample count and
random seed are enabled only for statistical runs; returning to deterministic
mode clears the previous statistical histogram.

The PySide6 shell uses the suite's dark engineering-console visual system:
cyan section headings, framed dark panels, compact Fusion controls, blue action
buttons, and dark PyQtGraph canvases. The orthographic geometry view remains a
white engineering drawing for contrast and print-like inspection.

The control rail and central plots are separated by a draggable splitter. The
3-D view renders opaque fuel-rod/cladding cylinders around a translucent blue
coolant-channel volume. Its dock remains movable and resizable, but floating
and closing are disabled to avoid invalidating the live OpenGL context on
affected Windows graphics drivers. Camera presets avoid the exact 90-degree
view singularity.

The central PyQtGraph workspace is organized into Thermal, Boiling/CHF,
Hydraulics, and Statistics tabs. Each tab contains at most two vertically
resizable plots. A persistent selected-node strip and synchronized dotted axial
cursor follow plot clicks and the geometry node slider across all analysis tabs.
The Statistics tab is enabled after a statistical run and displays separate
minimum-DNBR and peak-wall-temperature histograms.

The modeless **Solution Inspector** mirrors the main case inputs and Run mode,
follows the selected axial node, and presents the calculation in Geometry,
Properties, Flow, Heat Transfer, Quality/Void, Pressure Drop, CHF/Margin, and
Statistics tabs. Geometry and correlation controls are linked bidirectionally;
outputs are read-only and edits are marked pending until the shared case is run.
Each solution page draws from the result's structured model provenance.

The **Export current channel CSV** action writes one machine-readable row per
axial node. It includes thermal, hydraulic, phase, pressure-drop, heat-transfer,
all CHF-model predictions and details, plus repeated channel totals and exit
conditions so the file remains self-contained when filtered or plotted.

## Development status

| Group | Scope | Status |
|---|---|---|
| 1 | Single-channel geometry, conservation, properties and single-phase transport | Implemented |
| 2 | ONB and selectable Jens-Lottes, Thom and Chen boiling models | Implemented |
| 3 | Pressure-drop decomposition and selectable two-phase friction | Implemented for heated section |
| 4 | Homogeneous, Zivi, Smith and drift-flux void/slip models | Implemented |
| 5 | Tong W-3, Biasi, Bowring, EPRI-1 and Groeneveld CHF comparison | Implemented |
| 6 | Groeneveld full table, interpolation provenance and uncertainty mask | Implemented |
| 7 | PyQtGraph workspace, 3-D channel view, node selection and Solution Inspector | Implemented |
| 8 | Deterministic and introductory statistical hot-channel factors | Implemented; advanced statistics deferred |
| 9 | Analytic axial heat shapes | Six normalized profiles implemented; editable/CSV profiles deferred |
| 10 | CSV result export | Implemented for deterministic channel results |
| 11 | NESWC common-plenum channels with fixed total flow and equal pressure drop | Implemented |
| 12 | Turbulent mixing and pressure-driven crossflow | Not started |
| 13 | Pin-resolved square assembly | Not started |
| 14 | Hexagonal lattice and bounded neighboring-assembly studies | Not started |

The default remains the completed **single-channel teaching stage**. The next
progression stage runs the center and four neighboring copies of that solver with common inlet
conditions and geometry. It conserves their total flow and iterates the channel
flows until the five heated-path pressure drops agree. This is common-plenum
parallel-flow coupling, not axial crossflow CFD: no mass, momentum, or enthalpy
is exchanged between channels along their heated lengths.

The main screen retains the simple channel-wide power and flow factors. The
separate **Advanced axial nuclear-power factors** window adds any number of localized power
factors with Gaussian, triangular, or rectangular support. Students can compare
direct multiplicative combination with an independent-uncertainty root-sum-square
(RSS) rule. The physical axial heat shape remains outside that uncertainty
combination, and RSS is distinct from the Monte Carlo statistical run mode. Users explicitly choose
between renormalized redistribution (constant requested total power) and
additional-power mode. The Thermal plot compares base and modified linear heat,
while the inspector and CSV expose the local multiplier and overall nodal power
factor. Localized flow-area or geometry factors are deferred because they
require a node-dependent hydraulic geometry rather than the present constant
channel area.

The editable factor scope is deliberately explicit. Available now are the
channel-wide power and flow factors plus localized axial power/linear-heat
factors (location, magnitude, width, support shape, and combination rule).
Deferred families include localized flow/mass-flux factors; local geometry,
roughness, spacer, and manufacturing-tolerance factors; pin-to-pin radial power,
formal Fq/F-delta-H decomposition, assembly, crossflow, and turbulent-mixing
factors; and correlation-bias or covariance models.

The editor presents an El-Wakil-style cause/effect coverage matrix. It distinguishes
nuclear, engineering-mechanical, engineering-distribution, and modern-extension
sources; identifies whether each can affect bulk-coolant (Fc), coolant-film (Ff),
or fuel-element (Fe) temperature rise; and marks each source as editable, partial,
indirect, or future. The current user-defined hotspot is labelled specifically as
a localized axial nuclear power-distribution factor. The model does not yet claim
an explicit Fc/Ff/Fe factor decomposition, and Fe remains unavailable until a
fuel-pellet/gap conduction model is added.

### Groeneveld 2006 table provenance

`2006LUTdata.txt` is the MIT-licensed Greenwood transcription of the table
published by Groeneveld et al. (2007); its license is retained in
`GROENEVELD_DATA_LICENSE.txt`. SHA-256:
`BD113FE78E43697200B7AF69151DDE4CE159E9B2B8BE1F615F7E54778AA0E92C`.
The complete numeric matrix contains 24 pressure planes: 0.1, 0.3, 0.5, and
1 through 21 MPa. The journal's Appendix B prints 15 of these planes and states
that intermediate pressures were omitted for space. Runtime loading requires
the exact 24 × 21 × 23 shape. A validation routine checks the source-file
checksum and published anchor cells spanning all 15 printed planes, preventing
silent pressure-axis shifts. Queries outside the declared axes return
unavailable rather than being clamped or extrapolated.

`groeneveld_uncertainty.csv` is a separate 24 × 21 × 23 categorical mask
extracted cell by cell from NUREG Appendix C. Classes preserve the publication's
meaning: direct experimental-data region, calculated/extrapolated region,
avoid-extrapolation region, and low-quality region (LQR). The extraction utility
detects the scanned table grid and background tones; the runtime loader verifies
the CSV checksum, coordinate sequence, class range, and class counts. These
categories are provenance warnings, not invented numerical error percentages.
For each Groeneveld prediction the interpolation reports the weight-dominant
class and, separately, the worst class among nonzero contributing corners. The
Solution Inspector displays both with the pressure, mass-flux, and quality
brackets; numerical availability is kept separate from the caution category.

Run the focused tests with:

```powershell
python -m unittest simulators.SubchannelLaboratory.test_single_channel -v
```

## Deferred teaching roadmap

- user-editable nodal factors, heat-profile CSV import, and later neutronics coupling;
- hover/click provenance for major calculated values and active correlations;
- unheated-section friction, spacer-grid/form losses, and inlet/outlet losses;
- optional MacBeth and modified-Zuber CHF comparisons after their complete
  open formulations and selection boundaries are independently verified; GEXL
  remains excluded;
- a crossflow teaching model, followed by pin-resolved square assemblies and later hexagonal-lattice
  comparison;
- bounded neighboring-assembly studies only after single-assembly scaling is
  characterized;
- expanded statistical hot-channel-factor composition, including correlated
  and non-normal uncertainty choices and convergence diagnostics.
