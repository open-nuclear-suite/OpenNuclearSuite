# Water and steam property-table provenance

## Source formulation

The bundled `data/if97_ph_table.npz` archive was generated with CoolProp 8.0.0
using its explicit `IF97::Water` backend. The underlying industrial formulation
is **IAPWS R7-97(2012), Revised Release on the IAPWS Industrial Formulation 1997
for the Thermodynamic Properties of Water and Steam**:

<https://iapws.org/relguide/IF97-Rev.pdf>

The table-lookup architecture is informed by **IAPWS G13-15, Guideline on the
Fast Calculation of Steam and Water Properties with the Spline-Based Table
Look-Up Method**:

<https://iapws.org/documents/release/SBTL>

This implementation uses bilinear interpolation and does not claim to implement
the complete SBTL spline construction.

## Runtime domain and contents

- Pressure: 0.1--20 MPa on a nonuniform 111-point grid
- Specific enthalpy: 100--3600 kJ/kg on a 351-point grid
- Stored fields: temperature, specific volume, internal energy, and single-phase
  isobaric heat capacity
- Saturation fields: temperature, liquid/vapor enthalpy, specific volume,
  internal energy, and heat capacity

Pressure-enthalpy states inside the saturation dome use quality and linear
mixture relations for specific volume and internal energy. Specific volume is
interpolated instead of density because it follows the equilibrium mixture
relation directly.

Out-of-range requests raise `PropertyRangeError`; the runtime never silently
extrapolates.

## Reproduction

Install the generation-only dependency and regenerate from the repository root:

```powershell
python -m pip install -r simulators/ThermalHydraulicsSimulator/tools/requirements.txt
python simulators/ThermalHydraulicsSimulator/tools/generate_if97_tables.py
```

CoolProp is not a runtime dependency. PyInstaller build scripts explicitly
bundle the generated archive.

## Verification

`test_steam_properties.py` checks:

- formulation and generator metadata;
- published-generation reference states at nominal PWR pressure;
- off-grid interpolation against independently recorded IF97-generation values;
- saturation inversion and monotonicity;
- two-phase quality and specific-volume mixture relations; and
- explicit rejection of states outside the declared domain.

The current off-grid acceptance limits are 0.02 °C for temperature, 0.05% for
density, and 0.01 kJ/kg for internal energy at the selected verification states.

Standard-based properties do not validate the simulator's system equations,
component models, boiling or CHF correlations, or accident predictions.
