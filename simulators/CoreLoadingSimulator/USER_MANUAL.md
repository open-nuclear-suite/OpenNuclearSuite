# Core Loading Simulator User Manual

## 1. Purpose and scope

The Core Loading Simulator is an assembly-level teaching application for
exploring how an 11 x 11 loading pattern affects neutron flux, relative power,
burnup, leakage, control requirements, and selected thorium-cycle quantities.
It also supports multi-cycle assembly tracking and a guided refueling workflow.

The application uses simplified, classroom-scaled, homogenized physics. Its
results are qualitative and must not be used for reactor design, licensing,
safety analysis, criticality safety, operator training, or real fuel-management
decisions.

## 2. Starting the simulator

### From the Windows release

For the folder-based release, keep the executable beside its `_internal`
folder, then run:

```text
Core-Loading-Simulator\Core-Loading-Simulator.exe
```

For the standalone release, run:

```text
Core-Loading-Simulator.exe
```

The first launch may take several seconds. Windows SmartScreen may warn about
an unsigned application; verify the release checksum before proceeding.

### From Python source

From the repository root, install the requirements and run:

```powershell
python -m pip install -r requirements.txt
python simulators/CoreLoadingSimulator/main.py
```

Windows users with the project virtual environment installed may instead
double-click `run_core_loading_simulator.bat`.

## 3. Screen layout

The main window has three working areas:

1. **Left control pane** — assembly palette, presets, control banks, refueling,
   cycle controls, save/load, and export.
2. **Core loading map** — the editable 11 x 11 assembly map. Row and column
   labels identify positions such as `R06-C06`.
3. **Right results pane** — metric selection, top/3-D/trend plots, calculated
   indicators, and status messages.

The left and right panes scroll independently. Place the mouse over the pane
you want to scroll. Maximize the window on a small display.

## 4. Quick-start equilibrium-cycle exercise

This is the recommended first run.

1. Select **Conventional 3-batch PWR** under Loading Presets.
2. Leave control-bank insertion at 0% initially.
3. Select **Power** as the result metric and **Split** as the view.
4. Click **RECALCULATE CURRENT STATE**.
5. Inspect uncontrolled k-effective, controlled operating k, required soluble
   boron, radial power peak, leakage, and the power map.
6. Set **Full-power days per step** to 30.
7. Set **Stop at exposure** to the desired cycle exposure, for example 900 FPD.
8. Click **Run cycle**. Use **Pause** at any time, or use **Single cycle step**
   for controlled progression.
9. Change the result metric to **Burnup**, **Xenon-135**, **Samarium-149**, or
   **Power change: BOC** to examine cycle evolution.
10. Select **Trends** to inspect whole-core history.

The cycle calculation is a sequence of spatially coupled steady depletion
states. It is not a seconds-scale reactor transient.

## 5. Constructing or editing a core

### Loading presets

- **Conventional 3-batch PWR** creates a symmetric illustrative equilibrium
  loading with fresh, once-burned, and twice-burned fuel.
- **Thorium seed-blanket** creates a seed-and-blanket teaching arrangement.
- **Thorium checkerboard** creates an alternating thorium-oriented pattern.
- **Clear active core** empties all active positions.

### Manual editing

1. Choose an assembly type in the Assembly Palette.
2. Read its description and relative properties below the palette.
3. Click an available core position to place that type.
4. Continue clicking to place the same type in other positions.
5. Right-click a position to clear it.
6. Click **RECALCULATE CURRENT STATE** after editing.

Available palette types include fresh LEU fuel, once-burned fuel,
twice-burned fuel, fresh fuel with burnable absorber, thorium blanket,
U-233/thorium seed, reflector/low-power blanket, and empty position.

Loading an assembly onto the main map creates or updates a model state. For
multi-cycle work in which the identity of each used assembly matters, use the
guided refueling workspace described in Section 11.

## 6. Recalculate versus cycle advancement

**RECALCULATE CURRENT STATE** solves the current steady neutron and thermal
state without advancing exposure. Use it after changing the loading pattern or
control insertion.

**Single cycle step** advances by the number of full-power days entered in
**Full-power days per step**, updates depletion and poison inventories, and
then solves the new spatial state.

**Run cycle** repeats those steps using the selected animation delay until it
is paused or reaches a stopping condition. **Stop on k/peaking warning** ends
the automatic run when the configured teaching limits are encountered.

