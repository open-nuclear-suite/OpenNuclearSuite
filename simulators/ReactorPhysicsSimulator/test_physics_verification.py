"""Independent numerical verification and educational-physics validation tests."""

import math
import unittest

import numpy as np

import reactor_teaching_simulator as sim


def isolated_kinetics_model(dt=0.02):
    """Return point kinetics isolated from feedback, poisons, trips, and source."""
    model = sim.ReactorModel()
    state = model.s
    state.dt = dt
    state.source_strength = 0.0
    state.xeWorth = 0.0
    state.smWorth = 0.0
    state.alpha_f = 0.0
    state.alpha_c = 0.0
    state.alpha_density = 0.0
    state.alpha_void = 0.0
    state.rod_pos = 50.0
    state.boron_ppm = 0.0
    state.tripHighPower = 100.0
    state.tripHighHeat = 100.0
    state.tripHighFuelTemp = 1.0e9
    state.tripHighCladTemp = 1.0e9
    state.tripHighCoolTemp = 1.0e9
    state.tripLowFlow = -1.0
    state.update_reactivity_terms()
    return model


def positive_inhour_root(state, rho):
    """Independently solve the six-group inhour equation for alpha > 0."""
    low, high = 0.0, 1.0
    for _ in range(200):
        alpha = 0.5 * (low + high)
        residual = state.Lambda * alpha + sum(
            beta * alpha / (alpha + decay)
            for beta, decay in zip(state.beta_i, state.lambda_i)
        ) - rho
        if residual < 0.0:
            low = alpha
        else:
            high = alpha
    return 0.5 * (low + high)


