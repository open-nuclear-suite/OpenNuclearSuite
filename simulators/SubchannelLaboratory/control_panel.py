"""Reusable left-side controls for the Subchannel Laboratory window."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .axial_heat_shapes import AXIAL_HEAT_SHAPES
from .chf_correlations import CHF_CORRELATIONS
from .correlations import BOILING_CORRELATIONS, FRICTION_CORRELATIONS, HEAT_TRANSFER_CORRELATIONS
from .materials import CLADDING_MATERIALS
from .two_phase_friction import TWO_PHASE_FRICTION_MODELS
from .void_models import VOID_FRACTION_MODELS


EXPORTED_CONTROLS = (
    "pressure", "temperature", "flow", "heat", "heat_shape", "heat_shape_parameter", "power_factor",
    "flow_factor", "length", "unheated_inlet", "unheated_outlet", "pitch_mm",
    "rod_od_mm", "clad_id_mm", "roughness_um", "inclination", "nodes",
    "friction", "heat_transfer", "boiling", "chf_model", "void_model", "two_phase_friction",
    "cladding", "groeneveld_k1", "groeneveld_k2", "groeneveld_k4",
    "samples", "seed", "deterministic_mode", "statistical_mode",
    "run_mode_group", "run_button", "solution_button", "channel_balance_summary",
    "export_button", "advanced_hot_factors_button", "localized_factor_status", "summary",
)


def _spin(value: float, minimum: float, maximum: float,
          decimals: int = 2) -> QtWidgets.QDoubleSpinBox:
    control = QtWidgets.QDoubleSpinBox()
    control.setRange(minimum, maximum)
    control.setDecimals(decimals)
    control.setValue(value)
    return control


def _section_label(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def _combo(models, selected: str) -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox()
    for key, model in models.items():
        combo.addItem(model.label, key)
    combo.setCurrentIndex(combo.findData(selected))
    return combo


class SubchannelControlPanel(QtWidgets.QWidget):
    """Owns input widgets but leaves application behavior to the main window."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(9, 4, 9, 9)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        self.pressure = _spin(15.5, 0.1, 20.0)
        self.temperature = _spin(290.0, 1.0, 370.0)
        self.flow = _spin(0.38, 0.01, 5.0, 3)
        self.heat = _spin(18.0, 0.0, 100.0)
        self.heat_shape = _combo(AXIAL_HEAT_SHAPES, "sinusoidal")
        self.heat_shape_parameter = _spin(0.0, -1.0, 1.0, 3)
        self.heat_shape_parameter.setToolTip(
            "Used by offset/skew profiles. Offset cosine is limited internally to +/-0.35 L."
        )
        self.power_factor = _spin(1.15, 0.1, 3.0, 3)
        self.flow_factor = _spin(1.0, 0.1, 2.0, 3)
        self.advanced_hot_factors_button = QtWidgets.QPushButton("Advanced axial nuclear-power factors...")
        self.localized_factor_status = QtWidgets.QLabel("No localized axial nuclear-power factors")
        self.length = _spin(3.66, 0.10, 10.0, 3)
        self.unheated_inlet = _spin(0.0, 0.0, 5.0, 3)
        self.unheated_outlet = _spin(0.0, 0.0, 5.0, 3)
        self.pitch_mm = _spin(12.60, 5.0, 30.0, 3)
        self.rod_od_mm = _spin(9.50, 2.0, 25.0, 3)
        self.clad_id_mm = _spin(8.36, 1.0, 24.0, 3)
        self.roughness_um = _spin(1.50, 0.0, 100.0, 3)
        self.inclination = _spin(90.0, -90.0, 90.0, 1)
        self.nodes = QtWidgets.QSpinBox()
        self.nodes.setRange(4, 200)
        self.nodes.setValue(30)

        self.friction = _combo(FRICTION_CORRELATIONS, "haaland")
        self.heat_transfer = _combo(HEAT_TRANSFER_CORRELATIONS, "gnielinski")
        self.boiling = _combo(BOILING_CORRELATIONS, "chen")
        self.chf_model = _combo(CHF_CORRELATIONS, "tong_w3")
        self.void_model = _combo(VOID_FRACTION_MODELS, "homogeneous")
        self.two_phase_friction = _combo(TWO_PHASE_FRICTION_MODELS, "homogeneous")
        self.cladding = _combo(CLADDING_MATERIALS, "zircaloy4")
        self.groeneveld_k1 = QtWidgets.QCheckBox("K1 diameter")
        self.groeneveld_k1.setChecked(True)
        self.groeneveld_k2 = QtWidgets.QCheckBox("K2 bundle geometry")
        self.groeneveld_k4 = QtWidgets.QCheckBox("K4 heated length")
        groeneveld_factors = QtWidgets.QWidget()
        factor_layout = QtWidgets.QVBoxLayout(groeneveld_factors)
        factor_layout.setContentsMargins(0, 0, 0, 0)
        factor_layout.addWidget(self.groeneveld_k1)
        factor_layout.addWidget(self.groeneveld_k2)
        factor_layout.addWidget(self.groeneveld_k4)

        self.samples = QtWidgets.QSpinBox()
        self.samples.setRange(10, 5000)
        self.samples.setValue(250)
        self.seed = QtWidgets.QSpinBox()
        self.seed.setRange(0, 2_000_000_000)
        self.seed.setValue(2026)
        self.deterministic_mode = QtWidgets.QRadioButton("Deterministic")
        self.statistical_mode = QtWidgets.QRadioButton("Statistical")
        self.deterministic_mode.setChecked(True)
        self.run_mode_group = QtWidgets.QButtonGroup(self)
        self.run_mode_group.setExclusive(True)
        self.run_mode_group.addButton(self.deterministic_mode)
        self.run_mode_group.addButton(self.statistical_mode)
        mode_widget = QtWidgets.QWidget()
        mode_layout = QtWidgets.QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(self.deterministic_mode)
        mode_layout.addWidget(self.statistical_mode)

        self._add_section(form, "BOUNDARY CONDITIONS / POWER", (
            ("Inlet pressure (MPa)", self.pressure),
            ("Inlet temperature (°C)", self.temperature),
            ("Mass flow (kg/s)", self.flow),
            ("Average linear heat (kW/m)", self.heat),
            ("Axial heat shape", self.heat_shape),
            ("Shape offset / skew", self.heat_shape_parameter),
            ("Hot-channel power factor", self.power_factor),
            ("Hot-channel flow factor", self.flow_factor),
            ("Localized power factors", self.advanced_hot_factors_button),
            ("Advanced status", self.localized_factor_status),
        ))
        self._add_section(form, "CHANNEL GEOMETRY", (
            ("Heated length (m)", self.length),
            ("Unheated inlet length (m)", self.unheated_inlet),
            ("Unheated outlet length (m)", self.unheated_outlet),
            ("Axial nodes", self.nodes),
            ("Pin pitch (mm)", self.pitch_mm),
            ("Rod outer diameter (mm)", self.rod_od_mm),
            ("Cladding inner diameter (mm)", self.clad_id_mm),
            ("Flow inclination (deg)", self.inclination),
            ("Surface roughness (µm)", self.roughness_um),
        ))
        self._add_section(form, "PHYSICS MODELS", (
            ("Friction correlation", self.friction),
            ("Heat-transfer correlation", self.heat_transfer),
            ("Nucleate-boiling correlation", self.boiling),
            ("CHF correlation", self.chf_model),
            ("Groeneveld corrections", groeneveld_factors),
            ("Void / slip model", self.void_model),
            ("Two-phase friction model", self.two_phase_friction),
            ("Cladding material", self.cladding),
        ))
        self._add_section(form, "ANALYSIS MODE", (
            ("Run mode", mode_widget),
            ("Random samples", self.samples),
            ("Random seed", self.seed),
        ))

        self.run_button = QtWidgets.QPushButton("Run selected mode")
        self.run_button.setObjectName("primaryAction")
        form.addRow(self.run_button)
        self.solution_button = QtWidgets.QPushButton("Open solution inspector")
        form.addRow(self.solution_button)
        self.export_button = QtWidgets.QPushButton("Export current channel CSV")
        form.addRow(self.export_button)
        self.channel_balance_summary = self._status("Channel balance: not calculated")
        form.addRow(self.channel_balance_summary)
        self.summary = self._status("")
        self.summary.setMinimumWidth(300)
        form.addRow(self.summary)

    @staticmethod
    def _add_section(form: QtWidgets.QFormLayout, title: str, rows) -> None:
        form.addRow(_section_label(title))
        for label, widget in rows:
            form.addRow(label, widget)

    @staticmethod
    def _status(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("statusPanel")
        label.setWordWrap(True)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        return label

    def scroll_area(self) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self)
        scroll.setMinimumWidth(280)
        return scroll