**Reset burnup only** returns depletion-related state to its initial condition.
Use it cautiously: it is intended for restarting a teaching exercise, not for
preserving a multi-cycle fuel-management history.

## 7. Selecting and viewing results

Choose a metric from the right-pane list:

- **Flux**, **Fast flux**, and **Thermal flux** show normalized spatial neutron
  fields.
- **Power** shows normalized local assembly power.
- **Power index** shows an unnormalized power-related quantity useful for
  seeing overall depletion effects.
- **Power change: previous** compares the present state with the preceding
  step.
- **Power change: BOC** compares the present state with beginning of cycle.
- **Burnup** shows cumulative assembly exposure.
- **Breeding** highlights thorium-to-U-233-related behavior.
- **Fuel temperature**, **Moderator temperature**, and **Moderator density**
  display the feedback state.
- **Xenon-135** and **Samarium-149** display modeled neutron poisons.
- **Control insertion** shows the controlled positions and insertion level.

**Lock scale to BOC** keeps a stable color scale so automatic rescaling does
not hide spatial changes. **Show values** overlays numerical values on the core
map.

### Plot views

- **Top** — assembly-centered plan view.
- **3D** — interpolated surface view.
- **Split** — top and 3-D views together.
- **Trends** — time histories for the core and selected assembly.

Drag the 3-D surface to rotate it. Use the mouse wheel over the plot to zoom.
Click **Reset camera** to restore the default angle and zoom.

The 3-D surface is a smoothed display interpolation. Extrapolated values beyond
the active-core boundary illustrate falloff. These display values do not feed
back into the physics calculation.

## 8. Understanding key indicators

- **Uncontrolled k-effective** is the eigenvalue before soluble-boron control.
- **Controlled operating k** is the result after control effects and the
  illustrative boron search.
- **Required soluble boron** is the estimated concentration needed to approach
  critical operation when sufficient excess reactivity exists.
- **Radial power peak** is the maximum normalized assembly power.
- **Leakage index** is a qualitative measure of neutron loss at the boundary.
- **Thorium conversion ratio** summarizes modeled fertile conversion.
- **Centre-to-edge flux ratio** compares central and peripheral flux.
- **North-south** and **east-west flux tilt** indicate directional imbalance.
- **Flux centroid offset** shows displacement of the flux-weighted center.
- **Inserted control worth**, **all-banks-in k**, and **shutdown margin** are
  simplified control-bank teaching indicators.
- **Average fuel burnup** and **fuel burnup spread** summarize the loaded core.

Values should be interpreted comparatively—for example, before and after a
loading change—not as predictions for an actual reactor.

## 9. Inspecting an individual assembly

1. Shift-click an occupied main-core position.
2. Confirm its position and permanent assembly ID in the indicators.
3. Select **Trends** to follow that assembly's flux, power, burnup, Pa-233, and
   U-233 history.
4. Use **Open assembly inventory** for a table of all in-core and stored
   assemblies.
5. Select an inventory row and choose **View complete history** for its event
   and irradiation records.

Assembly history follows the permanent ID, not the grid position. Moving an
assembly therefore moves its burnup and isotope state with it.

## 10. Applying control-bank insertion

1. Enter a value from 0 to 100 in **Symmetric bank insertion (%)**.
2. Click **Apply insertion**.
3. Compare uncontrolled k, controlled operating k, control worth, power shape,
   and shutdown margin.
4. Click **Withdraw** to return the bank insertion to zero.

The simulator applies one insertion percentage to a predefined symmetric set
of control positions. It does not model detailed individual rod motion.

## 11. Guided refueling procedure

The guided workspace is the preferred way to prepare a next-cycle loading. It
works on a draft copy; **Cancel** leaves the operating core unchanged.

### 11.1 Open and unload

1. Save the current refueling state as a precaution.
2. Click **OPEN GUIDED REFUELING WORKSPACE**.
3. Set the desired outage duration.
4. Click **1 Unload core to staging**.

The outgoing positions are archived, the completed irradiation cycle is
credited, and the assemblies are sorted into:

- Once-burned rack
- Twice-burned rack
- Special/extended rack
- New-fuel supply
- Spent pool

### 11.2 Reload irradiated assemblies

Each used-fuel row represents one physical assembly and is therefore
single-use.

