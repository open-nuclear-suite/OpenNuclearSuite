"""Verification and interpolation checks for the bundled IF97 property table."""

from __future__ import annotations

import math
import unittest

from steam_properties import PropertyRangeError, SteamTables


class SteamPropertyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tables = SteamTables()

    def test_table_provenance_and_declared_domain(self) -> None:
        self.assertIn("IAPWS-IF97", self.tables.source)
        self.assertEqual(self.tables.generator_version, "CoolProp 8.0.0")
        self.assertEqual(self.tables.pressure_range_mpa, (0.1, 20.0))
        self.assertEqual(self.tables.enthalpy_range_kj_kg, (100.0, 3600.0))

    def test_if97_nominal_pwr_saturation_reference(self) -> None:
        # IF97::Water reference values used during generation at 15.5 MPa.
        sat = self.tables.saturation_at_pressure(15.5)
        self.assertAlmostEqual(sat.temperature_C, 344.7915516, places=5)
        self.assertAlmostEqual(sat.hf_kj_kg, 1629.8502994, places=4)
        self.assertAlmostEqual(sat.hg_kj_kg, 2596.2167214, places=4)
        self.assertAlmostEqual(sat.latent_heat_kj_kg, 966.3664220, places=4)

    def test_pressure_enthalpy_reference_in_compressed_liquid(self) -> None:
        state = self.tables.state_ph(15.5, 1300.0)
        self.assertEqual(state.phase, "compressed liquid")
        self.assertIsNone(state.quality)
        self.assertAlmostEqual(state.temperature_C, 293.0056102, places=4)
        self.assertAlmostEqual(state.density_kg_m3, 740.4695404, places=3)
        self.assertAlmostEqual(state.internal_energy_kj_kg, 1279.0794910, places=4)

    def test_transport_properties_match_if97_generation_reference(self) -> None:
        enthalpy = self.tables.enthalpy_pt(15.5, 290.0)
        transport = self.tables.transport_ph(15.5, enthalpy)
        self.assertAlmostEqual(transport.viscosity_Pa_s, 9.24874e-5, delta=2.0e-8)
        self.assertAlmostEqual(transport.conductivity_W_mK, 0.579207, delta=2.0e-4)
        self.assertAlmostEqual(transport.surface_tension_N_m, 0.00466908, delta=2.0e-6)
        self.assertEqual(transport.basis, "compressed-liquid")

    def test_two_phase_transport_requires_phase_basis(self) -> None:
        saturation = self.tables.saturation_at_pressure(7.0)
        enthalpy = 0.5 * (saturation.hf_kj_kg + saturation.hg_kj_kg)
        liquid = self.tables.transport_ph(7.0, enthalpy, "saturated-liquid")
        vapor = self.tables.transport_ph(7.0, enthalpy, "saturated-vapor")
        self.assertGreater(liquid.viscosity_Pa_s, vapor.viscosity_Pa_s)
        self.assertGreater(liquid.conductivity_W_mK, vapor.conductivity_W_mK)
        with self.assertRaises(ValueError):
            self.tables.transport_ph(7.0, enthalpy, "mixture")

    def test_off_grid_interpolation_against_if97_generation_references(self) -> None:
        references = (
            # pressure, enthalpy, temperature, density, internal energy
            (13.7, 1375.0, 306.3810735, 708.9715385, 1355.7604158),
            (5.3, 2800.0, 269.4817987, 26.7196101, 2601.6556032),
            (0.73, 500.0, 119.0294150, 944.1536754, 499.2654900),
        )
        for pressure, enthalpy, temperature, density, energy in references:
            with self.subTest(pressure=pressure, enthalpy=enthalpy):
                state = self.tables.state_ph(pressure, enthalpy)
                self.assertLess(abs(state.temperature_C - temperature), 0.02)
                self.assertLess(abs(state.density_kg_m3 - density) / density, 5.0e-4)
                self.assertLess(abs(state.internal_energy_kj_kg - energy), 0.01)

    def test_two_phase_interpolation_obeys_mixture_relations(self) -> None:
        sat = self.tables.saturation_at_pressure(8.0)
        enthalpy = sat.hf_kj_kg + 0.25 * sat.latent_heat_kj_kg
        state = self.tables.state_ph(8.0, enthalpy)
        self.assertEqual(state.phase, "two-phase")
        self.assertAlmostEqual(state.quality, 0.25, places=12)
        self.assertAlmostEqual(state.temperature_C, sat.temperature_C, places=12)
        expected_volume = sat.vf_m3_kg + 0.25 * (sat.vg_m3_kg - sat.vf_m3_kg)
        self.assertAlmostEqual(1.0 / state.density_kg_m3, expected_volume, places=12)
        self.assertTrue(math.isnan(state.cp_kj_kgK))

    def test_pressure_temperature_inverse_recovers_compressed_liquid_state(self) -> None:
        state = self.tables.state_pt(15.5, 290.0)
        self.assertEqual(state.phase, "compressed liquid")
        self.assertAlmostEqual(state.temperature_C, 290.0, places=3)
        self.assertAlmostEqual(
            self.tables.enthalpy_pt(15.5, state.temperature_C),
            state.enthalpy_kj_kg,
            places=6,
        )

    def test_saturation_inverse_and_monotonicity(self) -> None:
        temperatures = []
        for pressure in (0.1, 0.5, 2.0, 8.0, 15.5, 20.0):
            temperature = self.tables.saturation_temperature(pressure)
            temperatures.append(temperature)
            self.assertAlmostEqual(
                self.tables.saturation_pressure(temperature), pressure, places=10
            )
        self.assertEqual(temperatures, sorted(temperatures))

    def test_out_of_range_requests_fail_loudly(self) -> None:
        with self.assertRaises(PropertyRangeError):
            self.tables.state_ph(25.0, 1300.0)
        with self.assertRaises(PropertyRangeError):
            self.tables.state_ph(15.5, 50.0)


if __name__ == "__main__":
    unittest.main()
