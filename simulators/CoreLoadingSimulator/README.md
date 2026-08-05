# Core Loading Simulator

An interactive 11 x 11 assembly-level teaching simulator for exploring how
loading patterns affect simplified neutron flux, relative power, burnup,
leakage, and thorium fuel-cycle indicators.

Run from this directory with:

```powershell
python main.py
```

For step-by-step operating instructions, see [USER_MANUAL.md](USER_MANUAL.md).

## Main capabilities

- Editable rounded 11 x 11 core with conventional and thorium-bearing assembly types
- Conventional three-batch PWR, thorium seed-blanket, and checkerboard presets
- Coupled fast/thermal two-group diffusion k-eigenvalue calculation
- Fission-rate-derived assembly power without empirical profile compression
- Full-power-day cycle advancement with U-235, Pu-239, burnable absorber,
  Pa-233, and U-233 inventories
- Iterated assembly fuel-temperature, moderator-temperature, and density feedback
- Equilibrium full-power I-135/Xe-135 poisoning and long-term Pm-149/Sm-149 depletion
- Symmetric 2-D control-bank insertion, rod worth, and shutdown-margin estimates
- Permanent assembly IDs and `Rxx-Cxx` core-position identifiers
- State-preserving assembly moves, swaps, discharge, storage, and reload
- Multi-cycle per-assembly histories and outage decay
- JSON save/load of the complete core, storage pool, and assembly register
- Run, pause, single-step, animation-speed, and automatic-stop controls
- Flux, power, burnup, and breeding displays
- Calculated top view, rotatable interpolated 3-D surface, or split view
- Core trends and selected-assembly flux, power, burnup, Pa-233, and U-233 histories
- Uncontrolled k-effective, controlled operating k, and illustrative soluble-boron requirement
- Normalized power, unnormalized power index, and previous-step/BOC power-change maps
- Radial peaking, leakage, conversion, centre-to-edge, directional tilt, and
  flux-centroid indicators
- CSV export of assembly state and calculated indicators

The smooth 3-D plot is a display layer. Assembly-centre values come from the
model; values between positions are interpolated. Flux and power receive an
illustrative falloff outside the active-core boundary. Burnup and breeding are
zeroed outside material-bearing positions. Display-derived values never feed
back into the model.

## Cycle evolution

Set the full-power days per step, animation delay, and stopping exposure. Use
**Run cycle** for animated depletion, **Pause** to stop it, or **Single cycle
step** for one update. The run can stop automatically when its requested
exposure or the illustrative k/peaking warning threshold is reached.

Choose **Trends** in the result-display view to see whole-core history. Use
Shift-click on an active core position to select an assembly for its individual
history without changing the loading pattern. Ordinary click places the palette
selection, and right-click clears a position. Editing or loading a new pattern
starts a new history series.

**Recalculate current state** updates the steady solution without advancing
time. Cycle evolution is a sequence of spatially coupled steady-state depletion
steps; it is not a seconds-scale reactor-kinetics transient.

The conventional three-batch preset uses a classroom two-group cross-section
dataset calibrated as an illustrative equilibrium cycle. Uncontrolled k begins
above unity; an iterative boron search changes thermal absorption until the
eigenvalue approaches 1.000; and the boron requirement approaches zero near
end of cycle. The reported k is the eigenvalue of the discretized diffusion
equations, rather than a transformation applied to a separate reactivity
index. These remain teaching results, not design predictions.

Use **Power change: previous** or **Power change: BOC** to reveal spatial
redistribution that may be hard to see in a repeatedly normalized power map.
Cell values use three decimal places. **Lock scale to BOC** prevents changing
color limits from visually hiding depletion-driven changes.

The controls and results panes scroll independently. In a 3-D or split view,
drag the surface to rotate it and use the mouse wheel over the plot to zoom.
The camera angle and zoom persist across recalculation; **Reset camera** restores
the default view.

## Feedback, poisons, and control banks

