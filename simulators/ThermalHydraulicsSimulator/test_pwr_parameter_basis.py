"""P2-2 provenance and conversion tests for source-backed PWR parameters."""

import unittest

from pwr_parameter_basis import (
    LOFT_TIMING_EVIDENCE, P2_PARAMETER_BASIS, UNRESOLVED_P2_PARAMETERS,
)
from thermal_hydraulics_gui_backend import ThermalHydraulicsGUIBackend


class PWRParameterBasisTests(unittest.TestCase):
    def setUp(self):
        self.backend = ThermalHydraulicsGUIBackend()

    def test_source_backed_constants_match_machine_readable_basis(self):
        constants = self.backend.sim.c
        for name, basis in P2_PARAMETER_BASIS.items():
            with self.subTest(parameter=name):
                self.assertTrue(hasattr(constants, name))
                self.assertAlmostEqual(getattr(constants, name), basis.value, places=2)
                self.assertTrue(basis.source.startswith("https://"))
                self.assertTrue(basis.conversion)
                self.assertTrue(basis.applicability)

    def test_source_temperature_conversion_and_leg_split(self):
        state = self.backend.state
        self.assertAlmostEqual(self.backend.sim.c.TrefCool, 573.9 - 273.15, places=8)
        self.assertAlmostEqual(state.pwr_hot_leg_temperature_C, 321.25, places=2)
        self.assertAlmostEqual(state.pwr_cold_leg_temperature_C, 280.25, places=2)
        self.assertAlmostEqual(
            state.pwr_hot_leg_temperature_C - state.pwr_cold_leg_temperature_C,
            41.0, places=8,
        )

    def test_nominal_pump_and_loop_head_close(self):
        state = self.backend.state
        self.assertAlmostEqual(state.pwr_pump_head_m, 111.25, places=2)
        self.assertAlmostEqual(state.pwr_loop_loss_head_m, 111.25, places=2)
        self.backend.sim.step_model(0.05)
        self.assertAlmostEqual(state.pwr_primary_flow_fraction, 1.0, places=8)

    def test_secondary_reference_matches_source_basis(self):
        state = self.backend.state
        self.assertAlmostEqual(state.pwr_secondary_pressure_mpa, 5.76, places=6)
        self.assertAlmostEqual(state.pwr_secondary_mass_kg, 76965.77, places=2)
        self.backend.sim.step_model(0.05)
        self.assertAlmostEqual(state.pwr_secondary_mass_residual_kg_s, 0.0, places=8)
        self.assertAlmostEqual(state.pwr_secondary_energy_residual_MW, 0.0, places=8)

    def test_loft_timing_is_evidence_not_silently_adopted_controls(self):
        constants = self.backend.sim.c
        self.assertNotEqual(constants.pwr_hpsi_start_delay_s,
                            LOFT_TIMING_EVIDENCE["hpsi_injection_s"])
        self.assertNotEqual(constants.pwr_lpsi_start_delay_s,
                            LOFT_TIMING_EVIDENCE["lpsi_injection_s"])
        self.assertIn("Sequence evidence only", LOFT_TIMING_EVIDENCE["applicability"])

    def test_unsupported_parameters_remain_explicit(self):
        self.assertIn("break_coeff", UNRESOLVED_P2_PARAMETERS)
        self.assertIn("pwr_hpsi_runout_fraction_s", UNRESOLVED_P2_PARAMETERS)
        self.assertIn("pressurizer_tau", UNRESOLVED_P2_PARAMETERS)
        self.assertIn("pwr_axial_void_reactivity_pcm_per_fraction",
                      UNRESOLVED_P2_PARAMETERS)


if __name__ == "__main__":
    unittest.main()
