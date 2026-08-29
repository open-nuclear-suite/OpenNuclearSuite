"""R9 provenance and conversion tests for source-backed BWR parameters."""

import unittest

from bwr_parameter_basis import R9_PARAMETER_BASIS, UNRESOLVED_R9_PARAMETERS
from bwr_plant_model import BWRControlInputs
from thermal_hydraulics_gui_backend import ThermalHydraulicsGUIBackend


class BWRParameterBasisTests(unittest.TestCase):
    def setUp(self):
        self.backend = ThermalHydraulicsGUIBackend(); self.backend.select_plant("BWR")

    def test_source_backed_constants_match_machine_readable_basis(self):
        constants = self.backend.sim.c
        for name, basis in R9_PARAMETER_BASIS.items():
            if hasattr(constants, name):
                with self.subTest(parameter=name):
                    self.assertAlmostEqual(getattr(constants, name), basis.value, places=2)
            self.assertTrue(basis.source.startswith("https://"))
            self.assertTrue(basis.applicability)

    def test_rated_steam_flow_is_derived_from_energy_balance(self):
        model = self.backend.sim.physics
        self.assertAlmostEqual(model.reference_steam_flow_kg_s, 1685.0, delta=8.0)
        expected_quality = model.reference_steam_flow_kg_s / self.backend.sim.c.bwr_reference_core_flow_kg_s
        self.assertAlmostEqual(model.reference_flow_quality, expected_quality)
        self.assertAlmostEqual(model.reference_flow_quality, 0.129, delta=0.003)

    def test_effective_core_head_closes_at_nominal_flow(self):
        state = self.backend.state
        self.assertAlmostEqual(state.bwr_friction_head_m, self.backend.sim.c.bwr_loop_loss_head_m, places=2)
        self.assertAlmostEqual(
            state.bwr_core_friction_head_m + state.bwr_single_phase_loss_head_m
            + state.bwr_acceleration_head_m,
            self.backend.sim.c.bwr_loop_loss_head_m, places=2,
        )

    def test_source_rated_high_pressure_injection_points_are_reproduced(self):
        model = self.backend.sim.physics
        _, diagnostics = model.rhs(
            0.0, model.pack(self.backend.state),
            BWRControlInputs(rcic_pct=100.0, hpci_pct=100.0, auto_bwr_safety=False),
        )
        self.assertAlmostEqual(diagnostics.rcic_flow_kg_s, 37.85, delta=1.0)
        self.assertAlmostEqual(diagnostics.hpci_flow_kg_s, 315.0, delta=5.0)

    def test_unsupported_parameters_remain_explicit(self):
        self.assertIn("bwr_pump_shutoff_head_m", UNRESOLVED_R9_PARAMETERS)
        self.assertIn("bwr_reference_leg_sensitivity", UNRESOLVED_R9_PARAMETERS)
        self.assertIn("alpha_void", UNRESOLVED_R9_PARAMETERS)


if __name__ == "__main__":
    unittest.main()