Each steady cycle state iterates local fission power with fuel temperature,
moderator temperature/density, and equilibrium full-power xenon before the
boron criticality search is finalized. Pm-149 and Sm-149 evolve during cycle
steps. These fields can be inspected through their result-display maps.

The control-bank control applies one insertion percentage to a predefined
symmetric set of 29 core positions. Rod absorption participates directly in
both energy-group equations. Boron then performs fine criticality control when
sufficient excess reactivity remains. The indicators report inserted control
worth, an all-banks-in eigenvalue, and an illustrative shutdown margin.

The Xe-135 treatment represents equilibrium full-power operation; it is not an
hourly startup, shutdown, or xenon-oscillation transient model.

## Refueling and assembly tracking

Every non-empty assembly receives a permanent ID such as `FA-0001`, while each
active core location uses a position ID such as `R06-C06`. Hovering over a cell
shows both identifiers. Row and column position labels are also drawn around
the core map.

Enable **Refueling move/swap mode**, click an occupied source position, then
click a target. An empty target moves the assembly; an occupied target swaps
the two assemblies. Burnup, heavy-metal inventories, burnable absorber,
fission products, temperatures, cycle count, and history follow the assembly.

Use **Discharge selected to storage** to remove an assembly from the core. A
stored assembly can later be selected in the pool list and loaded at the
currently selected position. If that position is occupied, its assembly moves
to storage.

**Begin next cycle** applies the specified zero-power outage duration. I-135,
Xe-135, Pa-233, and Pm-149 decay analytically; Pa decay contributes U-233 and
Pm decay contributes Sm-149. Burnup and long-lived heavy-metal inventories are
retained, the cycle number increments, and the new loading is solved at BOC.

**Open assembly inventory** lists every in-core and stored assembly, its current
position, cumulative burnup, completed cycles, last power, and history length.
The complete history table records cycle, total exposure, event, position,
burnup, flux, power, U-235, and Pu-239. The Trends view follows the permanent
assembly ID rather than merely following its present grid cell.

Save the refueling state as JSON to preserve the core layout, storage pool,
isotope states, permanent IDs, cycle counters, and complete assembly histories
for a later session.

### Guided refueling workspace

Use **Open guided refueling workspace** for the transactional outage workflow.
It operates on a draft copy; Cancel leaves the operating core unchanged.

1. **Unload core to staging** archives the outgoing positions, credits the
   completed irradiation cycle, empties the draft core, and sorts assemblies.
2. The racks classify ordinary fuel as once burned, twice burned, or spent.
   Thorium, seed, and reflector assemblies use the special/extended rack. A
   separate new-fuel supply creates new permanent IDs.
3. Select a rack row and click a core position, or drag the row onto the core.
   A selected **new-fuel supply** type stays highlighted and active, so you can
   fill several positions with repeated clicks; every click creates a distinct
   permanent assembly ID. Use **Clear selection** to stop placing that type.
   Irradiated-fuel cards remain single-use because each card is one physical
   assembly. In-core assemblies can also be dragged or selected and moved.
   Loading onto an occupied position returns the displaced assembly to its rack.
4. Undo and Redo preserve a reversible draft-loading transaction.
5. **Validate loading** checks completeness, duplicate IDs, status consistency,
   cycle eligibility, k, boron, peaking, and shutdown margin.
6. **Preview EOC → BOC** compares previous end-of-cycle and proposed
   beginning-of-cycle power maps and indicators.
7. **Commit loading and begin next cycle** applies outage decay and replaces
   the operating core only after validation. Cancel discards the draft.

Rack columns can be sorted by assembly ID, burnup, completed cycles, or previous
position. The inspector shows burnup, heavy-metal inventories, last position,
eligibility category, and history length for the selected assembly.

## Scope

This application uses classroom-scaled, assembly-homogenized relationships.
It is not suitable for reactor design, licensing, safety analysis, criticality
safety, operator training, or real fuel-management decisions.
