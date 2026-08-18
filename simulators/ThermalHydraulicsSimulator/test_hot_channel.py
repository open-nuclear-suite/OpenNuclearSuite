"""Verification checks for the representative axial hot-channel model."""

from __future__ import annotations

import unittest

import numpy as np

from hot_channel import (
    HotChannelGeometry,
    HotChannelModel,
    w3_critical_heat_flux_W_m2,
)
from steam_properties import SteamTables


class HotChannelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tables = SteamTables()

    def solve(self, nodes: int = 20, power: float = 1.0, flow: float = 1.0):
        model = HotChannelModel(self.tables, HotChannelGeometry(node_count=nodes))
        return model.solve(power, 15.5, 290.0, flow)

    def test_nominal_channel_conserves_deposited_energy(self) -> None:
        result = self.solve()
        mass_flow = HotChannelGeometry().nominal_mass_flow_kg_s
        coolant_gain_W = mass_flow * (
            result.outlet_enthalpy_kj_kg - result.inlet_enthalpy_kj_kg
        ) * 1000.0
        self.assertAlmostEqual(coolant_gain_W, result.deposited_power_W, places=8)

    def test_bulk_temperature_and_enthalpy_rise_axially(self) -> None:
        result = self.solve()
        self.assertTrue(np.all(np.diff(result.enthalpy_kj_kg) > 0.0))
        self.assertTrue(np.all(np.diff(result.bulk_temperature_C) > 0.0))
        self.assertGreater(result.outlet_temperature_C, result.bulk_temperature_C[0])

    def test_fuel_and_clad_are_hotter_than_coolant(self) -> None:
        result = self.solve()
        self.assertTrue(np.all(result.clad_surface_temperature_C > result.bulk_temperature_C))
        self.assertTrue(
            np.all(result.fuel_centerline_temperature_C > result.clad_surface_temperature_C)
        )

    def test_power_and_flow_sensitivities_have_expected_direction(self) -> None:
        nominal = self.solve()
        high_power = self.solve(power=1.10)
        low_flow = self.solve(flow=0.80)
        self.assertGreater(
            np.max(high_power.fuel_centerline_temperature_C),
            np.max(nominal.fuel_centerline_temperature_C),
        )
        self.assertGreater(low_flow.outlet_temperature_C, nominal.outlet_temperature_C)

    def test_axial_grid_refinement_converges(self) -> None:
        coarse = self.solve(nodes=10)
        medium = self.solve(nodes=20)
        fine = self.solve(nodes=80)
        coarse_error = abs(
            np.max(coarse.fuel_centerline_temperature_C)
            - np.max(fine.fuel_centerline_temperature_C)
        )
        medium_error = abs(
            np.max(medium.fuel_centerline_temperature_C)
            - np.max(fine.fuel_centerline_temperature_C)
        )
        self.assertLess(medium_error, coarse_error)
        self.assertLess(abs(medium.outlet_temperature_C - fine.outlet_temperature_C), 0.2)

    def test_w3_correlation_reference_and_domain_guard(self) -> None:
        chf = w3_critical_heat_flux_W_m2(15.0, 4000.0, -0.10, 0.012, 100.0)
        self.assertAlmostEqual(chf / 1.0e6, 3.1856702574, places=8)
        self.assertTrue(
            np.isnan(w3_critical_heat_flux_W_m2(5.0, 4000.0, -0.10, 0.012, 100.0))
        )

    def test_nominal_dnbr_is_axially_resolved(self) -> None:
        result = self.solve()
        self.assertGreater(np.count_nonzero(result.chf_correlation_valid), 0)
        self.assertIsNotNone(result.minimum_dnbr_index)
        self.assertGreater(result.minimum_dnbr, 1.0)
        self.assertTrue(np.all(result.dnbr[result.chf_correlation_valid] > 0.0))

    def test_higher_power_reduces_minimum_dnbr(self) -> None:
        nominal = self.solve(power=1.0)
        high_power = self.solve(power=1.10)
        self.assertLess(high_power.minimum_dnbr, nominal.minimum_dnbr)

    def test_out_of_range_flow_is_reported_not_extrapolated(self) -> None:
        result = self.solve(flow=0.20)
        self.assertTrue(np.all(np.isnan(result.dnbr)))
        self.assertIn("outside its published range", result.phase_warning)


if __name__ == "__main__":
    unittest.main()