1. Select a rack tab.
2. Inspect assembly ID, burnup, completed cycles, and previous position.
3. Click a row and then click an empty core position, or drag the row onto the
   core.
4. Repeat with other eligible assemblies.

Loading onto an occupied position returns the displaced assembly to its rack.
Assemblies already in the draft core can be dragged to move or swap them.

### 11.3 Add new fuel efficiently

1. Open the **New fuel supply** tab.
2. Select the desired new-fuel type once.
3. The row remains highlighted and active.
4. Click as many available core positions as required.
5. Each click creates a distinct permanent assembly ID of the selected type.
6. Click **Clear selection** when finished with that type.

### 11.4 Correct and validate the draft

- Use **Undo** and **Redo** to revise draft-loading actions.
- Use **Mark selected as spent** to move an eligible discharged item to the
  spent pool.
- Click **Validate loading** before preview or commit.

Validation checks empty positions, duplicate IDs, assembly status, ordinary
fuel-cycle eligibility, k-effective, boron requirement, radial peaking, and
shutdown margin. Errors must be corrected. Warnings call attention to unusual
but reviewable teaching-model conditions.

### 11.5 Preview and commit

1. Click **Preview EOC → BOC**.
2. Compare the previous end-of-cycle and proposed beginning-of-cycle power
   maps and summary indicators.
3. Return to the draft and adjust the pattern if necessary.
4. Click **COMMIT LOADING AND BEGIN NEXT CYCLE** only when satisfied.

Commit applies outage decay, transfers the draft into the operating model,
increments the fuel cycle, and solves the new BOC state. **Cancel** discards
the draft instead.

## 12. Saving, loading, and exporting

### Save refueling state

Use **Save refueling state** to create a JSON file containing the core layout,
storage pool, isotope states, permanent assembly IDs, cycle counters, and
assembly histories. Save before a major reload and again after a successful
commit.

### Load state

Use **Load state** to restore a saved JSON session. Loading replaces the
current simulator state, so save current work first if it must be retained.

### Export current core CSV

Use **Export current core CSV** to create a spreadsheet-ready snapshot of the
current assembly states and calculated indicators. CSV export is for analysis;
use JSON when a session must later be resumed.

## 13. Suggested classroom investigations

1. Run the conventional three-batch preset from BOC toward EOC and examine the
   relationship among uncontrolled k, required boron, burnup, and power shape.
2. Move a fresh assembly from the periphery toward the center and compare
   power peaking and directional tilt.
3. Replace selected fresh assemblies with burnable-absorber assemblies and
   compare early-cycle power and reactivity.
4. Compare the thorium seed-blanket and checkerboard presets using breeding,
   Pa-233/U-233 assembly trends, and conversion ratio.
5. Perform a full reload while retaining assembly identities, then compare EOC
   and next-cycle BOC power maps.
6. Apply several symmetric bank insertion levels and observe changes in power
   distribution, controlled k, and control worth.

Change one factor at a time and save or export each reference case.

## 14. Troubleshooting

- **Controls or indicators are hidden:** maximize the window and scroll the
  left or right pane while the pointer is over it.
- **The 3-D plot does not zoom:** place the pointer directly over the plot and
  use the mouse wheel.
- **Recalculate does not advance burnup:** this is expected; use Single cycle
  step or Run cycle.
- **Power appears to change very little:** inspect Power index or Power change
  rather than only the repeatedly normalized Power map.
- **The automatic cycle stops early:** inspect the status message, stopping
  exposure, and Stop on k/peaking warning option.
- **A reload cannot be committed:** run Validate loading and correct every
  listed error, especially empty positions or ineligible spent fuel.
- **A used assembly disappears from its rack:** it has already been placed in
  the draft core; each used-assembly card is single-use.
- **A new-fuel type keeps placing assemblies:** click Clear selection to end
  sticky new-fuel placement.
- **A saved session cannot be found:** JSON state and CSV exports are written
  to the location chosen in the save dialog, not automatically to the program
  folder.

## 15. Recommended operating practice

For a reproducible teaching session:

1. Load a named preset or a saved JSON baseline.
2. Record the selected step size, stopping exposure, control insertion, and
   displayed metric.
3. Save the BOC state.
4. Run or step the cycle.
5. Export the desired data at comparison points.
6. Save before entering the guided refueling workspace.
7. Validate and preview every reload before committing it.
8. Preserve the post-commit JSON state for the next class or experiment.

