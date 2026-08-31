"""Contract regression tests for the dedicated PWR model boundary."""

from __future__ import annotations

import unittest
import math

import numpy as np

from hot_channel import HotChannelModel
from plant_models import PWRPlantModel, create_plant_model
from pwr_plant_model import PWRPlantModel as IndependentPWRPlantModel
from thermal_hydraulics_engine import (
    ControlInputs,
    PWRControlInputs,
    PWRStepDiagnostics,
    StepDiagnostics,
    ThermalHydraulicsEngine,
)
from thermal_hydraulics_gui_backend import ThermalHydraulicsGUIBackend
from thermal_hydraulics_simulator import (
    Constants,
    PWRConstants,
    PWRState,
    State,
)


class PWRPlantModelContractTests(unittest.TestCase):
    def test_backend_constructs_explicit_pwr_contracts(self):
        backend = ThermalHydraulicsGUIBackend()
        self.assertIsInstance(backend.sim.c, PWRConstants)
        self.assertIsInstance(backend.state, PWRState)
        self.assertIsInstance(backend.sim.physics, PWRPlantModel)
        self.assertIsInstance(backend.sim.physics, IndependentPWRPlantModel)
        self.assertIsInstance(backend.sim.physics, ThermalHydraulicsEngine)

    def test_factory_constructs_dedicated_pwr_model(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        diagnostics = model.step(state, PWRControlInputs(), 0.05)
        self.assertIsInstance(model, PWRPlantModel)
        self.assertIsInstance(diagnostics, PWRStepDiagnostics)
        self.assertEqual(model.metadata.key, "PWR")

    def test_legacy_contract_names_remain_aliases(self):
        self.assertIs(Constants, PWRConstants)
        self.assertIs(State, PWRState)
        self.assertIs(ControlInputs, PWRControlInputs)
        self.assertIs(StepDiagnostics, PWRStepDiagnostics)

    def test_pwr_control_contract_excludes_bwr_controls(self):
        fields = PWRControlInputs.__dataclass_fields__
        self.assertIn("pump_pct", fields)
        self.assertIn("sg_pct", fields)
        self.assertNotIn("recirc_pct", fields)
        self.assertNotIn("feedwater_pct", fields)

    def test_rhs_publishes_closed_mass_and_energy_ledgers(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        vector = model.pack(state)
        cases = (
            PWRControlInputs(),
            PWRControlInputs(pump_pct=0.0, sg_pct=0.0),
            PWRControlInputs(
                break_pct=35.0, porv_pct=20.0, eccs_pct=80.0,
                afw_pct=50.0, rhr_pct=70.0, auto_eccs=False,
            ),
        )
        for controls in cases:
            with self.subTest(controls=controls):
                _, diagnostics = model.rhs(0.0, vector, controls)
                self.assertAlmostEqual(
                    diagnostics.pwr_stored_mass_rate_fraction_s,
                    diagnostics.pwr_boundary_mass_rate_fraction_s,
                    places=14,
                )
                self.assertAlmostEqual(
                    diagnostics.pwr_mass_balance_residual_fraction_s, 0.0,
                    places=14,
                )
                self.assertAlmostEqual(
                    diagnostics.pwr_stored_energy_rate_MW,
                    diagnostics.pwr_boundary_energy_rate_MW,
                    places=10,
                )
                self.assertAlmostEqual(
                    diagnostics.pwr_energy_balance_residual_MW, 0.0,
                    places=10,
                )

    def test_backend_state_publishes_finite_transient_ledgers(self):
        backend = ThermalHydraulicsGUIBackend()
        backend.select_scenario("SBLOCA")
        for _ in range(100):
            backend.sim.step_model(backend.DT)
        state = backend.state
        values = (
            state.pwr_stored_mass_rate_fraction_s,
            state.pwr_boundary_mass_rate_fraction_s,
            state.pwr_mass_balance_residual_fraction_s,
            state.pwr_stored_energy_rate_MW,
            state.pwr_boundary_energy_rate_MW,
            state.pwr_energy_balance_residual_MW,
            state.pwr_projection_mass_correction_fraction_s,
            state.pwr_projection_energy_correction_MW,
        )
        self.assertTrue(all(math.isfinite(value) for value in values))
        self.assertLess(abs(state.pwr_mass_balance_residual_fraction_s), 1.0e-12)
        self.assertLess(abs(state.pwr_energy_balance_residual_MW), 1.0e-9)
        self.assertEqual(len(state.hist.pwr_mass_residual), 100)

    def test_projection_correction_is_reported_separately(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        state.M = 1.19999
        state.Ucool = constants.Ccool * state.M * (
            state.Tc - constants.coolant_energy_reference_C
        )
        diagnostics = model.step(
            state, PWRControlInputs(eccs_pct=100.0, auto_eccs=False), 0.05,
        )
        self.assertLess(
            diagnostics.pwr_projection_mass_correction_fraction_s, 0.0
        )
        self.assertAlmostEqual(state.M, 1.20, places=12)

    def test_protection_channels_have_declared_delays_and_retain_first_cause(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        state.n = constants.pwr_rps_high_flux_fraction + 0.01
        demand, cause = model.evaluate_protection(state, 0.05, 100.0)
        self.assertFalse(demand)
        self.assertEqual(cause, "None")
        demand, cause = model.evaluate_protection(state, 0.06, 100.0)
        self.assertTrue(demand)
        self.assertEqual(cause, "High neutron flux")
        self.assertEqual(state.pwr_trip_cause, "High neutron flux")
        state.n = 1.0
        state.P = constants.pwr_rps_high_pressure_mpa + 0.1
        model.evaluate_protection(
            state, constants.pwr_rps_high_pressure_delay_s, 100.0
        )
        self.assertEqual(state.pwr_trip_cause, "High neutron flux")

    def test_protection_timer_resets_when_signal_clears(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        state.P = constants.pwr_rps_high_pressure_mpa + 0.1
        model.evaluate_protection(state, 0.30, 100.0)
        state.P = constants.Pref
        model.evaluate_protection(state, 0.05, 100.0)
        self.assertEqual(state.pwr_rps_high_pressure_timer_s, 0.0)
        state.P = constants.pwr_rps_high_pressure_mpa + 0.1
        demand, _ = model.evaluate_protection(state, 0.25, 100.0)
        self.assertFalse(demand)

    def test_low_flow_channel_uses_power_permissive(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        state.n = constants.pwr_rps_low_flow_power_permissive - 0.01
        demand, _ = model.evaluate_protection(state, 2.0, 0.0)
        self.assertFalse(demand)
        state.n = 1.0
        demand, cause = model.evaluate_protection(
            state, constants.pwr_rps_low_flow_delay_s, 0.0
        )
        self.assertTrue(demand)
        self.assertEqual(cause, "Low primary flow")

    def test_low_inventory_and_coupled_thermal_channels_are_independent(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        low_inventory = PWRState(constants)
        low_inventory.M = constants.pwr_rps_low_inventory_fraction - 0.01
        demand, cause = model.evaluate_protection(
            low_inventory, constants.pwr_rps_low_inventory_delay_s, 100.0
        )
        self.assertTrue(demand)
        self.assertEqual(cause, "Low primary inventory")

        thermal = PWRState(constants)
        thermal.hot_peak_clad_C = constants.pwr_rps_high_clad_C + 1.0
        demand, _ = model.evaluate_protection(
            thermal, constants.pwr_rps_thermal_delay_s, 100.0,
            thermal_limit_enabled=False,
        )
        self.assertFalse(demand)
        demand, cause = model.evaluate_protection(
            thermal, constants.pwr_rps_thermal_delay_s, 100.0,
            thermal_limit_enabled=True,
        )
        self.assertTrue(demand)
        self.assertEqual(cause, "Fuel thermal limit")

    def test_disabled_auto_trip_reports_demand_without_actuating(self):
        backend = ThermalHydraulicsGUIBackend()
        backend.set_automatic("trip", False)
        backend.state.n = backend.sim.c.pwr_rps_high_flux_fraction + 0.01
        for _ in range(3):
            backend.sim.step_model(backend.DT)
        self.assertTrue(backend.state.pwr_protection_demand)
        self.assertFalse(backend.state.trip)
        self.assertEqual(backend.state.pwr_trip_cause, "High neutron flux")

    def test_manual_scram_records_cause(self):
        backend = ThermalHydraulicsGUIBackend()
        backend.scram()
        self.assertTrue(backend.state.trip)
        self.assertEqual(backend.state.pwr_trip_cause, "Manual reactor trip")

    def test_component_pump_curves_and_availability(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)

        def diagnostics_at(pressure, controls):
            state.Tprz = model.properties.saturation_temperature(pressure)
            vector = model.pack(state)
            return model.rhs(0.0, vector, controls)[1]

        hpsi_high = diagnostics_at(
            15.0, PWRControlInputs(hpsi_pct=100.0, auto_eccs=False)
        )
        hpsi_low = diagnostics_at(
            8.0, PWRControlInputs(hpsi_pct=100.0, auto_eccs=False)
        )
        self.assertGreater(hpsi_high.pwr_hpsi_in_fraction_s, 0.0)
        self.assertGreater(
            hpsi_low.pwr_hpsi_in_fraction_s,
            hpsi_high.pwr_hpsi_in_fraction_s,
        )
        blocked = diagnostics_at(
            8.0, PWRControlInputs(
                hpsi_pct=100.0, hpsi_available=False, auto_eccs=False
            ),
        )
        self.assertEqual(blocked.pwr_hpsi_in_fraction_s, 0.0)

        lpsi_blocked_by_head = diagnostics_at(
            8.0, PWRControlInputs(lpsi_pct=100.0, auto_eccs=False)
        )
        lpsi_low_pressure = diagnostics_at(
            1.0, PWRControlInputs(lpsi_pct=100.0, auto_eccs=False)
        )
        self.assertEqual(lpsi_blocked_by_head.pwr_lpsi_in_fraction_s, 0.0)
        self.assertGreater(lpsi_low_pressure.pwr_lpsi_in_fraction_s, 0.0)

    def test_accumulator_is_passive_finite_inventory(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        state.Tprz = model.properties.saturation_temperature(2.0)
        state.P = 2.0
        before = state.pwr_accumulator_inventory_fraction
        diagnostics = model.step(
            state, PWRControlInputs(auto_eccs=False), 0.05
        )
        self.assertGreater(diagnostics.pwr_accumulator_in_fraction_s, 0.0)
        self.assertLess(state.pwr_accumulator_inventory_fraction, before)
        unavailable = PWRState(constants)
        unavailable.Tprz = model.properties.saturation_temperature(2.0)
        diagnostics = model.step(
            unavailable,
            PWRControlInputs(auto_eccs=False, accumulator_available=False),
            0.05,
        )
        self.assertEqual(diagnostics.pwr_accumulator_in_fraction_s, 0.0)

    def test_automatic_injection_delays_latches_and_resets(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        state.P, state.M = 10.0, 0.90
        controls = PWRControlInputs(
            auto_eccs=True, auto_eccs_demand=0.35, break_pct=10.0
        )
        model._effective_safety_controls(state, controls, 0.50)
        self.assertFalse(state.pwr_hpsi_latched)
        effective = model._effective_safety_controls(state, controls, 0.50)
        self.assertTrue(state.pwr_hpsi_latched)
        self.assertEqual(effective.hpsi_pct, 100.0)

        state.P, state.M = 1.0, 0.80
        for _ in range(8):
            effective = model._effective_safety_controls(state, controls, 1.0)
        self.assertTrue(state.pwr_lpsi_latched)
        self.assertTrue(state.pwr_recirculation_latched)
        self.assertEqual(effective.lpsi_pct, 100.0)
        self.assertEqual(effective.recirculation_pct, 100.0)

        state.P, state.M, state.Tcl = 15.5, 1.0, constants.TrefClad
        recovery = PWRControlInputs(auto_eccs=True, break_pct=0.0)
        model._effective_safety_controls(
            state, recovery, constants.pwr_safety_reset_delay_s
        )
        self.assertFalse(state.pwr_hpsi_latched)
        self.assertFalse(state.pwr_lpsi_latched)
        self.assertFalse(state.pwr_recirculation_latched)

    def test_resolved_primary_stores_close_to_aggregate_ledgers(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        for _ in range(100):
            model.step(state, PWRControlInputs(auto_eccs=False), 0.05)
        component_mass = sum((
            state.pwr_core_inventory_fraction,
            state.pwr_hot_leg_inventory_fraction,
            state.pwr_cold_leg_inventory_fraction,
            state.pwr_pressurizer_liquid_inventory_fraction,
            state.pwr_pressurizer_steam_inventory_fraction,
        ))
        component_energy = sum((
            state.pwr_core_energy_MJ, state.pwr_hot_leg_energy_MJ,
            state.pwr_cold_leg_energy_MJ,
            state.pwr_pressurizer_liquid_energy_MJ,
            state.pwr_pressurizer_steam_energy_MJ,
        ))
        self.assertAlmostEqual(component_mass, state.M, places=12)
        self.assertAlmostEqual(component_energy, state.Ucool, places=8)

    def test_primary_flow_has_pump_coastdown_and_head_balance(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        model.step(state, PWRControlInputs(auto_eccs=False), 0.05)
        nominal_flow = state.pwr_primary_flow_fraction
        for _ in range(80):
            model.step(
                state, PWRControlInputs(pump_pct=0.0, auto_eccs=False), 0.05
            )
        self.assertLess(state.pwr_primary_flow_fraction, 0.55 * nominal_flow)
        self.assertEqual(state.pwr_pump_head_m, 0.0)
        self.assertGreaterEqual(state.pwr_buoyancy_head_m, 0.0)
        self.assertGreater(state.pwr_loop_loss_head_m, 0.0)

    def test_pressurizer_surge_tracks_primary_inventory_redistribution(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        model.initialize_state(state)
        before = (state.pwr_pressurizer_liquid_inventory_fraction
                  + state.pwr_pressurizer_steam_inventory_fraction)
        state.M = 0.80
        model._advance_primary_components(state, before, 1.0)
        after = (state.pwr_pressurizer_liquid_inventory_fraction
                 + state.pwr_pressurizer_steam_inventory_fraction)
        self.assertLess(after, before)
        self.assertLess(state.pwr_surge_flow_fraction_s, 0.0)

    def test_steam_generator_secondary_has_closed_nominal_balances(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        for _ in range(200):
            model.step(state, PWRControlInputs(auto_eccs=False), 0.05)
        self.assertAlmostEqual(
            state.pwr_secondary_mass_kg, constants.pwr_secondary_inventory_kg,
            places=6,
        )
        self.assertAlmostEqual(
            state.pwr_secondary_pressure_mpa,
            constants.pwr_secondary_reference_pressure_mpa, places=6,
        )
        self.assertAlmostEqual(state.pwr_secondary_mass_residual_kg_s, 0.0, places=8)
        self.assertAlmostEqual(state.pwr_secondary_energy_residual_MW, 0.0, places=8)

    def test_axial_state_is_normalized_and_vapor_holdup_rises_upward(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        model.initialize_state(state)
        self.assertAlmostEqual(float(state.pwr_axial_power_fraction.sum()), 1.0)
        self.assertAlmostEqual(float(state.pwr_axial_vapor_fraction.sum()), 1.0)
        self.assertTrue(all(
            state.pwr_axial_vapor_fraction[i] < state.pwr_axial_vapor_fraction[i + 1]
            for i in range(3)
        ))

    def test_top_entry_rods_shift_axial_power_downward(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        state = PWRState(constants)
        model.initialize_state(state)
        before = state.pwr_axial_power_fraction.copy()
        for _ in range(40):
            model._advance_axial_state(state, 80.0, 0.05)
        self.assertGreater(state.pwr_axial_power_fraction[0], before[0])
        self.assertLess(state.pwr_axial_power_fraction[-1], before[-1])
        self.assertLessEqual(state.pwr_axial_peak_node, 2)

    def test_axial_void_signal_changes_with_holdup_at_fixed_total_void(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        bottom = model._axial_voids(0.20, [0.70, 0.10, 0.10, 0.10])
        middle = model._axial_voids(0.20, [0.10, 0.45, 0.35, 0.10])
        self.assertNotAlmostEqual(
            model._spatial_void_signal(bottom),
            model._spatial_void_signal(middle), places=8,
        )

    def test_axial_shape_changes_distribution_not_deposited_power(self):
        constants = PWRConstants()
        model = create_plant_model("PWR", constants)
        channel = HotChannelModel(model.properties)
        bottom = channel.solve(1.0, 15.5, 290.0, 1.0, np.array([0.55, 0.25, 0.15, 0.05]))
        top = channel.solve(1.0, 15.5, 290.0, 1.0, np.array([0.05, 0.15, 0.25, 0.55]))
        self.assertAlmostEqual(bottom.deposited_power_W, top.deposited_power_W, places=8)
        self.assertNotEqual(
            int(np.argmax(bottom.linear_heat_W_m)),
            int(np.argmax(top.linear_heat_W_m)),
        )

    def test_axial_state_refines_with_timestep(self):
        def run(dt):
            constants = PWRConstants()
            model = create_plant_model("PWR", constants)
            state = PWRState(constants)
            for _ in range(round(2.0 / dt)):
                model.step(
                    state, PWRControlInputs(rod_pct=65.0, pump_pct=50.0,
                                            auto_eccs=False), dt
                )
            return state
        coarse, fine = run(0.04), run(0.02)
        self.assertLess(float(np.max(np.abs(
            coarse.pwr_axial_power_fraction - fine.pwr_axial_power_fraction
        ))), 2.0e-3)
        self.assertLess(float(np.max(np.abs(
            coarse.pwr_axial_vapor_fraction - fine.pwr_axial_vapor_fraction
        ))), 2.0e-3)


if __name__ == "__main__":
    unittest.main()
