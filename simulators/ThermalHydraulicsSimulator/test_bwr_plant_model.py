"""Regression tests for the consolidated independent BWR vessel model."""

from __future__ import annotations

import unittest

from bwr_plant_model import BWRControlInputs
from plant_models import CapabilityStatus
from thermal_hydraulics_engine import ControlInputs, ThermalHydraulicsEngine
from thermal_hydraulics_gui_backend import ThermalHydraulicsGUIBackend
from thermal_hydraulics_simulator import BWRState, State


class BWRPlantModelTests(unittest.TestCase):
    def make_backend(self):
        backend = ThermalHydraulicsGUIBackend()
        backend.select_plant("BWR")
        return backend

    def test_bwr_engine_is_not_a_pwr_engine(self):
        backend = self.make_backend()
        self.assertNotIsInstance(backend.sim.physics, ThermalHydraulicsEngine)
        self.assertEqual(backend.sim.physics.pack(backend.state).size, 37)

    def test_bwr_has_distinct_state_and_control_contracts(self):
        bwr = self.make_backend()
        pwr = ThermalHydraulicsGUIBackend()
        self.assertIsInstance(bwr.state, BWRState)
        self.assertIsInstance(pwr.state, State)
        self.assertNotIsInstance(pwr.state, BWRState)
        self.assertNotIn("recirc_pct", ControlInputs.__dataclass_fields__)
        self.assertIn("recirc_pct", BWRControlInputs.__dataclass_fields__)

    def test_capability_maturity_is_explicit(self):
        metadata = self.make_backend().sim.physics.metadata
        self.assertEqual(metadata.capabilities["vessel_balances"], CapabilityStatus.IMPLEMENTED)
        self.assertEqual(metadata.capabilities["void_feedback"], CapabilityStatus.TEACHING_SURROGATE)
        self.assertEqual(metadata.capabilities["axial_channel"], CapabilityStatus.DIAGNOSTIC_ONLY)
        self.assertEqual(metadata.capabilities["validated_mcpr"], CapabilityStatus.NOT_IMPLEMENTED)

    def test_nominal_mass_and_energy_derivatives_close(self):
        backend = self.make_backend()
        model, state = backend.sim.physics, backend.state
        vector = model.pack(state)
        derivative, diagnostics = model.rhs(0.0, vector, BWRControlInputs())
        mass_rate = sum(derivative[index] for index in (
            model.I_MCORE, model.I_MDC, model.I_MUPPER,
            model.I_MSEPARATOR, model.I_MCORE_VAPOR, model.I_MSTEAM
        ))
        self.assertAlmostEqual(mass_rate, 0.0, places=8)
        stored_energy_rate = (
            backend.sim.c.Cfuel * derivative[model.I_TF]
            + backend.sim.c.Cclad * derivative[model.I_TCL]
            + derivative[model.I_UCORE] + derivative[model.I_UDC]
            + derivative[model.I_UUPPER] + derivative[model.I_USEPARATOR]
            + derivative[model.I_UCORE_VAPOR] + derivative[model.I_USTEAM]
        )
        self.assertAlmostEqual(stored_energy_rate, 0.0, places=7)
        self.assertAlmostEqual(diagnostics.flow_effective, 1.0, places=8)
        self.assertAlmostEqual(diagnostics.mass_balance_residual_kg_s, 0.0, places=8)
        self.assertAlmostEqual(diagnostics.energy_balance_residual_MW, 0.0, places=7)

    def test_equilibrium_flash_closes_mass_energy_and_volume(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        vector = model.pack(state)
        total_mass = sum(vector[index] for index in (
            model.I_MCORE, model.I_MDC, model.I_MUPPER, model.I_MSEPARATOR, model.I_MCORE_VAPOR, model.I_MSTEAM
        ))
        total_energy = sum(vector[index] for index in (
            model.I_UCORE, model.I_UDC, model.I_UUPPER, model.I_USEPARATOR, model.I_UCORE_VAPOR, model.I_USTEAM
        ))
        pressure, sat, liquid, vapor, energy_residual = model.equilibrium_from_totals(
            total_mass, total_energy
        )
        vessel_volume = (backend.sim.c.bwr_steam_dome_volume_m3
                         +backend.sim.c.bwr_liquid_inventory_kg*model.reference_saturation.vf_m3_kg)
        self.assertAlmostEqual(liquid+vapor, total_mass, places=8)
        self.assertAlmostEqual(liquid*sat.vf_m3_kg+vapor*sat.vg_m3_kg, vessel_volume, places=7)
        self.assertAlmostEqual(energy_residual, 0.0, places=7)
        self.assertAlmostEqual(pressure, backend.sim.c.Pref, places=7)

    def test_equilibrium_pressure_and_vapor_respond_monotonically_to_energy(self):
        backend = self.make_backend(); model = backend.sim.physics
        vector = model.pack(backend.state)
        mass = sum(vector[index] for index in (
            model.I_MCORE, model.I_MDC, model.I_MUPPER, model.I_MSEPARATOR, model.I_MCORE_VAPOR, model.I_MSTEAM
        ))
        energy = sum(vector[index] for index in (
            model.I_UCORE, model.I_UDC, model.I_UUPPER, model.I_USEPARATOR, model.I_UCORE_VAPOR, model.I_USTEAM
        ))
        low = model.equilibrium_from_totals(mass, energy-5000)
        high = model.equilibrium_from_totals(mass, energy+5000)
        self.assertLess(low[0], high[0])
        self.assertLess(low[3], high[3])

    def test_equilibrium_projection_preserves_total_mass_and_energy(self):
        backend = self.make_backend(); model = backend.sim.physics
        vector = model.pack(backend.state)
        vector[model.I_MSTEAM] *= 1.05
        vector[model.I_USTEAM] *= 0.97
        before_mass = sum(vector[index] for index in (
            model.I_MCORE, model.I_MDC, model.I_MUPPER, model.I_MSEPARATOR, model.I_MCORE_VAPOR, model.I_MSTEAM
        ))
        before_energy = sum(vector[index] for index in (
            model.I_UCORE, model.I_UDC, model.I_UUPPER, model.I_USEPARATOR, model.I_UCORE_VAPOR, model.I_USTEAM
        ))
        projected = model.project(vector)
        self.assertAlmostEqual(before_mass, sum(projected[index] for index in (
            model.I_MCORE, model.I_MDC, model.I_MUPPER, model.I_MSEPARATOR, model.I_MCORE_VAPOR, model.I_MSTEAM
        )), places=7)
        self.assertAlmostEqual(before_energy, sum(projected[index] for index in (
            model.I_UCORE, model.I_UDC, model.I_UUPPER, model.I_USEPARATOR, model.I_UCORE_VAPOR, model.I_USTEAM
        )), places=6)

    def test_external_mass_balance_matches_boundary_flows(self):
        backend = self.make_backend()
        model, state = backend.sim.physics, backend.state
        controls = BWRControlInputs(feedwater_pct=70.0, main_steam_pct=85.0, srv_pct=20.0)
        derivative, diagnostics = model.rhs(0.0, model.pack(state), controls)
        actual = sum(derivative[index] for index in (
            model.I_MCORE, model.I_MDC, model.I_MUPPER,
            model.I_MSEPARATOR, model.I_MCORE_VAPOR, model.I_MSTEAM
        ))
        feed = diagnostics.feedwater_flow_kg_s
        steam = diagnostics.main_steam_flow_kg_s
        srv = diagnostics.porv_out * backend.sim.c.bwr_liquid_inventory_kg
        self.assertAlmostEqual(actual, feed - steam - srv, places=7)
        self.assertAlmostEqual(diagnostics.mass_balance_residual_kg_s, 0.0, places=8)

    def test_phase_b_storage_and_geometry_are_initialized(self):
        backend = self.make_backend(); state = backend.state
        self.assertGreater(state.bwr_upper_plenum_mass_kg, 0.0)
        self.assertGreater(state.bwr_separator_mass_kg, 0.0)
        self.assertAlmostEqual(state.bwr_collapsed_level_m, backend.sim.c.bwr_level_span_m)
        self.assertAlmostEqual(state.bwr_steam_volume_residual_m3, 0.0, places=7)
        self.assertAlmostEqual(state.bwr_steam_energy_residual_MJ, 0.0, places=7)
        self.assertGreater(state.bwr_core_vapor_mass_kg, 0.0)

    def test_core_void_is_derived_from_phase_volumes(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        sat = model.properties.saturation_at_pressure(state.P)
        expected = (state.bwr_core_vapor_mass_kg*sat.vg_m3_kg)/(
            state.bwr_core_vapor_mass_kg*sat.vg_m3_kg
            +state.bwr_core_mass_kg*sat.vf_m3_kg
        )
        self.assertAlmostEqual(state.void_fraction, expected, places=10)

    def test_axial_state_is_normalized_and_void_rises_upward(self):
        backend = self.make_backend(); state = backend.state
        self.assertAlmostEqual(float(state.bwr_axial_power_fraction.sum()), 1.0)
        self.assertAlmostEqual(float(state.bwr_axial_vapor_fraction.sum()), 1.0)
        self.assertTrue(all(
            state.bwr_axial_void_fraction[i] < state.bwr_axial_void_fraction[i+1]
            for i in range(3)
        ))

    def test_bottom_entry_rods_shift_axial_power_upward(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        derivative, _ = model.rhs(
            0.0,model.pack(state),BWRControlInputs(rod_pct=70.0)
        )
        self.assertLess(derivative[model.I_AXIAL_POWER][0], 0.0)
        self.assertGreater(derivative[model.I_AXIAL_POWER][-1], 0.0)

    def test_axial_void_distribution_changes_void_reactivity_at_fixed_inventory(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        bottom=model.pack(state); middle=bottom.copy()
        bottom[model.I_AXIAL_VAPOR]=[0.70,0.10,0.10,0.10]
        middle[model.I_AXIAL_VAPOR]=[0.10,0.45,0.35,0.10]
        _,bottom_diagnostics=model.rhs(0.0,bottom,BWRControlInputs())
        _,middle_diagnostics=model.rhs(0.0,middle,BWRControlInputs())
        self.assertNotAlmostEqual(
            bottom_diagnostics.rho_total,middle_diagnostics.rho_total,places=8
        )

    def test_axial_projection_preserves_normalized_shape_contract(self):
        backend = self.make_backend(); model = backend.sim.physics
        vector=model.pack(backend.state)
        vector[model.I_AXIAL_POWER]=[-1.0,2.0,3.0,4.0]
        vector[model.I_AXIAL_VAPOR]=[4.0,3.0,2.0,-1.0]
        projected=model.project(vector)
        self.assertAlmostEqual(float(projected[model.I_AXIAL_POWER].sum()),1.0)
        self.assertAlmostEqual(float(projected[model.I_AXIAL_VAPOR].sum()),1.0)
        self.assertTrue((projected[model.I_AXIAL_POWER] > 0.0).all())

    def test_valid_dryout_margin_reduces_cooling_and_heats_cladding(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        vector = model.pack(state)
        wet, wet_diagnostics = model.rhs(
            0.0, vector,
            BWRControlInputs(critical_power_ratio=1.20, critical_power_valid_nodes=8),
        )
        dry, dry_diagnostics = model.rhs(
            0.0, vector,
            BWRControlInputs(critical_power_ratio=0.70, critical_power_valid_nodes=8),
        )
        self.assertTrue(dry_diagnostics.critical_power_coupled)
        self.assertEqual(dry_diagnostics.heat_transfer_regime, "film boiling / dryout")
        self.assertLess(dry_diagnostics.coolant_heat_transfer_factor,
                        wet_diagnostics.coolant_heat_transfer_factor)
        self.assertGreater(dry[model.I_TCL], wet[model.I_TCL])

    def test_invalid_critical_power_result_cannot_trigger_dryout(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        _, diagnostics = model.rhs(
            0.0, model.pack(state),
            BWRControlInputs(critical_power_ratio=0.20, critical_power_valid_nodes=0),
        )
        self.assertFalse(diagnostics.critical_power_coupled)
        self.assertEqual(diagnostics.heat_transfer_regime, "unassessed two-phase")

    def test_geometry_level_tracks_liquid_specific_volume(self):
        backend = self.make_backend(); initial = backend.state.bwr_collapsed_level_m
        backend.state.bwr_downcomer_mass_kg -= 0.10*backend.sim.c.bwr_liquid_inventory_kg
        backend.sim.physics.step(backend.state, BWRControlInputs(auto_bwr_safety=False), 0.01)
        self.assertLess(backend.state.bwr_collapsed_level_m, initial)

    def test_timestep_refinement_acceptance(self):
        def run(dt):
            backend = self.make_backend()
            controls = BWRControlInputs(recirc_pct=0, feedwater_pct=80, main_steam_pct=90)
            for _ in range(round(2.0/dt)):
                backend.sim.physics.step(backend.state, controls, dt)
            return backend.state
        coarse, fine = run(0.04), run(0.02)
        self.assertLess(abs(coarse.P-fine.P), 0.01)
        self.assertLess(abs(coarse.M-fine.M), 2.0e-4)
        self.assertLess(abs(coarse.n-fine.n), 2.0e-3)
        self.assertLess(
            float(abs(coarse.bwr_axial_power_fraction-fine.bwr_axial_power_fraction).max()),
            2.0e-3,
        )
        self.assertLess(
            float(abs(coarse.bwr_axial_vapor_fraction-fine.bwr_axial_vapor_fraction).max()),
            2.0e-3,
        )
        self.assertLess(abs(fine.bwr_steam_volume_residual_m3), 1.0e-6)
        self.assertLess(
            abs(fine.bwr_steam_energy_residual_MJ)/fine.bwr_steam_energy_MJ,
            5.0e-3,
        )

    def test_displayed_flows_are_the_integrated_rhs_flows(self):
        backend = self.make_backend()
        model, state = backend.sim.physics, backend.state
        state.bwr_downcomer_mass_kg -= 0.20*backend.sim.c.bwr_liquid_inventory_kg
        sat = model.properties.saturation_at_pressure(1.5)
        state.bwr_steam_mass_kg = backend.sim.c.bwr_steam_dome_volume_m3/sat.vg_m3_kg
        controls = BWRControlInputs(
            feedwater_pct=65, main_steam_pct=50, bypass_pct=20,
            srv_pct=10, bwr_break_pct=8, auto_bwr_safety=True,
        )
        diagnostics = model.step(state, controls, 0.02)
        self.assertEqual(state.bwr_feedwater_flow_kg_s, diagnostics.feedwater_flow_kg_s)
        self.assertEqual(state.bwr_steam_flow_kg_s, diagnostics.main_steam_flow_kg_s)
        self.assertEqual(state.bwr_lpci_flow_kg_s, diagnostics.lpci_flow_kg_s)
        self.assertEqual(state.bwr_core_spray_flow_kg_s, diagnostics.core_spray_flow_kg_s)
        self.assertAlmostEqual(diagnostics.mass_balance_residual_kg_s, 0.0, places=8)
        self.assertAlmostEqual(diagnostics.energy_balance_residual_MW, 0.0, places=7)

    def test_recirculation_trip_increases_void_and_reduces_power(self):
        backend = self.make_backend()
        initial_void = backend.state.void_fraction
        backend.select_scenario("RECIRC_TRIP")
        backend.start(); backend.advance_elapsed(2.0, max_steps=100)
        self.assertGreater(backend.state.void_fraction, initial_void)
        backend.advance_elapsed(18.0, max_steps=500)
        self.assertLess(backend.state.bwr_core_flow_fraction, 0.45)
        self.assertLess(backend.state.n, 0.80)

    def test_recirculation_uses_a_closed_head_balance(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        derivative, diagnostics = model.rhs(
            0.0, model.pack(state), BWRControlInputs(recirc_pct=100)
        )
        self.assertAlmostEqual(
            diagnostics.pump_head_m+diagnostics.buoyancy_head_m,
            diagnostics.friction_head_m,
            places=8,
        )
        self.assertAlmostEqual(derivative[model.I_FLOW], 0.0, places=8)
        trip_derivative, trip_diagnostics = model.rhs(
            0.0, model.pack(state), BWRControlInputs(recirc_pct=0)
        )
        self.assertEqual(trip_diagnostics.pump_head_m, 0.0)
        self.assertLess(trip_derivative[model.I_FLOW], 0.0)

    def test_recirculation_losses_are_componentized(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        _, diagnostics = model.rhs(0.0, model.pack(state), BWRControlInputs())
        self.assertAlmostEqual(
            diagnostics.friction_head_m,
            diagnostics.core_friction_head_m
            +diagnostics.single_phase_loss_head_m
            +diagnostics.acceleration_head_m,
            places=10,
        )
        self.assertGreater(diagnostics.core_friction_head_m, 0.0)
        self.assertGreater(diagnostics.two_phase_friction_multiplier, 1.0)

    def test_void_increases_driving_head_and_two_phase_loss(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        sat = model.properties.saturation_at_pressure(state.P)
        rho_l = 1.0/sat.vf_m3_kg
        low = model._recirculation_heads(0.7, 0.0, 0.10, sat, rho_l)
        high = model._recirculation_heads(0.7, 0.0, 0.60, sat, rho_l)
        self.assertGreater(high[1], low[1])
        self.assertGreater(high[2], low[2])
        self.assertGreater(high[5], low[5])

    def test_recirc_pump_head_declines_with_flow_at_fixed_speed(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        sat = model.properties.saturation_at_pressure(state.P)
        rho_l = 1.0/sat.vf_m3_kg
        low_flow = model._recirculation_heads(0.4, 1.0, state.void_fraction, sat, rho_l)
        high_flow = model._recirculation_heads(1.0, 1.0, state.void_fraction, sat, rho_l)
        self.assertGreater(low_flow[0], high_flow[0])

    def test_reference_leg_temperature_has_instrument_lag(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        initial_reference = state.bwr_reference_leg_temperature_C
        state.bwr_downcomer_energy_MJ *= 0.97
        model.step(state, BWRControlInputs(auto_bwr_safety=False), 0.1)
        self.assertLess(state.bwr_downcomer_temperature_C, initial_reference)
        self.assertLess(state.bwr_reference_leg_temperature_C, initial_reference)
        self.assertGreater(state.bwr_reference_leg_temperature_C, state.bwr_downcomer_temperature_C)
        self.assertAlmostEqual(
            state.bwr_indicated_level_percent,
            100.0*state.bwr_indicated_level_m/backend.sim.c.bwr_level_span_m,
        )

    def test_turbine_trip_pressurizes_and_opens_srv(self):
        backend = self.make_backend()
        backend.select_scenario("TURBINE_TRIP")
        backend.start(); backend.advance_elapsed(20.0, max_steps=500)
        self.assertGreater(backend.state.P, 7.4)
        self.assertGreater(backend.state.bwr_srv_flow_kg_s, 0.0)
        self.assertTrue(backend.state.trip)

    def test_loss_of_feedwater_reduces_liquid_inventory(self):
        backend = self.make_backend()
        backend.select_scenario("LOFW")
        backend.start(); backend.advance_elapsed(15.0, max_steps=400)
        self.assertLess(backend.state.M, 0.95)

    def test_low_level_automatically_actuates_high_pressure_injection(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        state.bwr_downcomer_mass_kg -= 0.15*backend.sim.c.bwr_liquid_inventory_kg
        state.bwr_indicated_level_percent = 85.0
        controls = BWRControlInputs(auto_bwr_safety=True)
        model.step(state, controls, 0.5)
        self.assertFalse(state.bwr_hpci_latched)
        state.bwr_indicated_level_percent = 85.0
        model.step(state, controls, 0.6)
        self.assertTrue(state.bwr_hpci_latched)
        # Removing liquid without a compensating equilibrium state produces an
        # artificial high-specific-energy state here. The latch remains set,
        # but the pump correctly cannot inject above its shutoff head.
        self.assertGreaterEqual(
            state.P-backend.sim.c.bwr_suppression_pool_pressure_mpa,
            backend.sim.c.bwr_hpci_shutoff_head_mpa,
        )
        self.assertEqual(state.bwr_hpci_flow_kg_s, 0.0)

    def test_rps_channels_have_independent_declared_delays_and_causes(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        state.n = backend.sim.c.bwr_rps_high_flux_fraction+0.01
        demand, cause = model.evaluate_protection(state, 0.05)
        self.assertFalse(demand)
        self.assertEqual(cause, "None")
        demand, cause = model.evaluate_protection(state, 0.06)
        self.assertTrue(demand)
        self.assertIn("High neutron flux", cause)
        self.assertEqual(state.bwr_trip_cause, "High neutron flux")

    def test_rps_timer_resets_when_signal_clears_before_delay(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        state.P = backend.sim.c.bwr_rps_high_pressure_mpa+0.1
        model.evaluate_protection(state, 0.3)
        self.assertGreater(state.bwr_rps_high_pressure_timer_s, 0.0)
        state.P = backend.sim.c.Pref
        demand, _ = model.evaluate_protection(state, 0.1)
        self.assertFalse(demand)
        self.assertEqual(state.bwr_rps_high_pressure_timer_s, 0.0)

    def test_low_level_protection_uses_indicated_level_channel(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        state.bwr_indicated_level_percent = backend.sim.c.bwr_rps_low_level_percent-1.0
        demand, cause = model.evaluate_protection(
            state, backend.sim.c.bwr_rps_low_level_delay_s
        )
        self.assertTrue(demand)
        self.assertIn("Low reactor water level", cause)

    def test_ads_requires_a_low_pressure_injection_path(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        state.bwr_indicated_level_percent = backend.sim.c.bwr_ads_start_level_percent-1.0
        unavailable = BWRControlInputs(
            auto_bwr_safety=True, lpci_available=False, core_spray_available=False
        )
        model._effective_safety_controls(
            state, unavailable, backend.sim.c.bwr_ads_start_delay_s+0.1
        )
        self.assertFalse(state.bwr_ads_latched)
        available = BWRControlInputs(auto_bwr_safety=True, lpci_available=True)
        model._effective_safety_controls(
            state, available, backend.sim.c.bwr_ads_start_delay_s+0.1
        )
        self.assertTrue(state.bwr_ads_latched)

    def test_high_pressure_injection_curve_has_positive_nominal_flow(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        _, diagnostics = model.rhs(
            0.0, model.pack(state),
            BWRControlInputs(hpci_pct=100, rcic_pct=100, auto_bwr_safety=False),
        )
        self.assertGreater(diagnostics.hpci_flow_kg_s, 0.0)
        self.assertGreater(diagnostics.rcic_flow_kg_s, 0.0)
        self.assertGreater(diagnostics.hpci_head_margin_mpa, 0.0)

    def test_generic_pump_curve_enforces_shutoff_head(self):
        backend = self.make_backend(); model = backend.sim.physics
        flow, margin = model._injection_curve(1.0, 4200.0, 2.0, 2.2)
        self.assertEqual(flow, 0.0)
        self.assertLess(margin, 0.0)
        lower_flow, lower_margin = model._injection_curve(1.0, 4200.0, 2.0, 1.0)
        self.assertGreater(lower_flow, 0.0)
        self.assertGreater(lower_margin, 0.0)

    def test_break_model_is_backpressure_aware_and_chokes(self):
        backend = self.make_backend(); model = backend.sim.physics
        choked_flux, critical_pressure, choked = model._hem_break_flux(7.0, 0.1)
        restricted_flux, _, restricted = model._hem_break_flux(7.0, 6.5)
        self.assertGreater(choked_flux, 0.0)
        self.assertTrue(choked)
        self.assertGreater(critical_pressure, 0.1)
        self.assertGreater(choked_flux, restricted_flux)
        self.assertFalse(restricted)

    def test_failed_safety_system_cannot_inject(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        diagnostics = model.step(
            state, BWRControlInputs(hpci_pct=100, hpci_available=False), 0.05
        )
        self.assertEqual(diagnostics.hpci_flow_kg_s, 0.0)

    def test_safety_latch_resets_only_after_level_hysteresis_delay(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        state.bwr_hpci_latched = True
        for _ in range(9): model.step(state, BWRControlInputs(), 1.0)
        self.assertTrue(state.bwr_hpci_latched)
        for _ in range(2): model.step(state, BWRControlInputs(), 1.0)
        self.assertFalse(state.bwr_hpci_latched)

    def test_pool_mass_and_energy_follow_safety_flows(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        initial_mass = state.bwr_suppression_pool_mass_kg
        initial_energy = state.bwr_suppression_pool_energy_MJ
        model.step(state, BWRControlInputs(rcic_pct=100, auto_bwr_safety=False), 0.1)
        self.assertLess(state.bwr_suppression_pool_mass_kg, initial_mass)
        self.assertNotEqual(state.bwr_suppression_pool_energy_MJ, initial_energy)
        self.assertAlmostEqual(state.bwr_vessel_pool_mass_residual_kg_s, 0.0, places=8)
        self.assertAlmostEqual(state.bwr_vessel_pool_energy_residual_MW, 0.0, places=7)

    def test_depleted_pool_blocks_suction_systems(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        state.bwr_suppression_pool_mass_kg = 0.19*backend.sim.c.bwr_pool_mass_kg
        state.bwr_suppression_pool_energy_MJ = (
            state.bwr_suppression_pool_mass_kg*backend.sim.c.bwr_pool_cp_kJ_kgK*35/1000
        )
        diagnostics = model.step(
            state, BWRControlInputs(rcic_pct=100, hpci_pct=100, auto_bwr_safety=False), 0.05
        )
        self.assertEqual(diagnostics.rcic_flow_kg_s, 0.0)
        self.assertEqual(diagnostics.hpci_flow_kg_s, 0.0)

    def test_ads_depressurizes_and_heats_suppression_pool(self):
        backend = self.make_backend()
        backend.set_controls(main_steam=0, feedwater=0, ads=100)
        initial_pressure = backend.state.P
        initial_pool = backend.state.bwr_suppression_pool_temperature_C
        backend.start(); backend.advance_elapsed(8.0, max_steps=200)
        self.assertLess(backend.state.P, initial_pressure)
        self.assertGreater(backend.state.bwr_suppression_pool_temperature_C, initial_pool)
        self.assertGreater(backend.state.bwr_srv_flow_kg_s, 0.0)

    def test_lpci_and_core_spray_are_pressure_dependent(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        sat = model.properties.saturation_at_pressure(1.5)
        total_mass = sum((state.bwr_core_mass_kg, state.bwr_downcomer_mass_kg,
                          state.bwr_upper_plenum_mass_kg, state.bwr_separator_mass_kg,
                          state.bwr_core_vapor_mass_kg, state.bwr_steam_mass_kg))
        vessel_volume = (backend.sim.c.bwr_steam_dome_volume_m3
                         +backend.sim.c.bwr_liquid_inventory_kg*model.reference_saturation.vf_m3_kg)
        vapor_mass = (vessel_volume-total_mass*sat.vf_m3_kg)/(sat.vg_m3_kg-sat.vf_m3_kg)
        liquid_mass = total_mass-vapor_mass
        scale = liquid_mass/sum((state.bwr_core_mass_kg, state.bwr_downcomer_mass_kg,
                                 state.bwr_upper_plenum_mass_kg, state.bwr_separator_mass_kg))
        for mass_name, energy_name in (
            ("bwr_core_mass_kg","bwr_core_energy_MJ"),
            ("bwr_downcomer_mass_kg","bwr_downcomer_energy_MJ"),
            ("bwr_upper_plenum_mass_kg","bwr_upper_plenum_energy_MJ"),
            ("bwr_separator_mass_kg","bwr_separator_energy_MJ"),
        ):
            setattr(state,mass_name,getattr(state,mass_name)*scale)
            setattr(state,energy_name,getattr(state,mass_name)*sat.uf_kj_kg/1000)
        state.bwr_core_vapor_mass_kg = 0.0
        state.bwr_core_vapor_energy_MJ = 0.0
        state.bwr_steam_mass_kg = vapor_mass
        state.bwr_steam_energy_MJ = vapor_mass*sat.ug_kj_kg/1000
        controls = BWRControlInputs(lpci_pct=100, core_spray_pct=100, auto_bwr_safety=False)
        derivative, _ = model.rhs(0.0, model.pack(state), controls)
        baseline, _ = model.rhs(
            0.0, model.pack(state), BWRControlInputs(auto_bwr_safety=False)
        )
        self.assertGreater(derivative[model.I_MCORE], baseline[model.I_MCORE])
        self.assertGreater(derivative[model.I_MDC], baseline[model.I_MDC])

    def test_void_swell_separates_indicated_and_collapsed_level(self):
        backend = self.make_backend(); backend.select_scenario("RECIRC_TRIP")
        backend.start(); backend.advance_elapsed(2.0, max_steps=100)
        self.assertGreater(
            backend.state.bwr_indicated_level_percent,
            backend.state.bwr_collapsed_level_percent,
        )

    def test_fifteen_percent_rod_step_reaches_damped_part_power_state(self):
        backend = self.make_backend(); model, state = backend.sim.physics, backend.state
        controls = BWRControlInputs(rod_pct=15.0, auto_bwr_safety=False)
        powers = []
        for step in range(3600):
            model.step(state, controls, 0.05)
            if step % 20 == 0:
                powers.append(state.n)
        settled = powers[-20:]
        self.assertLess(max(powers[10:]), 1.05)
        self.assertGreater(state.n, 0.75)
        self.assertLess(state.n, 0.90)
        self.assertLess(max(settled)-min(settled), 0.01)
        self.assertGreater(state.P, 6.7)
        self.assertLess(state.P, 7.1)


if __name__ == "__main__":
    unittest.main()
