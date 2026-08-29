"""Checks for the representative BWR axial-channel inspector model."""

from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np

from bwr_hot_channel import BWRHotChannelModel
from steam_properties import SteamTables
from thermal_hydraulics_gui_backend import ThermalHydraulicsGUIBackend


class BWRHotChannelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = BWRHotChannelModel(SteamTables())

    def solve(self, power=1.0, flow=1.0):
        return self.model.solve(power, 7.0, 284.4, flow)

    def test_axial_energy_balance_and_two_phase_outputs(self):
        result = self.solve()
        mass_flow = self.model.geometry.nominal_mass_flow_kg_s
        recovered = mass_flow * (
            result.outlet_enthalpy_kj_kg-result.inlet_enthalpy_kj_kg
        ) * 1000.0
        self.assertAlmostEqual(recovered, result.deposited_power_W, places=6)
        self.assertGreater(np.max(result.void_fraction), 0.0)
        self.assertTrue(np.all((result.void_fraction >= 0) & (result.void_fraction <= 1)))
        self.assertTrue(np.isfinite(result.minimum_cpr))

    def test_power_and_flow_change_cpr_in_expected_direction(self):
        nominal = self.solve()
        high_power = self.solve(power=1.15)
        low_flow = self.solve(flow=0.75)
        self.assertLess(high_power.minimum_cpr, nominal.minimum_cpr)
        self.assertLess(low_flow.minimum_cpr, nominal.minimum_cpr)

    def test_backend_publishes_bwr_inspector_result(self):
        backend = ThermalHydraulicsGUIBackend(); backend.select_plant("BWR")
        backend.sim.step_model(0.05)
        result = backend.sim.hot_channel_result
        self.assertEqual(result.plant_type, "BWR")
        self.assertEqual(result.z_m.size, 24)
        self.assertAlmostEqual(backend.state.hot_min_dnbr, result.minimum_cpr)
        self.assertFalse(backend.sim.hot_channel_coupling_var.get())
        with self.assertRaises(ValueError):
            backend.set_automatic("hot_channel", True)

    def test_pressure_loss_is_solved_and_increases_with_flow(self):
        nominal = self.solve(flow=1.0)
        high_flow = self.solve(flow=1.15)
        self.assertTrue(np.all(np.diff(nominal.pressure_mpa) < 0.0))
        self.assertGreater(
            high_flow.pressure_mpa[0]-high_flow.pressure_mpa[-1],
            nominal.pressure_mpa[0]-nominal.pressure_mpa[-1],
        )

    def test_xl_applicability_guard_disables_out_of_range_cpr(self):
        result = self.model.solve(1.0, 2.0, 200.0, 1.0)
        self.assertFalse(np.any(result.chf_correlation_valid))
        self.assertTrue(np.isnan(result.minimum_cpr))
        self.assertIn("outside its declared range", result.phase_warning)

    def test_post_dryout_curve_degrades_heat_transfer(self):
        nucleate, _ = BWRHotChannelModel.post_dryout_multiplier(1.2, True)
        transition, transition_regime = BWRHotChannelModel.post_dryout_multiplier(0.9, True)
        film, film_regime = BWRHotChannelModel.post_dryout_multiplier(0.7, True)
        guarded, guarded_regime = BWRHotChannelModel.post_dryout_multiplier(0.2, False)
        self.assertGreater(nucleate, transition)
        self.assertGreater(transition, film)
        self.assertEqual(guarded, 1.0)
        self.assertEqual(transition_regime, "transition boiling")
        self.assertEqual(film_regime, "film boiling / dryout")
        self.assertEqual(guarded_regime, "unassessed two-phase")

    def test_dynamic_axial_shape_moves_heat_flux_peak(self):
        bottom=self.model.solve(1.0,7.0,284.4,1.0,np.array([0.55,0.25,0.15,0.05]))
        top=self.model.solve(1.0,7.0,284.4,1.0,np.array([0.05,0.15,0.25,0.55]))
        self.assertLess(int(np.argmax(bottom.surface_heat_flux_W_m2)),
                        int(np.argmax(top.surface_heat_flux_W_m2)))
        self.assertAlmostEqual(bottom.deposited_power_W,top.deposited_power_W,places=6)

    def test_bundle_and_channel_factors_reduce_margin(self):
        base = self.solve()
        hotter_geometry = replace(
            self.model.geometry,
            radial_hot_channel_factor=1.28,
            enthalpy_rise_factor=1.14,
        )
        hotter = BWRHotChannelModel(self.model.properties, hotter_geometry).solve(
            1.0, 7.0, 284.4, 1.0
        )
        self.assertLess(hotter.minimum_cpr, base.minimum_cpr)


if __name__ == "__main__":
    unittest.main()