class PhysicsVerificationTests(unittest.TestCase):
    def test_delayed_precursor_initialization_is_exact_equilibrium(self):
        state = sim.ReactorState()
        derivatives = (state.beta_i / state.Lambda) * state.P - state.lambda_i * state.C
        np.testing.assert_allclose(derivatives, 0.0, rtol=0.0, atol=1.0e-15)

    def test_critical_source_free_kinetics_remains_steady(self):
        model = isolated_kinetics_model()
        initial_power = model.s.P
        model.advance(100.0)
        self.assertAlmostEqual(model.s.P, initial_power, delta=1.0e-10)
        np.testing.assert_allclose(
            model.s.C,
            (model.s.beta_i / (model.s.Lambda * model.s.lambda_i)) * model.s.P,
            rtol=0.0,
            atol=1.0e-9,
        )

    def test_asymptotic_period_matches_independent_inhour_solution(self):
        model = isolated_kinetics_model()
        state = model.s
        state.rho_manual = 20.0e-5
        expected_alpha = positive_inhour_root(state, state.rho_manual)
        model.advance(200.0)
        power_1 = state.P
        model.advance(200.0)
        measured_alpha = math.log(state.P / power_1) / 200.0
        self.assertAlmostEqual(measured_alpha / expected_alpha, 1.0, delta=0.002)

    def test_explicit_integration_converges_under_timestep_refinement(self):
        results = []
        for dt in (0.04, 0.02, 0.01, 0.005):
            model = isolated_kinetics_model(dt)
            model.s.rho_manual = 100.0e-5
            model.advance(20.0)
            results.append(model.s.P)
        errors = [abs(value - results[-1]) for value in results[:-1]]
        self.assertGreater(errors[0], errors[1])
        self.assertGreater(errors[1], errors[2])
        self.assertLess(errors[1] / results[-1], 1.0e-7)

    def test_advanced_rod_worth_is_monotonic_symmetric_and_differentiable(self):
        positions = np.linspace(0.0, 100.0, 101)
        worth = np.array([sim.rod_reactivity(position, True) for position in positions])
        self.assertTrue(np.all(np.diff(worth) >= 0.0))
        np.testing.assert_allclose(worth, -worth[::-1], rtol=0.0, atol=1.0e-14)
        position = 40.0
        h = 1.0e-3
        finite_difference = 1.0e5 * (
            sim.rod_reactivity(position + h, True) - sim.rod_reactivity(position - h, True)
        ) / (2.0 * h)
        self.assertAlmostEqual(
            finite_difference,
            sim.differential_rod_worth_pcm_per_pct(position, True),
            delta=1.0e-7,
        )

    def test_poison_initial_conditions_satisfy_all_equilibrium_equations(self):
        state = sim.ReactorState(sim.PedagogicalSettings(physics_profile="Advanced core physics"))
        residuals = (
            state.iodineYield * state.P - state.lambdaI * state.I,
            state.xeDirectYield * state.P + state.lambdaI * state.I
            - state.lambdaXe * state.Xe - state.xeBurn * state.P * state.Xe,
            state.pmYield * state.P - state.lambdaPm * state.Pm,
            state.lambdaPm * state.Pm - state.smBurn * state.P * state.Sm,
        )
        np.testing.assert_allclose(residuals, 0.0, rtol=0.0, atol=1.0e-15)

    def test_poison_shutdown_derivative_directions_are_physical(self):
        state = sim.ReactorState(sim.PedagogicalSettings(physics_profile="Advanced core physics"))
        shutdown_power = 0.01
        iodine_rate = state.iodineYield * shutdown_power - state.lambdaI * state.I
        xenon_rate = (
            state.xeDirectYield * shutdown_power + state.lambdaI * state.I
            - state.lambdaXe * state.Xe - state.xeBurn * shutdown_power * state.Xe
        )
        promethium_rate = state.pmYield * shutdown_power - state.lambdaPm * state.Pm
        samarium_rate = state.lambdaPm * state.Pm - state.smBurn * shutdown_power * state.Sm
        self.assertLess(iodine_rate, 0.0)
        self.assertGreater(xenon_rate, 0.0)
        self.assertLess(promethium_rate, 0.0)
        self.assertGreater(samarium_rate, 0.0)

    def test_decay_heat_and_thermal_initial_conditions_are_equilibrated(self):
        state = sim.ReactorState()
        np.testing.assert_allclose(state.Dh, state.decay_frac * state.P, rtol=0.0, atol=1.0e-15)
        self.assertAlmostEqual(state.Qheat, state.P, places=15)
        flow = state.coolantFlow / 100.0
        sink = state.heatSink / 100.0
        coolant_equilibrium = state.inletT + 60.0 * state.Qheat / (flow * sink)
        clad_equilibrium = coolant_equilibrium + 80.0 * state.Qheat / flow
        fuel_equilibrium = clad_equilibrium + 140.0 * state.Qheat / flow
        self.assertAlmostEqual(state.coolT, coolant_equilibrium)
        self.assertAlmostEqual(state.cladT, clad_equilibrium)
        self.assertAlmostEqual(state.fuelT, fuel_equilibrium)

    def test_advanced_feedback_has_expected_sign_and_component_sum(self):
        state = sim.ReactorState(sim.PedagogicalSettings(physics_profile="Advanced core physics"))
        state.fuelT += 10.0
        state.coolT += 20.0
        state.update_reactivity_terms()
        self.assertLess(state.rho_fuel, 0.0)
        self.assertLess(state.rho_moderator_temp, 0.0)
        self.assertLess(state.rho_density, 0.0)
        self.assertEqual(state.rho_void, 0.0)
        self.assertAlmostEqual(
            state.rho_temp,
            state.rho_fuel + state.rho_moderator_temp + state.rho_density + state.rho_void,
        )

    def test_external_source_strength_orders_subcritical_power(self):
        settings = sim.PedagogicalSettings(
            physics_profile="Advanced core physics",
            initial_condition="Subcritical startup",
        )
        low_source = sim.ReactorModel()
        high_source = sim.ReactorModel()
        low_source.reset(settings)
        high_source.reset(settings)
        low_source.s.source_strength = 1.0e-6
        high_source.s.source_strength = 1.0e-4
        low_source.advance(30.0)
        high_source.advance(30.0)
        self.assertGreater(high_source.s.P, low_source.s.P)
        self.assertLess(low_source.s.reactivity_pcm, 0.0)
        self.assertLess(high_source.s.reactivity_pcm, 0.0)

    def test_cycle_exposure_and_excess_reactivity_follow_declared_law(self):
        settings = sim.PedagogicalSettings(
            physics_profile="Advanced core physics",
            cycle_preset="Beginning of cycle",
        )
        model = sim.ReactorModel()
        model.reset(settings)
        model.advance(10.0)
        state = model.s
        expected_rho = 0.0030 * (1.0 - state.exposure_efpd / state.cycle_length_efpd)
        self.assertAlmostEqual(state.rho_depletion, expected_rho, places=14)
        self.assertGreater(state.exposure_efpd, 0.0)
        self.assertLessEqual(state.exposure_efpd, 10.0)


if __name__ == "__main__":
    unittest.main()
