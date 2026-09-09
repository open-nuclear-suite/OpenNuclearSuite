"""Verification tests for the first subchannel-laboratory chunk."""

from __future__ import annotations

import unittest
import csv
import tempfile
from pathlib import Path

import numpy as np

from simulators.SubchannelLaboratory.correlations import blasius_friction, churchill_friction
from simulators.SubchannelLaboratory.single_channel import (
    ChannelGeometry,
    ChannelInputs,
    SingleChannelModel,
    StatisticalSettings,
    run_statistical_hot_channel,
)
from simulators.SubchannelLaboratory.void_models import VOID_FRACTION_MODELS
from simulators.SubchannelLaboratory.two_phase_friction import TWO_PHASE_FRICTION_MODELS
from simulators.SubchannelLaboratory.axial_heat_shapes import AXIAL_HEAT_SHAPES
from simulators.SubchannelLaboratory.chf_correlations import (
    biasi_critical_heat_flux_W_m2,
    bowring_critical_heat_flux_W_m2,
    epri_1_critical_heat_flux_W_m2,
)
from simulators.SubchannelLaboratory.neighboring_channels import (
    CHANNEL_LABELS,
    CommonPlenumChannelModel,
    ParallelChannelSetting,
)
from simulators.SubchannelLaboratory.groeneveld_lut import (
    PRESSURE_MPA,
    interpolate_groeneveld_2006,
    validate_groeneveld_data,
)
from simulators.SubchannelLaboratory.groeneveld_uncertainty import (
    UNCERTAINTY_MASK,
    validate_uncertainty_mask,
)
from simulators.SubchannelLaboratory.csv_export import write_channel_result_csv
from simulators.SubchannelLaboratory.localized_hot_factors import LocalizedPowerFactor


class SingleChannelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = SingleChannelModel()
        cls.geometry = ChannelGeometry()
        cls.inputs = ChannelInputs()

    def test_energy_is_conserved(self) -> None:
        result = self.model.solve(self.geometry, self.inputs)
        mass_flow = self.inputs.mass_flow_kg_s * self.inputs.flow_factor
        gained = mass_flow * (result.outlet_enthalpy_kj_kg - result.inlet_enthalpy_kj_kg) * 1000.0
        self.assertAlmostEqual(gained, result.deposited_power_W, places=7)
        self.assertAlmostEqual(
            result.heated_surface_area_m2,
            self.geometry.wetted_perimeter_m * self.geometry.heated_length_m,
        )
        self.assertAlmostEqual(
            result.average_surface_heat_flux_W_m2,
            result.deposited_power_W / result.heated_surface_area_m2,
        )
        self.assertAlmostEqual(
            result.outlet_pressure_mpa,
            self.inputs.inlet_pressure_mpa - result.total_heated_pressure_drop_kpa / 1000.0,
        )

    def test_pressure_falls_and_enthalpy_rises(self) -> None:
        result = self.model.solve(self.geometry, self.inputs)
        self.assertTrue(np.all(np.diff(result.pressure_mpa) < 0.0))
        self.assertTrue(np.all(np.diff(result.enthalpy_kj_kg) > 0.0))
        self.assertEqual(len(result.flow_regime), self.geometry.node_count)
        np.testing.assert_array_equal(result.chf_correlation_valid, np.isfinite(result.dnbr))
        self.assertTrue(np.all(result.velocity_m_s > 0.0))
        self.assertTrue(np.all(result.reynolds > 0.0))
        self.assertTrue(np.all(result.prandtl > 0.0))
        self.assertTrue(np.all(result.nusselt > 0.0))
        self.assertTrue(np.all(np.diff(result.cumulative_pressure_drop_kpa) > 0.0))
        self.assertTrue(np.all(result.node_pressure_drop_kpa > 0.0))
        self.assertAlmostEqual(
            result.total_heated_pressure_drop_kpa,
            float(np.sum(result.node_pressure_drop_kpa)),
            places=10,
        )
        self.assertTrue(np.all(result.viscosity_Pa_s > 0.0))
        self.assertTrue(np.all(result.conductivity_W_mK > 0.0))
        self.assertTrue(np.all(result.surface_tension_N_m > 0.0))
        provenance = {item.quantity: item.model_key for item in result.provenance}
        self.assertEqual(provenance["transport_properties"], "if97_transport_table")
        self.assertEqual(provenance["critical_heat_flux"], "tong_w3")

    def test_editable_length_changes_energy_deposition(self) -> None:
        short = self.model.solve(ChannelGeometry(heated_length_m=2.0), self.inputs)
        long = self.model.solve(ChannelGeometry(heated_length_m=4.0), self.inputs)
        self.assertAlmostEqual(long.deposited_power_W / short.deposited_power_W, 2.0, places=10)
        self.assertGreater(long.outlet_enthalpy_kj_kg, short.outlet_enthalpy_kj_kg)

    def test_biasi_chf_selection_and_validity_are_explicit(self) -> None:
        self.assertTrue(np.isfinite(biasi_critical_heat_flux_W_m2(10.0, 3000.0, 0.05, 0.01)))
        self.assertTrue(np.isnan(biasi_critical_heat_flux_W_m2(15.5, 3000.0, 0.05, 0.01)))
        selected = self.model.solve(
            self.geometry, ChannelInputs(inlet_pressure_mpa=10.0, chf_key="biasi")
        )
        self.assertEqual(selected.selected_chf_key, "biasi")
        np.testing.assert_array_equal(
            selected.critical_heat_flux_W_m2, selected.chf_predictions_W_m2["biasi"]
        )
        self.assertIn("tong_w3", selected.chf_predictions_W_m2)
        provenance = {item.quantity: item.model_key for item in selected.provenance}
        self.assertEqual(provenance["critical_heat_flux"], "biasi")

    def test_bowring_chf_selection_quality_trend_and_domain(self) -> None:
        subcooled = bowring_critical_heat_flux_W_m2(
            15.5, 4000.0, -0.10, 0.012, 1.0e6, 3.66
        )
        saturated = bowring_critical_heat_flux_W_m2(
            15.5, 4000.0, 0.05, 0.012, 1.0e6, 3.66
        )
        self.assertTrue(np.isfinite(subcooled))
        self.assertGreater(subcooled, saturated)
        self.assertTrue(np.isnan(bowring_critical_heat_flux_W_m2(
            20.0, 4000.0, 0.0, 0.012, 1.0e6, 3.66
        )))
        selected = self.model.solve(self.geometry, ChannelInputs(chf_key="bowring"))
        self.assertEqual(selected.selected_chf_key, "bowring")
        self.assertTrue(np.any(selected.chf_validity["bowring"]))
        np.testing.assert_array_equal(
            selected.critical_heat_flux_W_m2, selected.chf_predictions_W_m2["bowring"]
        )

    def test_groeneveld_grid_interpolation_corrections_and_selection(self) -> None:
        validation = validate_groeneveld_data()
        self.assertTrue(validation.valid)
        self.assertEqual(validation.shape, (24, 21, 23))
        np.testing.assert_array_equal(PRESSURE_MPA, (0.1, 0.3, 0.5, *range(1, 22)))
        grid = interpolate_groeneveld_2006(
            0.1, 0.0, -0.5, 0.008, 0.0126, 0.0095, 3.66, 900.0, 5.0
        )
        self.assertTrue(grid.valid)
        self.assertAlmostEqual(grid.chf_W_m2, 8_111_000.0)
        self.assertIn("P[0.1,0.3] w=0", grid.detail)
        self.assertEqual(grid.uncertainty_class, 2)
        self.assertEqual(grid.worst_corner_class, 2)
        self.assertIn("avoid extrapolation", grid.detail)
        printed_plane = interpolate_groeneveld_2006(
            5.0, 0.0, -0.5, 0.008, 0.0126, 0.0095, 3.66, 800.0, 20.0,
            diameter_correction=False,
        )
        self.assertAlmostEqual(printed_plane.chf_W_m2, 6_044_000.0)
        self.assertIn("P[5,6] w=0", printed_plane.detail)
        lqr = interpolate_groeneveld_2006(
            1.0, 500.0, 0.5, 0.008, 0.0126, 0.0095, 3.66, 800.0, 20.0,
            diameter_correction=False,
        )
        self.assertEqual(lqr.uncertainty_class, 3)
        self.assertEqual(lqr.uncertainty_label, "low-quality region (LQR)")
        mixed = interpolate_groeneveld_2006(
            1.0, 500.0, 0.475, 0.008, 0.0126, 0.0095, 3.66, 800.0, 20.0,
            diameter_correction=False,
        )
        self.assertEqual(mixed.worst_corner_class, 3)
        self.assertIn("corner class weights=", mixed.detail)
        uncorrected = interpolate_groeneveld_2006(
            10.0, 3000.0, 0.1, 0.012, 0.0126, 0.0095, 3.66, 700.0, 40.0,
            diameter_correction=False,
        )
        corrected = interpolate_groeneveld_2006(
            10.0, 3000.0, 0.1, 0.012, 0.0126, 0.0095, 3.66, 700.0, 40.0,
            diameter_correction=True,
        )
        self.assertAlmostEqual(
            corrected.chf_W_m2 / uncorrected.chf_W_m2, np.sqrt(0.008 / 0.012)
        )
        outside = interpolate_groeneveld_2006(
            22.0, 3000.0, 0.1, 0.012, 0.0126, 0.0095, 3.66, 700.0, 40.0
        )
        self.assertFalse(outside.valid)
        self.assertTrue(np.isnan(outside.chf_W_m2))
        selected = self.model.solve(
            self.geometry, ChannelInputs(chf_key="groeneveld_2006")
        )
        self.assertEqual(selected.selected_chf_key, "groeneveld_2006")
        self.assertTrue(np.any(selected.chf_validity["groeneveld_2006"]))
        self.assertIn("K1 diameter", selected.chf_interpolation_detail["groeneveld_2006"][0])

    def test_groeneveld_uncertainty_mask_is_coordinate_aligned(self) -> None:
        validation = validate_uncertainty_mask()
        self.assertTrue(validation.valid)
        self.assertEqual(validation.shape, (24, 21, 23))
        self.assertEqual(validation.class_counts, (4992, 5444, 877, 279))
        # Printed Appendix C examples: low-pressure zero-flow subcooling is
        # medium gray, while the 1 MPa/G=500/x=0.5 cell is in the black LQR.
        self.assertEqual(UNCERTAINTY_MASK[0, 0, 0], 2)
        self.assertEqual(UNCERTAINTY_MASK[3, 4, 17], 3)

    def test_total_channel_length_separates_unheated_sections(self) -> None:
        geometry = ChannelGeometry(
            heated_length_m=3.5,
            unheated_inlet_length_m=0.4,
            unheated_outlet_length_m=0.2,
        )
        self.assertAlmostEqual(geometry.total_channel_length_m, 4.1)
        result = self.model.solve(geometry, self.inputs)
        self.assertLess(result.z_m[-1], geometry.heated_length_m)

    def test_pressure_drop_components_close_to_total(self) -> None:
        result = self.model.solve(self.geometry, self.inputs)
        np.testing.assert_allclose(
            result.total_pressure_drop_kpa,
            result.friction_pressure_drop_kpa
            + result.gravity_pressure_drop_kpa
            + result.acceleration_pressure_drop_kpa,
            rtol=1.0e-12,
        )
        self.assertAlmostEqual(
            result.total_heated_pressure_drop_kpa,
            result.total_friction_pressure_drop_kpa
            + result.total_gravity_pressure_drop_kpa
            + result.total_acceleration_pressure_drop_kpa,
            places=10,
        )
        self.assertAlmostEqual(
            self.inputs.inlet_pressure_mpa - result.outlet_pressure_mpa,
            result.total_heated_pressure_drop_kpa / 1000.0,
            places=10,
        )

    def test_inclination_controls_signed_elevation_head(self) -> None:
        horizontal = self.model.solve(
            self.geometry, ChannelInputs(inclination_degrees=0.0)
        )
        upward = self.model.solve(
            self.geometry, ChannelInputs(inclination_degrees=90.0)
        )
        downward = self.model.solve(
            self.geometry, ChannelInputs(inclination_degrees=-90.0)
        )
        self.assertAlmostEqual(horizontal.total_gravity_pressure_drop_kpa, 0.0, places=12)
        self.assertGreater(upward.total_gravity_pressure_drop_kpa, 0.0)
        self.assertLess(downward.total_gravity_pressure_drop_kpa, 0.0)
        self.assertGreater(
            upward.total_heated_pressure_drop_kpa,
            horizontal.total_heated_pressure_drop_kpa,
        )

    def test_homogeneous_boiling_case_has_acceleration_loss(self) -> None:
        result = self.model.solve(
            self.geometry,
            ChannelInputs(mass_flow_kg_s=0.20, average_linear_heat_W_m=20_000.0),
        )
        self.assertGreater(result.outlet_void_fraction, 0.0)
        self.assertGreater(result.total_acceleration_pressure_drop_kpa, 0.0)
        self.assertTrue(np.all(result.mixture_density_kg_m3 > 0.0))

    def test_void_models_preserve_phase_boundaries(self) -> None:
        for model in VOID_FRACTION_MODELS.values():
            common = dict(
                rho_l=700.0, rho_g=35.0, mass_flux=1500.0,
                surface_tension=0.02, inclination_degrees=90.0,
            )
            self.assertEqual(model.evaluate(quality=-0.1, **common).void_fraction, 0.0)
            self.assertEqual(model.evaluate(quality=1.1, **common).void_fraction, 1.0)

    def test_selectable_slip_models_change_void_and_hydraulics(self) -> None:
        case = dict(mass_flow_kg_s=0.20, average_linear_heat_W_m=20_000.0)
        results = {
            key: self.model.solve(
                self.geometry, ChannelInputs(**case, void_model_key=key)
            )
            for key in VOID_FRACTION_MODELS
        }
        outlet_voids = {round(result.outlet_void_fraction, 5) for result in results.values()}
        total_drops = {round(result.total_heated_pressure_drop_kpa, 4) for result in results.values()}
        self.assertEqual(len(outlet_voids), len(VOID_FRACTION_MODELS))
        self.assertEqual(len(total_drops), len(VOID_FRACTION_MODELS))
        self.assertTrue(np.allclose(results["homogeneous"].slip_ratio, 1.0))
        self.assertGreater(results["zivi"].slip_ratio[-1], results["smith"].slip_ratio[-1])

    def test_drift_flux_validity_guard_flags_horizontal_use(self) -> None:
        result = self.model.solve(
            self.geometry,
            ChannelInputs(
                mass_flow_kg_s=0.20,
                average_linear_heat_W_m=20_000.0,
                void_model_key="zuber_findlay",
                inclination_degrees=0.0,
            ),
        )
        two_phase = (result.equilibrium_quality > 0.0) & (result.equilibrium_quality < 1.0)
        self.assertGreater(np.count_nonzero(two_phase), 0)
        self.assertTrue(np.all(~result.void_model_valid[two_phase]))

    def test_two_phase_friction_models_change_friction_loss(self) -> None:
        case = dict(
            mass_flow_kg_s=0.15,
            average_linear_heat_W_m=18_000.0,
            friction_key="churchill",
        )
        results = {
            key: self.model.solve(
                self.geometry, ChannelInputs(**case, two_phase_friction_key=key)
            )
            for key in TWO_PHASE_FRICTION_MODELS
        }
        losses = {
            round(result.total_friction_pressure_drop_kpa, 5)
            for result in results.values()
        }
        self.assertEqual(len(losses), len(TWO_PHASE_FRICTION_MODELS))
        self.assertTrue(np.allclose(results["homogeneous"].two_phase_friction_multiplier, 1.0))
        self.assertGreater(
            results["lockhart_chisholm"].total_friction_pressure_drop_kpa,
            results["homogeneous"].total_friction_pressure_drop_kpa,
        )
        self.assertGreater(
            results["friedel"].total_friction_pressure_drop_kpa,
            results["homogeneous"].total_friction_pressure_drop_kpa,
        )

    def test_separated_friction_reverts_at_single_phase_boundaries(self) -> None:
        common = dict(
            pressure_mpa=10.0, mass_flux=1500.0, diameter=0.012, length=0.1,
            rho_l=700.0, rho_g=35.0, mu_l=9.0e-5, mu_g=2.0e-5,
            surface_tension=0.02, inclination_degrees=90.0,
            friction_evaluator=lambda _re: 0.02,
            baseline_dp_kpa=1.25, reynolds=100_000.0,
        )
        for key, model in TWO_PHASE_FRICTION_MODELS.items():
            if key == "martinelli_nelson":
                qualities = (-0.1, 1.1)
            else:
                qualities = (-0.1, 0.0, 1.0, 1.1)
            for quality in qualities:
                result = model.evaluate(quality=quality, **common)
                self.assertEqual(result.pressure_drop_kpa, 1.25)
                self.assertEqual(result.multiplier, 1.0)

    def test_martinelli_nelson_table_and_bilinear_interpolation(self) -> None:
        model = TWO_PHASE_FRICTION_MODELS["martinelli_nelson"]
        common = dict(
            mass_flux=1500.0, diameter=0.012, length=0.1,
            rho_l=700.0, rho_g=35.0, mu_l=9.0e-5, mu_g=2.0e-5,
            surface_tension=0.02, inclination_degrees=90.0,
            friction_evaluator=lambda _re: 0.02,
            baseline_dp_kpa=1.25, reynolds=100_000.0,
        )
        tabulated = model.evaluate(quality=0.50, pressure_mpa=13.8, **common)
        self.assertAlmostEqual(tabulated.multiplier, 5.59)
        midpoint = model.evaluate(quality=0.55, pressure_mpa=15.5, **common)
        expected = (5.59 + 6.34 + 3.38 + 3.70) / 4.0
        self.assertAlmostEqual(midpoint.multiplier, expected)
        self.assertIn("P=13.8-17.2", midpoint.detail)
        outside = model.evaluate(quality=0.5, pressure_mpa=25.0, **common)
        self.assertFalse(outside.valid)
        self.assertEqual(outside.pressure_drop_kpa, 1.25)

    def test_axial_heat_shapes_preserve_total_power_and_change_boiling_height(self) -> None:
        case = dict(mass_flow_kg_s=0.20, average_linear_heat_W_m=20_000.0)
        uniform = self.model.solve(
            self.geometry, ChannelInputs(**case, heat_shape_key="uniform")
        )
        sinusoidal = self.model.solve(
            self.geometry, ChannelInputs(**case, heat_shape_key="sinusoidal")
        )
        self.assertEqual(set(AXIAL_HEAT_SHAPES), {
            "uniform", "sinusoidal", "chopped_cosine", "offset_cosine",
            "skewed_sine", "piecewise_linear",
        })
        self.assertAlmostEqual(uniform.deposited_power_W, sinusoidal.deposited_power_W)
        self.assertTrue(np.allclose(uniform.axial_heat_shape_factor, 1.0))
        self.assertAlmostEqual(np.mean(sinusoidal.axial_heat_shape_factor), 1.0)
        for key in AXIAL_HEAT_SHAPES:
            profile = self.model.solve(
                self.geometry,
                ChannelInputs(**case, heat_shape_key=key, heat_shape_parameter=0.25),
            )
            self.assertAlmostEqual(np.mean(profile.axial_heat_shape_factor), 1.0)
            self.assertAlmostEqual(profile.deposited_power_W, uniform.deposited_power_W)
        lower_skew = self.model.solve(
            self.geometry,
            ChannelInputs(**case, heat_shape_key="skewed_sine", heat_shape_parameter=-0.7),
        )
        upper_skew = self.model.solve(
            self.geometry,
            ChannelInputs(**case, heat_shape_key="skewed_sine", heat_shape_parameter=0.7),
        )
        self.assertLess(
            np.argmax(lower_skew.axial_heat_shape_factor),
            np.argmax(upper_skew.axial_heat_shape_factor),
        )
        self.assertNotAlmostEqual(
            uniform.onset_nucleate_boiling_height_m,
            sinusoidal.onset_nucleate_boiling_height_m,
        )
        for result in (uniform, sinusoidal):
            self.assertAlmostEqual(
                result.nonboiling_length_m
                + result.subcooled_boiling_length_m
                + result.bulk_two_phase_length_m,
                self.geometry.heated_length_m,
            )
            self.assertGreaterEqual(result.bulk_boiling_height_m, result.onset_nucleate_boiling_height_m)

    def test_localized_power_factors_combine_and_offer_two_power_modes(self) -> None:
        factors = (
            LocalizedPowerFactor(0.35, 1.20, 0.12, "gaussian"),
            LocalizedPowerFactor(0.70, 1.10, 0.20, "triangular"),
        )
        nominal = self.model.solve(self.geometry, ChannelInputs(heat_shape_key="uniform"))
        redistributed = self.model.solve(self.geometry, ChannelInputs(
            heat_shape_key="uniform", localized_power_factors=factors,
            preserve_power_with_local_factors=True,
        ))
        additional = self.model.solve(self.geometry, ChannelInputs(
            heat_shape_key="uniform", localized_power_factors=factors,
            preserve_power_with_local_factors=False,
        ))
        self.assertAlmostEqual(redistributed.deposited_power_W, nominal.deposited_power_W)
        self.assertGreater(additional.deposited_power_W, nominal.deposited_power_W)
        self.assertGreater(np.max(redistributed.localized_power_factor), 1.0)
        self.assertAlmostEqual(
            np.max(redistributed.combined_power_factor),
            np.max(redistributed.axial_heat_shape_factor) * 1.15,
        )
        self.assertNotEqual(
            int(np.argmax(redistributed.linear_heat_rate_W_m)),
            int(np.argmax(nominal.linear_heat_rate_W_m)),
        )

    def test_statistical_rss_hot_factor_can_be_compared_with_multiplication(self) -> None:
        factors = (
            LocalizedPowerFactor(0.50, 1.20, 1.0, "rectangular"),
            LocalizedPowerFactor(0.50, 1.10, 1.0, "rectangular"),
        )
        multiplied = self.model.solve(self.geometry, ChannelInputs(
            heat_shape_key="uniform", power_factor=1.15,
            localized_power_factors=factors, preserve_power_with_local_factors=False,
            hot_factor_combination_method="multiplicative",
        ))
        rss = self.model.solve(self.geometry, ChannelInputs(
            heat_shape_key="uniform", power_factor=1.15,
            localized_power_factors=factors, preserve_power_with_local_factors=False,
            hot_factor_combination_method="statistical_rss",
        ))
        self.assertTrue(np.allclose(multiplied.combined_power_factor, 1.15 * 1.20 * 1.10))
        expected_rss = 1.0 + np.sqrt(0.15**2 + 0.20**2 + 0.10**2)
        self.assertTrue(np.allclose(rss.combined_power_factor, expected_rss))
        self.assertGreater(multiplied.deposited_power_W, rss.deposited_power_W)
        self.assertEqual(rss.hot_factor_combination_method, "statistical_rss")

        preserved = self.model.solve(self.geometry, ChannelInputs(
            heat_shape_key="sinusoidal", power_factor=1.15,
            localized_power_factors=factors, preserve_power_with_local_factors=True,
            hot_factor_combination_method="statistical_rss",
        ))
        nominal = 18_000.0 * 1.15 * self.geometry.heated_length_m
        self.assertAlmostEqual(preserved.deposited_power_W, nominal)

    def test_friedel_domain_guard_flags_high_mass_flux(self) -> None:
        result = self.model.solve(
            self.geometry,
            ChannelInputs(
                mass_flow_kg_s=0.20,
                average_linear_heat_W_m=20_000.0,
                two_phase_friction_key="friedel",
            ),
        )
        two_phase = (result.equilibrium_quality > 0.0) & (result.equilibrium_quality < 1.0)
        self.assertGreater(np.count_nonzero(two_phase), 0)
        self.assertTrue(np.all(~result.two_phase_friction_valid[two_phase]))

    def test_reduced_flow_exposes_boiling_and_keeps_some_w3_nodes(self) -> None:
        result = self.model.solve(
            self.geometry,
            ChannelInputs(mass_flow_kg_s=0.20, average_linear_heat_W_m=20_000.0),
        )
        self.assertIn("bulk two-phase", result.flow_regime)
        self.assertGreater(np.max(result.void_fraction), 0.0)
        self.assertGreater(np.count_nonzero(result.chf_correlation_valid), 0)
        self.assertGreater(np.count_nonzero(result.nucleate_boiling_active), 0)
        self.assertIn("chen", result.wall_heat_transfer_mode)

    def test_selectable_boiling_correlations_change_wall_solution(self) -> None:
        case = dict(
            inlet_pressure_mpa=12.0,
            inlet_temperature_C=270.0,
            mass_flow_kg_s=0.20,
            average_linear_heat_W_m=20_000.0,
        )
        peaks = {
            key: self.model.solve(
                self.geometry, ChannelInputs(**case, boiling_key=key)
            ).peak_wall_temperature_C
            for key in ("jens_lottes", "thom", "chen")
        }
        self.assertEqual(len({round(value, 3) for value in peaks.values()}), 3)

    def test_cladding_choice_changes_inner_not_outer_surface(self) -> None:
        zirconium = self.model.solve(
            self.geometry, ChannelInputs(cladding_key="zircaloy4")
        )
        sic = self.model.solve(
            self.geometry, ChannelInputs(cladding_key="silicon_carbide")
        )
        np.testing.assert_allclose(zirconium.wall_temperature_C, sic.wall_temperature_C)
        self.assertGreater(
            np.max(sic.inner_clad_temperature_C),
            np.max(zirconium.inner_clad_temperature_C),
        )

    def test_expected_power_and_flow_sensitivity(self) -> None:
        nominal = self.model.solve(self.geometry, self.inputs)
        hotter = self.model.solve(self.geometry, ChannelInputs(power_factor=1.25))
        lower_flow = self.model.solve(self.geometry, ChannelInputs(flow_factor=0.85))
        self.assertGreater(hotter.peak_wall_temperature_C, nominal.peak_wall_temperature_C)
        self.assertGreater(lower_flow.bulk_temperature_C[-1], nominal.bulk_temperature_C[-1])

    def test_correlation_domain_metadata(self) -> None:
        self.assertTrue(blasius_friction(50_000.0).valid)
        self.assertFalse(blasius_friction(1_000.0).valid)
        self.assertAlmostEqual(churchill_friction(1000.0).value, 0.064, places=4)

    def test_statistical_samples_are_reproducible(self) -> None:
        settings = StatisticalSettings(sample_count=12, seed=42)
        first = run_statistical_hot_channel(self.model, self.geometry, self.inputs, settings)
        second = run_statistical_hot_channel(self.model, self.geometry, self.inputs, settings)
        np.testing.assert_allclose(first.minimum_dnbr, second.minimum_dnbr, equal_nan=True)
        np.testing.assert_allclose(first.peak_wall_temperature_C, second.peak_wall_temperature_C)
        self.assertGreater(np.std(first.peak_wall_temperature_C), 0.0)

    def test_epri_1_chf_is_selectable_and_range_guarded(self) -> None:
        value = epri_1_critical_heat_flux_W_m2(10.0, 3000.0, 0.05, -0.20, 1.0e6)
        self.assertTrue(np.isfinite(value))
        self.assertGreater(value, 0.0)
        self.assertTrue(np.isnan(epri_1_critical_heat_flux_W_m2(
            0.5, 3000.0, 0.05, -0.20, 1.0e6
        )))
        selected = self.model.solve(self.geometry, ChannelInputs(chf_key="epri_1"))
        self.assertEqual(selected.selected_chf_key, "epri_1")
        self.assertTrue(np.any(selected.chf_validity["epri_1"]))
        self.assertIn("base EPRI-1", selected.chf_interpolation_detail["epri_1"][0])

    def test_csv_export_contains_nodal_results_all_chf_models_and_totals(self) -> None:
        result = self.model.solve(self.geometry, self.inputs)
        with tempfile.TemporaryDirectory() as directory:
            path = write_channel_result_csv(Path(directory) / "channel.csv", result)
            with path.open(newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), self.geometry.node_count)
        self.assertEqual(int(rows[0]["node"]), 1)
        self.assertEqual(int(rows[-1]["node"]), self.geometry.node_count)
        self.assertIn("CHF_groeneveld_2006_W_m2", rows[0])
        self.assertIn("CHF_groeneveld_2006_detail", rows[0])
        self.assertAlmostEqual(
            float(rows[-1]["total_heated_dP_kPa"]), result.total_heated_pressure_drop_kpa
        )

    def test_neswc_common_plenum_conserves_total_flow_and_equalizes_pressure(self) -> None:
        settings = tuple(
            ParallelChannelSetting(label, power)
            for label, power in zip(
                CHANNEL_LABELS,
                (1.0, 1.0, 1.0, 1.0, 1.08),
            )
        )
        result = CommonPlenumChannelModel(self.model).solve(
            self.geometry, self.inputs, settings
        )
        self.assertEqual(len(result.channels), 5)
        self.assertGreater(
            result.channels[4].deposited_power_W, result.channels[0].deposited_power_W
        )
        self.assertGreater(
            result.channels[4].bulk_temperature_C[-1],
            result.channels[0].bulk_temperature_C[-1],
        )
        self.assertAlmostEqual(
            float(np.sum(result.mass_flows_kg_s)), result.total_mass_flow_kg_s
        )
        self.assertTrue(result.converged)
        self.assertLess(result.pressure_drop_spread_kpa, 0.1)
        self.assertLess(result.mass_flows_kg_s[4], result.mass_flows_kg_s[0])
        for mass_flow, channel in zip(result.mass_flows_kg_s, result.channels):
            gained = mass_flow * (
                channel.outlet_enthalpy_kj_kg - channel.inlet_enthalpy_kj_kg
            ) * 1000.0
            self.assertAlmostEqual(gained, channel.deposited_power_W, delta=1.0)
            self.assertTrue(np.all(np.diff(channel.enthalpy_kj_kg) > 0.0))

    def test_neswc_limiting_location_matches_global_minimum_dnbr(self) -> None:
        settings = tuple(
            ParallelChannelSetting(label, 1.0 + 0.04 * index)
            for index, label in enumerate(CHANNEL_LABELS)
        )
        result = CommonPlenumChannelModel(self.model).solve(
            self.geometry,
            ChannelInputs(inlet_temperature_C=270.0, mass_flow_kg_s=0.20),
            settings,
        )
        channel_index = result.limiting_channel_index
        node_index = result.limiting_node_index
        self.assertIsNotNone(channel_index)
        self.assertIsNotNone(node_index)
        minima = [channel.minimum_dnbr for channel in result.channels]
        self.assertEqual(channel_index, int(np.nanargmin(minima)))
        self.assertEqual(
            node_index, int(np.nanargmin(result.channels[channel_index].dnbr))
        )

    def test_neswc_symmetric_channels_split_total_flow_equally(self) -> None:
        settings = tuple(ParallelChannelSetting(label) for label in CHANNEL_LABELS)
        result = CommonPlenumChannelModel(self.model).solve(
            self.geometry, self.inputs, settings
        )
        np.testing.assert_allclose(result.flow_ratios, np.ones(5), rtol=1.0e-10)
        drops = [channel.total_heated_pressure_drop_kpa for channel in result.channels]
        np.testing.assert_allclose(drops, np.full(5, drops[0]), rtol=1.0e-10)

    def test_neswc_stage_rejects_wrong_channel_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly five"):
            CommonPlenumChannelModel(self.model).solve(
                self.geometry,
                self.inputs,
                (ParallelChannelSetting("only"),),
            )


if __name__ == "__main__":
    unittest.main()
