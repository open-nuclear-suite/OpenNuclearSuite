"""Editor and scope matrix for localized axial nuclear-power factors."""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from .axial_heat_shapes import AXIAL_HEAT_SHAPES
from .localized_hot_factors import LOCAL_FACTOR_SHAPES, LocalizedPowerFactor
from .localized_hot_factors import combine_power_hot_factors


class HotFactorEditor(QtWidgets.QDialog):
    def __init__(self, owner) -> None:
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("User-defined localized axial nuclear power-distribution factors")
        self.setWindowFlag(QtCore.Qt.Window, True)
        self.setModal(False)
        self.resize(1120, 860)
        layout = QtWidgets.QVBoxLayout(self)
        explanation = QtWidgets.QLabel(
            "This editor changes only the axial nuclear power/linear-heat distribution. "
            "The channel-wide power factor remains on the main screen. Choose direct "
            "multiplication or independent-uncertainty RSS combination. The physical axial "
            "heat shape is not treated as an uncertainty. Location and width are fractions "
            "of heated length."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("statusPanel")
        layout.addWidget(explanation)
        scope_box = QtWidgets.QGroupBox("El-Wakil cause/effect coverage matrix")
        scope_layout = QtWidgets.QVBoxLayout(scope_box)
        legend = QtWidgets.QLabel(
            "Effects: <b>Fc</b> = bulk-coolant temperature/enthalpy rise; "
            "<b>Ff</b> = coolant-film temperature rise; "
            "<b>Fe</b> = fuel-element temperature rise. “Indirect” means the source is "
            "not mechanistically resolved."
        )
        legend.setWordWrap(True)
        scope_layout.addWidget(legend)
        coverage_rows = (
            ("Nuclear", "Neutron / power distribution", "Fc, Ff; Fe unavailable", "EDITABLE", "Global plus localized axial power"),
            ("Nuclear", "Fuel concentration, rods, material nonuniformity", "Fc, Ff, Fe", "INDIRECT", "User-entered power distribution only"),
            ("Engineering—mechanical", "Fuel-element warpage / bowing", "Fc, Ff", "FUTURE", "Needs local geometry and crossflow"),
            ("Engineering—mechanical", "Fuel/clad conductivity, gap, tolerances", "Fe", "PARTIAL", "Clad material and nominal dimensions only"),
            ("Engineering—distribution", "Coolant-flow distribution", "Fc, Ff", "PARTIAL", "Global flow factor; local flow deferred"),
            ("Engineering—distribution", "Heat-transfer coefficient uncertainty", "Ff", "PARTIAL", "Correlation selection; no h uncertainty"),
            ("Engineering—geometry", "Dimensions, roughness, spacers", "Fc, Ff, Fe", "PARTIAL", "Nominal geometry; tolerances deferred"),
            ("Modern extension", "Bias, covariance, radial/assembly mixing", "Depends", "FUTURE", "Requires uncertainty and subchannel stages"),
        )
        coverage = QtWidgets.QTableWidget(len(coverage_rows), 5)
        coverage.setHorizontalHeaderLabels(("Class", "Source/component", "Affected rise", "Status", "Present representation"))
        for row, values in enumerate(coverage_rows):
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                coverage.setItem(row, column, item)
        coverage.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        coverage.verticalHeader().setVisible(False)
        coverage.setAlternatingRowColors(True)
        coverage.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        coverage.setMinimumHeight(235)
        scope_layout.addWidget(coverage)
        layout.addWidget(scope_box)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels((
            "Enabled", "Location z/L", "Peak magnitude", "Width dZ/L", "Shape",
        ))
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table, 1)
        actions = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("Add factor")
        remove = QtWidgets.QPushButton("Remove selected")
        add.clicked.connect(self.add_default_factor)
        remove.clicked.connect(self.remove_selected)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addStretch(1)
        layout.addLayout(actions)
        mode_box = QtWidgets.QGroupBox("Power interpretation")
        mode_layout = QtWidgets.QVBoxLayout(mode_box)
        self.preserve = QtWidgets.QRadioButton(
            "Redistribute and renormalize - preserve requested total channel power"
        )
        self.add_power = QtWidgets.QRadioButton(
            "Additional power - localized factors also change total channel power"
        )
        mode_layout.addWidget(self.preserve)
        mode_layout.addWidget(self.add_power)
        layout.addWidget(mode_box)
        combination_box = QtWidgets.QGroupBox("Hot-factor combination")
        combination_layout = QtWidgets.QVBoxLayout(combination_box)
        self.multiplicative = QtWidgets.QRadioButton(
            "Multiplicative - Fhot(z) = Fpower x product[Fi(z)]"
        )
        self.statistical_rss = QtWidgets.QRadioButton(
            "Independent statistical RSS - Fhot(z) = 1 + sqrt(sum[(Fi(z) - 1)^2])"
        )
        combination_layout.addWidget(self.multiplicative)
        combination_layout.addWidget(self.statistical_rss)
        note = QtWidgets.QLabel(
            "RSS combines uncertainty allowances; it is separate from the Monte Carlo "
            "Statistical run mode. Deviations from 1.0 are treated as unsigned."
        )
        note.setWordWrap(True)
        combination_layout.addWidget(note)
        layout.addWidget(combination_box)
        self.summary = QtWidgets.QLabel()
        self.summary.setObjectName("statusPanel")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        bottom = QtWidgets.QHBoxLayout()
        apply_only = QtWidgets.QPushButton("Apply")
        apply_run = QtWidgets.QPushButton("Apply and run")
        apply_run.setObjectName("primaryAction")
        close = QtWidgets.QPushButton("Close")
        apply_only.clicked.connect(self.apply)
        apply_run.clicked.connect(self.apply_and_run)
        close.clicked.connect(self.close)
        bottom.addStretch(1)
        bottom.addWidget(apply_only)
        bottom.addWidget(apply_run)
        bottom.addWidget(close)
        layout.addLayout(bottom)
        self.load_from_owner()

    @staticmethod
    def _spin(value: float, minimum: float, maximum: float) -> QtWidgets.QDoubleSpinBox:
        widget = QtWidgets.QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(3)
        widget.setSingleStep(0.01)
        widget.setValue(value)
        return widget

    def add_factor(self, factor: LocalizedPowerFactor) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        enabled = QtWidgets.QCheckBox()
        enabled.setChecked(factor.enabled)
        enabled.setStyleSheet("margin-left:24px")
        self.table.setCellWidget(row, 0, enabled)
        self.table.setCellWidget(row, 1, self._spin(factor.location_fraction, 0.0, 1.0))
        self.table.setCellWidget(row, 2, self._spin(factor.magnitude, 0.1, 3.0))
        self.table.setCellWidget(row, 3, self._spin(factor.width_fraction, 0.001, 1.0))
        shape = QtWidgets.QComboBox()
        for key in LOCAL_FACTOR_SHAPES:
            shape.addItem(key.title(), key)
        shape.setCurrentIndex(shape.findData(factor.shape))
        self.table.setCellWidget(row, 4, shape)

    def add_default_factor(self) -> None:
        self.add_factor(LocalizedPowerFactor())

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def load_from_owner(self) -> None:
        self.table.setRowCount(0)
        for factor in self.owner.localized_power_factors:
            self.add_factor(factor)
        self.preserve.setChecked(self.owner.preserve_power_with_local_factors)
        self.add_power.setChecked(not self.owner.preserve_power_with_local_factors)
        method = self.owner.hot_factor_combination_method
        self.multiplicative.setChecked(method == "multiplicative")
        self.statistical_rss.setChecked(method == "statistical_rss")
        self._update_summary()

    def factors(self) -> tuple[LocalizedPowerFactor, ...]:
        return tuple(LocalizedPowerFactor(
            location_fraction=self.table.cellWidget(row, 1).value(),
            magnitude=self.table.cellWidget(row, 2).value(),
            width_fraction=self.table.cellWidget(row, 3).value(),
            shape=str(self.table.cellWidget(row, 4).currentData()),
            enabled=self.table.cellWidget(row, 0).isChecked(),
        ) for row in range(self.table.rowCount()))

    def _update_summary(self) -> None:
        enabled = [factor for factor in self.owner.localized_power_factors if factor.enabled]
        mode = "renormalized redistribution" if self.owner.preserve_power_with_local_factors else "additional power"
        method = self.owner.hot_factor_combination_method
        geometry = self.owner._geometry()
        dz = geometry.heated_length_m / geometry.node_count
        z = (np.arange(geometry.node_count, dtype=float) + 0.5) * dz
        base = AXIAL_HEAT_SHAPES[str(self.owner.heat_shape.currentData())].evaluate(
            z, geometry.heated_length_m, self.owner.heat_shape_parameter.value()
        )
        local, hot = combine_power_hot_factors(
            z, geometry.heated_length_m, self.owner.localized_power_factors,
            self.owner.power_factor.value(), method,
        )
        raw_overall = base * hot
        normalization = (
            self.owner.power_factor.value() / np.mean(raw_overall)
            if self.owner.preserve_power_with_local_factors else 1.0
        )
        overall = raw_overall * normalization
        peak_index = int(np.argmax(overall))
        formula = (
            "Fpower x product[Fi(z)]" if method == "multiplicative"
            else "1 + sqrt((Fpower-1)^2 + sum[(Fi(z)-1)^2])"
        )
        self.summary.setText(
            f"Hot-factor rule: Fhot(z) = {formula}<br>"
            f"Combined axial factor: Foverall(z) = Fshape(z) x Fhot(z)<br>"
            f"Fpower={self.owner.power_factor.value():.4g}; normalization={normalization:.4g}; "
            f"peak Foverall={overall[peak_index]:.4g} at z/L={z[peak_index] / geometry.heated_length_m:.4g}.<br>"
            f"Peak localized contribution={np.max(local):.4g}; active localized factors: "
            f"{len(enabled)}; interpretation: {mode}."
        )

    @QtCore.Slot()
    def apply(self) -> None:
        self.owner.localized_power_factors = self.factors()
        self.owner.preserve_power_with_local_factors = self.preserve.isChecked()
        self.owner.hot_factor_combination_method = (
            "statistical_rss" if self.statistical_rss.isChecked() else "multiplicative"
        )
        self._update_summary()
        count = sum(factor.enabled for factor in self.owner.localized_power_factors)
        method = "RSS" if self.owner.hot_factor_combination_method == "statistical_rss" else "multiplicative"
        self.owner.localized_factor_status.setText(
            f"{count} active localized axial nuclear-power factor(s) - {method}"
        )

    @QtCore.Slot()
    def apply_and_run(self) -> None:
        self.apply()
        self.owner.run_selected_mode()
