"""Linked, modeless step-by-step solution inspector."""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from .inspector_pages import render_inspector_pages


class SolutionInspector(QtWidgets.QDialog):
    """A non-modal view onto the main window's single shared case state."""

    def __init__(self, owner) -> None:
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Subchannel Solution Inspector")
        self.setWindowFlag(QtCore.Qt.Window, True)
        self.setModal(False)
        self.resize(1040, 760)
        self.previous_values: dict[str, float] | None = None
        self._linked_controls: list[tuple[QtWidgets.QWidget, QtWidgets.QWidget]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("SOLUTION INSPECTOR — LINKED CASE")
        title.setObjectName("suiteTitle")
        self.pending = QtWidgets.QLabel("SYNCHRONIZED")
        self.pending.setStyleSheet("color:#55ff9a;font-weight:700")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.pending)
        root.addLayout(title_row)

        self.scope_banner = QtWidgets.QLabel(
            "NODE-LOCAL SOLUTION: Select a node below. Rows marked CHANNEL TOTAL or OUTLET "
            "are whole-channel reference values."
        )
        self.scope_banner.setObjectName("statusPanel")
        self.scope_banner.setWordWrap(True)
        self.scope_banner.setStyleSheet(
            "QLabel{background:#102638;border:1px solid #35b6ff;"
            "padding:7px;color:#ffffff;font-weight:600;}"
        )
        root.addWidget(self.scope_banner)

        case_box = QtWidgets.QGroupBox("LINKED CASE CONTROLS")
        grid = QtWidgets.QGridLayout(case_box)
        self._add_double(grid, 0, "Pressure (MPa)", self.owner.pressure)
        self._add_double(grid, 1, "Inlet temperature (°C)", self.owner.temperature)
        self._add_double(grid, 2, "Mass flow (kg/s)", self.owner.flow)
        self._add_double(grid, 3, "Linear heat (kW/m)", self.owner.heat)
        self._add_double(grid, 4, "Power factor", self.owner.power_factor)
        self._add_double(grid, 5, "Flow factor", self.owner.flow_factor)
        grid.addWidget(QtWidgets.QLabel("Run mode"), 2, 0)
        self.mode = QtWidgets.QComboBox()
        self.mode.addItem("Deterministic", "deterministic")
        self.mode.addItem("Statistical", "statistical")
        self.mode.currentIndexChanged.connect(self._push_mode)
        grid.addWidget(self.mode, 2, 1)
        self.run_button = QtWidgets.QPushButton("RUN LINKED CASE")
        self.run_button.setObjectName("primaryAction")
        self.run_button.clicked.connect(self.run_linked_case)
        grid.addWidget(self.run_button, 2, 2, 1, 3)
        root.addWidget(case_box)

        node_row = QtWidgets.QHBoxLayout()
        previous = QtWidgets.QPushButton("◀ Previous node")
        following = QtWidgets.QPushButton("Next node ▶")
        previous.clicked.connect(lambda: self._step_node(-1))
        following.clicked.connect(lambda: self._step_node(1))
        self.node_label = QtWidgets.QLabel()
        self.node_label.setObjectName("statusPanel")
        node_row.addWidget(previous)
        node_row.addWidget(following)
        node_row.addWidget(self.node_label, 1)
        root.addLayout(node_row)

        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)
        self.pages: dict[str, QtWidgets.QTextBrowser] = {}
        self._add_geometry_tab()
        self._add_text_tab("Properties")
        self._add_flow_tab()
        self._add_heat_tab()
        self._add_text_tab("Quality / Void")
        self._add_text_tab("Pressure Drop")
        self._add_chf_tab()
        self._add_statistics_tab()
        self.tabs.setToolTip(
            "Most result tabs show the selected axial node. Geometry and Statistics are case-wide; "
            "channel totals and outlet values are explicitly labelled."
        )

    def _text_browser(self) -> QtWidgets.QTextBrowser:
        browser = QtWidgets.QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(
            "QTextBrowser{background:#0f171e;border:1px solid #435461;padding:10px;}"
        )
        return browser

    def _add_text_tab(self, name: str) -> None:
        browser = self._text_browser()
        self.pages[name] = browser
        self.tabs.addTab(browser, name)

    def _tab_with_controls(self, name: str) -> tuple[QtWidgets.QWidget, QtWidgets.QFormLayout]:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        controls = QtWidgets.QGroupBox(f"{name.upper()} INPUTS")
        form = QtWidgets.QFormLayout(controls)
        layout.addWidget(controls)
        browser = self._text_browser()
        layout.addWidget(browser, 1)
        self.pages[name] = browser
        self.tabs.addTab(page, name)
        return page, form

    def _add_geometry_tab(self) -> None:
        _page, form = self._tab_with_controls("Geometry")
        for label, source in (
            ("Heated length (m)", self.owner.length),
            ("Unheated inlet (m)", self.owner.unheated_inlet),
            ("Unheated outlet (m)", self.owner.unheated_outlet),
            ("Pin pitch (mm)", self.owner.pitch_mm),
            ("Rod OD (mm)", self.owner.rod_od_mm),
            ("Clad ID (mm)", self.owner.clad_id_mm),
            ("Roughness (µm)", self.owner.roughness_um),
        ):
            form.addRow(label, self._linked_double(source))
        form.addRow("Axial nodes", self._linked_integer(self.owner.nodes))

    def _add_flow_tab(self) -> None:
        _page, form = self._tab_with_controls("Flow")
        form.addRow("Friction correlation", self._linked_combo(self.owner.friction))
        form.addRow("Void / slip model", self._linked_combo(self.owner.void_model))
        form.addRow("Two-phase friction model", self._linked_combo(self.owner.two_phase_friction))
        form.addRow("Flow inclination (deg)", self._linked_double(self.owner.inclination))

    def _add_heat_tab(self) -> None:
        _page, form = self._tab_with_controls("Heat Transfer")
        form.addRow("Axial heat shape", self._linked_combo(self.owner.heat_shape))
        form.addRow("Shape offset / skew", self._linked_double(self.owner.heat_shape_parameter))
        form.addRow("Single-phase correlation", self._linked_combo(self.owner.heat_transfer))
        form.addRow("Boiling correlation", self._linked_combo(self.owner.boiling))
        form.addRow("Cladding material", self._linked_combo(self.owner.cladding))

    def _add_chf_tab(self) -> None:
        _page, form = self._tab_with_controls("CHF / Margin")
        form.addRow("Selected CHF correlation", self._linked_combo(self.owner.chf_model))
        form.addRow("Groeneveld K1 diameter", self._linked_check(self.owner.groeneveld_k1))
        form.addRow("Groeneveld K2 bundle", self._linked_check(self.owner.groeneveld_k2))
        form.addRow("Groeneveld K4 heated length", self._linked_check(self.owner.groeneveld_k4))

    def _add_statistics_tab(self) -> None:
        _page, form = self._tab_with_controls("Statistics")
        form.addRow("Samples", self._linked_integer(self.owner.samples))
        form.addRow("Random seed", self._linked_integer(self.owner.seed))

    def _add_double(self, grid: QtWidgets.QGridLayout, column: int, label: str, source) -> None:
        row = 0 if column < 3 else 1
        col = (column % 3) * 2
        grid.addWidget(QtWidgets.QLabel(label), row, col)
        grid.addWidget(self._linked_double(source), row, col + 1)

    def _linked_double(self, source) -> QtWidgets.QDoubleSpinBox:
        target = QtWidgets.QDoubleSpinBox()
        target.setRange(source.minimum(), source.maximum())
        target.setDecimals(source.decimals())
        target.setSingleStep(source.singleStep())
        target.setValue(source.value())
        target.valueChanged.connect(lambda value, widget=source: self._push_value(widget, value))
        source.valueChanged.connect(lambda value, widget=target: self._pull_value(widget, value))
        self._linked_controls.append((source, target))
        return target

    def _linked_integer(self, source) -> QtWidgets.QSpinBox:
        target = QtWidgets.QSpinBox()
        target.setRange(source.minimum(), source.maximum())
        target.setSingleStep(source.singleStep())
        target.setValue(source.value())
        target.valueChanged.connect(lambda value, widget=source: self._push_value(widget, value))
        source.valueChanged.connect(lambda value, widget=target: self._pull_value(widget, value))
        self._linked_controls.append((source, target))
        return target

    def _linked_combo(self, source) -> QtWidgets.QComboBox:
        target = QtWidgets.QComboBox()
        for index in range(source.count()):
            target.addItem(source.itemText(index), source.itemData(index))
        target.setCurrentIndex(source.currentIndex())
        target.currentIndexChanged.connect(
            lambda index, widget=source: self._push_combo(widget, index)
        )
        source.currentIndexChanged.connect(
            lambda index, widget=target: self._pull_combo(widget, index)
        )
        self._linked_controls.append((source, target))
        return target

    def _linked_check(self, source) -> QtWidgets.QCheckBox:
        target = QtWidgets.QCheckBox()
        target.setChecked(source.isChecked())
        target.toggled.connect(lambda checked, widget=source: self._push_check(widget, checked))
        source.toggled.connect(lambda checked, widget=target: self._pull_check(widget, checked))
        self._linked_controls.append((source, target))
        return target

    def _push_value(self, source, value) -> None:
        with QtCore.QSignalBlocker(source):
            source.setValue(value)
        self._mark_pending()

    def _pull_value(self, target, value) -> None:
        with QtCore.QSignalBlocker(target):
            target.setValue(value)
        self._mark_pending()

    def _push_combo(self, source, index: int) -> None:
        with QtCore.QSignalBlocker(source):
            source.setCurrentIndex(index)
        self._mark_pending()

    def _pull_combo(self, target, index: int) -> None:
        with QtCore.QSignalBlocker(target):
            target.setCurrentIndex(index)
        self._mark_pending()

    def _push_check(self, source, checked: bool) -> None:
        with QtCore.QSignalBlocker(source):
            source.setChecked(checked)
        self._mark_pending()

    def _pull_check(self, target, checked: bool) -> None:
        with QtCore.QSignalBlocker(target):
            target.setChecked(checked)
        self._mark_pending()

    def _push_mode(self) -> None:
        statistical = self.mode.currentData() == "statistical"
        with QtCore.QSignalBlocker(self.owner.statistical_mode), QtCore.QSignalBlocker(
            self.owner.deterministic_mode
        ):
            self.owner.statistical_mode.setChecked(statistical)
            self.owner.deterministic_mode.setChecked(not statistical)
        self.owner._update_run_mode_controls()
        self._mark_pending()

    def sync_mode_from_main(self) -> None:
        index = 1 if self.owner.statistical_mode.isChecked() else 0
        with QtCore.QSignalBlocker(self.mode):
            self.mode.setCurrentIndex(index)

    def _mark_pending(self) -> None:
        self.pending.setText("MODIFIED — RUN REQUIRED")
        self.pending.setStyleSheet("color:#ffbf3f;font-weight:700")

    def _snapshot(self) -> dict[str, float] | None:
        result = self.owner.current_result
        if result is None:
            return None
        i = min(self.owner.selected_node, result.z_m.size - 1)
        return {
            "Wall temperature": float(result.wall_temperature_C[i]),
            "Reynolds number": float(result.reynolds[i]),
            "Pressure drop": float(result.cumulative_pressure_drop_kpa[i]),
            "DNBR": float(result.dnbr[i]),
        }

    @QtCore.Slot()
    def run_linked_case(self) -> None:
        self.previous_values = self._snapshot()
        self.owner.run_selected_mode()
        self.pending.setText("SYNCHRONIZED")
        self.pending.setStyleSheet("color:#55ff9a;font-weight:700")
        self.refresh()

    def _step_node(self, step: int) -> None:
        result = self.owner.current_result
        if result is None:
            return
        node = max(0, min(self.owner.selected_node + step, result.z_m.size - 1))
        self.owner.node_selector.setValue(node + 1)
        self.refresh()

    def refresh(self) -> None:
        self.sync_mode_from_main()
        result = self.owner.current_result
        if result is None:
            for browser in self.pages.values():
                browser.setHtml("<h3>No calculation is available.</h3>")
            return
        i = min(self.owner.selected_node, result.z_m.size - 1)
        self.scope_banner.setText(
            f"NODE-LOCAL SOLUTION: Result tabs currently refer to axial node {i + 1} "
            f"at z = {result.z_m[i]:.4f} m. Rows marked CHANNEL TOTAL or OUTLET are "
            "whole-channel reference values. Geometry and Statistics describe the whole case."
        )
        self.node_label.setText(
            f"Node {i + 1}/{result.z_m.size} · z={result.z_m[i]:.4f} m · "
            f"{result.flow_regime[i]} · wall model: {result.wall_heat_transfer_mode[i]}"
        )
        geometry = self.owner._geometry()
        rendered_pages = render_inspector_pages(
            result,
            geometry,
            i,
            statistical=self.owner.statistical_mode.isChecked(),
            samples=self.owner.samples.value(),
            seed=self.owner.seed.value(),
        )
        for name, html in rendered_pages.items():
            self.pages[name].setHtml(html)
        if self.previous_values:
            current = self._snapshot() or {}
            deltas = []
            for name, previous in self.previous_values.items():
                value = current.get(name, float("nan"))
                if np.isfinite(value) and np.isfinite(previous):
                    deltas.append(f"{name}: {value-previous:+.5g}")
            if deltas:
                self.node_label.setText(self.node_label.text() + " · Δ " + "; ".join(deltas))
