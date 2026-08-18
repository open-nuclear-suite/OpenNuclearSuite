"""Generate compact runtime water-property tables from IAPWS-IF97.

Generation dependency: CoolProp (not required by the simulator at runtime).
The backend is explicitly selected as ``IF97::Water``.  Generated data cover
the teaching simulator's declared 0.1--20 MPa and 100--3600 kJ/kg domain.

Reference formulation:
    IAPWS R7-97(2012), Revised Release on the IAPWS Industrial Formulation
    1997 for the Thermodynamic Properties of Water and Steam.

The runtime interpolator follows the table-lookup approach recommended by
IAPWS G13-15, although this compact educational implementation uses bilinear
interpolation rather than the guideline's full spline construction.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import CoolProp
from CoolProp.CoolProp import PropsSI


FLUID = "IF97::Water"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "if97_ph_table.npz"


def prop(output: str, pressure_mpa: float, key: str, value: float) -> float:
    return float(PropsSI(output, "P", pressure_mpa * 1.0e6, key, value, FLUID))


def generate() -> None:
    pressure_mpa = np.unique(
        np.concatenate(
            ([np.linspace(0.1, 1.0, 19), np.linspace(1.0, 5.0, 33), np.linspace(5.0, 20.0, 61)])
        )
    )
    enthalpy_kj_kg = np.linspace(100.0, 3600.0, 351)

    sat_names = ("temperature_C", "hf", "hg", "vf", "vg", "uf", "ug", "cpf", "cpg")
    saturation = {name: np.empty(pressure_mpa.size) for name in sat_names}
    for i, pressure in enumerate(pressure_mpa):
        saturation["temperature_C"][i] = prop("T", pressure, "Q", 0.0) - 273.15
        saturation["hf"][i] = prop("H", pressure, "Q", 0.0) / 1000.0
        saturation["hg"][i] = prop("H", pressure, "Q", 1.0) / 1000.0
        saturation["vf"][i] = 1.0 / prop("D", pressure, "Q", 0.0)
        saturation["vg"][i] = 1.0 / prop("D", pressure, "Q", 1.0)
        saturation["uf"][i] = prop("U", pressure, "Q", 0.0) / 1000.0
        saturation["ug"][i] = prop("U", pressure, "Q", 1.0) / 1000.0
        saturation["cpf"][i] = prop("C", pressure, "Q", 0.0) / 1000.0
        saturation["cpg"][i] = prop("C", pressure, "Q", 1.0) / 1000.0

    shape = (pressure_mpa.size, enthalpy_kj_kg.size)
    temperature_C = np.empty(shape)
    specific_volume = np.empty(shape)
    internal_energy_kj_kg = np.empty(shape)
    cp_kj_kgK = np.empty(shape)

    for i, pressure in enumerate(pressure_mpa):
        hf, hg = saturation["hf"][i], saturation["hg"][i]
        for j, enthalpy in enumerate(enthalpy_kj_kg):
            temperature_C[i, j] = prop("T", pressure, "H", enthalpy * 1000.0) - 273.15
            specific_volume[i, j] = 1.0 / prop("D", pressure, "H", enthalpy * 1000.0)
            internal_energy_kj_kg[i, j] = prop("U", pressure, "H", enthalpy * 1000.0) / 1000.0
            if hf < enthalpy < hg:
                cp_kj_kgK[i, j] = np.nan
            else:
                cp_kj_kgK[i, j] = prop("C", pressure, "H", enthalpy * 1000.0) / 1000.0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUTPUT,
        pressure_mpa=pressure_mpa,
        enthalpy_kj_kg=enthalpy_kj_kg,
        temperature_C=temperature_C,
        specific_volume_m3_kg=specific_volume,
        internal_energy_kj_kg=internal_energy_kj_kg,
        cp_kj_kgK=cp_kj_kgK,
        source=np.array("IAPWS-IF97 via CoolProp IF97::Water"),
        generator_version=np.array(f"CoolProp {CoolProp.__version__}"),
        formulation=np.array("IAPWS R7-97(2012)"),
        lookup_guideline=np.array("IAPWS G13-15 table lookup; bilinear educational subset"),
        **{f"sat_{key}": value for key, value in saturation.items()},
    )
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024.0:.1f} KiB)")


if __name__ == "__main__":
    generate()
