"""PySide6/PyQtGraph interface for the first subchannel laboratory chunk."""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from .control_panel import EXPORTED_CONTROLS, SubchannelControlPanel
from .csv_export import write_channel_result_csv
from .materials import CLADDING_MATERIALS
from .pyqtgraph_handler import PyQtGraphHandler
from .single_channel import (
    ChannelGeometry,
    ChannelInputs,
    SingleChannelModel,
    StatisticalSettings,
    run_statistical_hot_channel,
)
from .void_models import VOID_FRACTION_MODELS
from .two_phase_friction import TWO_PHASE_FRICTION_MODELS
from .axial_heat_shapes import AXIAL_HEAT_SHAPES
from .plot_workspace import AnalysisPlotWorkspace
from .branding import APPLICATION_NAME, SUITE_NAME, SUITE_VERSION, show_about_dialog
from .neighboring_channels import (
    CHANNEL_LABELS,
    CommonPlenumChannelModel,
    ParallelChannelSetting,
)


def _node_ranges(labels: tuple[str, ...]) -> str:
    """Compact consecutive node labels for the status panel."""
    if not labels:
        return ""
    groups: list[str] = []
    start = 0
    for index in range(1, len(labels) + 1):
        if index == len(labels) or labels[index] != labels[start]:
            node_range = str(start + 1) if index == start + 1 else f"{start + 1}-{index}"
            groups.append(f"{labels[start]}: nodes {node_range}")
            start = index
    return "; ".join(groups)


class SubchannelLaboratoryWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APPLICATION_NAME} — v{SUITE_VERSION}")
        self.resize(1500, 900)
        self.model = SingleChannelModel()
        self.four_channel_model = CommonPlenumChannelModel(self.model)
        self.graphs = PyQtGraphHandler()
        self.current_result = None
        self.current_four_channel_result = None
        self.selected_channel = 4
        self.selected_node = 0
        self.solution_inspector = None
        self.hot_factor_editor = None
        self.localized_power_factors = ()
        self.preserve_power_with_local_factors = True
        self.hot_factor_combination_method = "multiplicative"
        self._build_ui()
        self.run_case()

    def _build_ui(self) -> None:
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)
        header = QtWidgets.QHBoxLayout()
        heading = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel(APPLICATION_NAME.upper())
        title.setObjectName("suiteTitle")
        subtitle = QtWidgets.QLabel(f"{SUITE_NAME.upper()}  ·  VERSION {SUITE_VERSION}")
        subtitle.setObjectName("suiteSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch(1)
        about_button = QtWidgets.QPushButton("ABOUT")
        about_button.setToolTip("About this simulator and its intended use")
        about_button.clicked.connect(self.show_about)
        header.addWidget(about_button, 0, QtCore.Qt.AlignTop)
        outer.addLayout(header)
        body = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        outer.addWidget(body, 1)
        self.control_panel = SubchannelControlPanel()
        for name in EXPORTED_CONTROLS:
            setattr(self, name, getattr(self.control_panel, name))
        self.run_button.clicked.connect(self.run_selected_mode)
        self.solution_button.clicked.connect(self.open_solution_inspector)
        self.export_button.clicked.connect(self.export_current_csv)
        self.advanced_hot_factors_button.clicked.connect(self.open_hot_factor_editor)
        self.deterministic_mode.toggled.connect(self._update_run_mode_controls)
        self.statistical_mode.toggled.connect(self._update_run_mode_controls)
        self.progression.currentIndexChanged.connect(self._progression_changed)
        self.channel_selector.currentIndexChanged.connect(self._selected_channel_changed)
        self.channel_map_group.idClicked.connect(self.channel_selector.setCurrentIndex)
        for control in self.channel_power_factors:
            control.valueChanged.connect(self._four_channel_input_changed)
        self._update_run_mode_controls()

        self.workspace_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(7)
        self.workspace_splitter.addWidget(self.control_panel.scroll_area())

        self.plot_workspace = AnalysisPlotWorkspace(self.graphs)
        self.analysis_tabs = self.plot_workspace.tabs
        self.selected_node_strip = self.plot_workspace.selected_node_strip
        for name in (
            "temperature_plot", "heat_profile_plot", "margin_plot", "phase_plot",
            "pressure_drop_plot", "hydraulic_local_plot", "histogram",
            "wall_temperature_histogram", "axial_plots", "axial_cursors",
        ):
            setattr(self, name, getattr(self.plot_workspace, name))
        self.workspace_splitter.addWidget(self.plot_workspace)
        self.workspace_splitter.setStretchFactor(0, 0)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setSizes([410, 760])
        layout.addWidget(self.workspace_splitter, 1)
        self._build_geometry_dock()
        for plot in self.axial_plots:
            plot.scene().sigMouseClicked.connect(
                lambda event, source=plot: self._axial_plot_clicked(source, event)
            )
        self.update_illustration()

    @QtCore.Slot()
    def _progression_changed(self) -> None:
        stage = str(self.progression.currentData())
        four = stage == "neswc_independent"
        self.four_channel_box.setVisible(four)
        self.statistical_mode.setEnabled(not four)
        if four and self.statistical_mode.isChecked():
            self.deterministic_mode.setChecked(True)
        self.progression_note.setText(
            "The original center channel plus north, east, south, and west parallel paths. "
            "Total flow is conserved and redistributed to a common pressure drop; "
            "there is no axial crossflow or turbulent mixing."
            if four else
            "Single axial channel. Start here for conservation, boiling, CHF, and DNBR."
        )
        flow_factor_label = self.control_panel.layout().labelForField(self.flow_factor)
        flow_label = self.control_panel.layout().labelForField(self.flow)
        if flow_factor_label is not None:
            flow_factor_label.setText("Total-flow factor" if four else "Hot-channel flow factor")
        if flow_label is not None:
            flow_label.setText("Nominal channel flow (kg/s)" if four else "Mass flow (kg/s)")
        self.run_case()

    @QtCore.Slot()
    def _selected_channel_changed(self) -> None:
        self.selected_channel = int(self.channel_selector.currentData())
        self.channel_map_buttons[self.selected_channel].setChecked(True)
        if self.current_four_channel_result is not None:
            self.current_result = self.current_four_channel_result.channels[self.selected_channel]
            self.plot_workspace.update_four_channel(
                self.current_four_channel_result, self.selected_channel
            )
            self._present_current_result()

    @QtCore.Slot()
    def _four_channel_input_changed(self) -> None:
        if str(self.progression.currentData()) == "neswc_independent":
            self.run_case()

    def _four_channel_settings(self) -> tuple[ParallelChannelSetting, ...]:
        return tuple(
            ParallelChannelSetting(label, power.value())
            for label, power in zip(CHANNEL_LABELS, self.channel_power_factors)
        )

    def _build_geometry_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Channel geometry and 3-D inspection", self)
        dock.setObjectName("channel_geometry_dock")
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        # Reparenting an active QOpenGLWidget by floating or closing its dock can
        # invalidate the native context on some Windows drivers. Keep the pane
        # movable and resizable but remove those unsafe title-bar actions.
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        self.illustration = self.graphs.subchannel_3d_view()
        layout.addWidget(self.illustration, 1)
        views = QtWidgets.QHBoxLayout()
        for label, elevation, azimuth in (
            ("Isometric", 18.0, 35.0),
            ("Top", 89.5, 0.0),
            ("Front", 0.0, -90.0),
            ("Side", 0.0, 0.0),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, e=elevation, a=azimuth: self._set_geometry_view(e, a)
            )
            views.addWidget(button)
        layout.addLayout(views)
        instruction = QtWidgets.QLabel(
            "Left-drag to orbit; right/middle-drag or Shift+left-drag to pan; "
            "mouse wheel to zoom. Use the preset views for precise inspection. "
            "The node selector moves the red inspection plane."
        )
        instruction.setWordWrap(True)
        layout.addWidget(instruction)
        self.node_selector = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.node_selector.setRange(1, self.nodes.value())
        self.node_selector.setValue(1)
        self.node_selector.valueChanged.connect(self._node_selector_changed)
        layout.addWidget(self.node_selector)
        self.geometry_info = QtWidgets.QLabel()
        self.geometry_info.setObjectName("statusPanel")
        self.geometry_info.setWordWrap(True)
        self.geometry_info.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.geometry_info)
        self.node_inspector = QtWidgets.QLabel("Select an axial plot location or use the node slider.")
        self.node_inspector.setObjectName("statusPanel")
        self.node_inspector.setWordWrap(True)
        self.node_inspector.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.node_inspector)
        dock.setWidget(content)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.geometry_dock = dock
        self.cladding.currentIndexChanged.connect(self.update_illustration)
        for control in (
            self.length, self.unheated_inlet, self.unheated_outlet, self.pitch_mm,
            self.rod_od_mm, self.clad_id_mm, self.roughness_um, self.nodes,
        ):
            control.valueChanged.connect(self._geometry_changed)

    def _set_geometry_view(self, elevation: float, azimuth: float) -> None:
        self.illustration.setCameraPosition(elevation=elevation, azimuth=azimuth)
        self.illustration.update()

    @QtCore.Slot()
    def _geometry_changed(self) -> None:
        self.node_selector.setMaximum(self.nodes.value())
        self.selected_node = min(self.selected_node, self.nodes.value() - 1)
        self.node_selector.setValue(self.selected_node + 1)
        self.update_illustration()

    @QtCore.Slot(int)
    def _node_selector_changed(self, node_number: int) -> None:
        self.selected_node = node_number - 1
        self._update_node_inspector()
        self.update_illustration()

    @QtCore.Slot()
    def update_illustration(self) -> None:
        try:
            geometry = self._geometry()
        except ValueError:
            return
        material = CLADDING_MATERIALS[str(self.cladding.currentData())]
        four_stage = (
            str(self.progression.currentData()) == "neswc_independent"
            and self.current_four_channel_result is not None
        )
        if four_stage:
            bundle = self.current_four_channel_result
            self.graphs.set_neswc_channels_3d(
                self.illustration, geometry.rod_pitch_m, geometry.rod_outer_diameter_m,
                geometry.heated_length_m, geometry.unheated_inlet_length_m,
                geometry.unheated_outlet_length_m, geometry.node_count, material.color,
                regimes=tuple(channel.flow_regime for channel in bundle.channels),
                selected_channel=self.selected_channel,
                limiting_channel=bundle.limiting_channel_index,
                selected_node=self.selected_node,
            )
        else:
            regimes = None if self.current_result is None else self.current_result.flow_regime
            self.graphs.set_four_pin_subchannel_3d(
                self.illustration, geometry.rod_pitch_m, geometry.rod_outer_diameter_m,
                geometry.heated_length_m, geometry.unheated_inlet_length_m,
                geometry.unheated_outlet_length_m, geometry.node_count, material.color,
                regimes=regimes, selected_node=self.selected_node,
            )
        self.geometry_info.setText(
            f"Total channel length: {geometry.total_channel_length_m:.3f} m<br>"
            f"Heated length: {geometry.heated_length_m:.3f} m<br>"
            f"Unheated inlet / outlet: {geometry.unheated_inlet_length_m:.3f} / "
            f"{geometry.unheated_outlet_length_m:.3f} m<br>"
            f"Pitch / rod OD / clad ID: {geometry.rod_pitch_m * 1000:.3f} / "
            f"{geometry.rod_outer_diameter_m * 1000:.3f} / "
            f"{geometry.clad_inner_diameter_m * 1000:.3f} mm<br>"
            f"Flow area: {geometry.flow_area_m2 * 1e6:.3f} mm²<br>"
            f"Wetted perimeter: {geometry.wetted_perimeter_m * 1000:.3f} mm<br>"
            f"Hydraulic diameter: {geometry.hydraulic_diameter_m * 1000:.3f} mm<br>"
            f"Relative roughness: {geometry.roughness_m / geometry.hydraulic_diameter_m:.3g}<br>"
            + (
                "The center channel and its N/E/S/W parallel neighbors are shown. "
                "Cyan marks the selected channel; red marks the limiting channel. "
                "Flows satisfy a common-plenum pressure balance; axial crossflow is not solved."
                if four_stage else
                "Current conservation and pressure-drop solution spans the heated section."
            )
        )

    def _geometry(self) -> ChannelGeometry:
        return ChannelGeometry(
            node_count=self.nodes.value(),
            heated_length_m=self.length.value(),
            unheated_inlet_length_m=self.unheated_inlet.value(),
            unheated_outlet_length_m=self.unheated_outlet.value(),
            rod_outer_diameter_m=self.rod_od_mm.value() / 1000.0,
            clad_inner_diameter_m=self.clad_id_mm.value() / 1000.0,
            rod_pitch_m=self.pitch_mm.value() / 1000.0,
            roughness_m=self.roughness_um.value() / 1.0e6,
        )

    def _axial_plot_clicked(self, plot, event) -> None:
        if self.current_result is None or not plot.sceneBoundingRect().contains(event.scenePos()):
            return
        position = plot.getPlotItem().vb.mapSceneToView(event.scenePos())
        self.selected_node = int(np.argmin(np.abs(self.current_result.z_m - position.x())))
        self.node_selector.setValue(self.selected_node + 1)
        self._update_node_inspector()
        self.update_illustration()

    def _update_node_inspector(self) -> None:
        result = self.current_result
        if result is None:
            return
        i = min(self.selected_node, result.z_m.size - 1)
        dnbr = "unavailable" if not np.isfinite(result.dnbr[i]) else f"{result.dnbr[i]:.3f}"
        self.plot_workspace.set_node_summary(result, i, dnbr)
        self.plot_workspace.set_axial_cursor(float(result.z_m[i]))
        self.node_inspector.setText(
            f"Node {i + 1} at z={result.z_m[i]:.3f} m<br>"
            f"Regime: {result.flow_regime[i]}<br>"
            f"Node ΔP total: {result.node_pressure_drop_kpa[i]:.3f} kPa "
            f"(f/g/a = {result.friction_pressure_drop_kpa[i]:.3f} / "
            f"{result.gravity_pressure_drop_kpa[i]:.3f} / "
            f"{result.acceleration_pressure_drop_kpa[i]:.3f})<br>"
            f"Total heated-channel pressure drop: {result.total_heated_pressure_drop_kpa:.2f} kPa<br>"
            f"Wall model: {result.wall_heat_transfer_mode[i]}<br>"
            f"Tbulk/Twall: {result.bulk_temperature_C[i]:.2f}/{result.wall_temperature_C[i]:.2f} °C<br>"
            f"G={result.mass_flux_kg_m2_s[i]:.1f} kg/m²·s; v={result.velocity_m_s[i]:.2f} m/s<br>"
            f"Void model: {VOID_FRACTION_MODELS[str(self.void_model.currentData())].label}; "
            f"S={result.slip_ratio[i]:.3f}; valid={'yes' if result.void_model_valid[i] else 'no'}<br>"
            f"Two-phase friction: "
            f"{TWO_PHASE_FRICTION_MODELS[str(self.two_phase_friction.currentData())].label}; "
            f"multiplier={result.two_phase_friction_multiplier[i]:.3f}; "
            f"valid={'yes' if result.two_phase_friction_valid[i] else 'no'}<br>"
            + (f"Interpolation: {result.two_phase_friction_detail[i]}<br>" if result.two_phase_friction_detail[i] else "")
            + f"Liquid/vapor velocity: {result.liquid_velocity_m_s[i]:.3f} / "
            f"{result.vapor_velocity_m_s[i]:.3f} m/s<br>"
            f"Re={result.reynolds[i]:.3g}; Pr={result.prandtl[i]:.3g}; Nu={result.nusselt[i]:.3g}<br>"
            f"μ={result.viscosity_Pa_s[i]:.3e} Pa·s; "
            f"k={result.conductivity_W_mK[i]:.4f} W/m·K; "
            f"σ={result.surface_tension_N_m[i]:.4f} N/m<br>"
            f"f={result.friction_factor[i]:.5f}; ΔPcum={result.cumulative_pressure_drop_kpa[i]:.2f} kPa<br>"
            f"xₑ={result.equilibrium_quality[i]:.4f}; α={result.void_fraction[i]:.4f}; DNBR={dnbr}"
        )

        if self.solution_inspector is not None and self.solution_inspector.isVisible():
            self.solution_inspector.refresh()

    def _inputs(self) -> ChannelInputs:
        return ChannelInputs(
            inlet_pressure_mpa=self.pressure.value(),
            inlet_temperature_C=self.temperature.value(),
            mass_flow_kg_s=self.flow.value(),
            average_linear_heat_W_m=self.heat.value() * 1000.0,
            power_factor=self.power_factor.value(),
            flow_factor=self.flow_factor.value(),
            friction_key=str(self.friction.currentData()),
            heat_transfer_key=str(self.heat_transfer.currentData()),
            boiling_key=str(self.boiling.currentData()),
            chf_key=str(self.chf_model.currentData()),
            groeneveld_k1=self.groeneveld_k1.isChecked(),
            groeneveld_k2=self.groeneveld_k2.isChecked(),
            groeneveld_k4=self.groeneveld_k4.isChecked(),
            cladding_key=str(self.cladding.currentData()),
            inclination_degrees=self.inclination.value(),
            void_model_key=str(self.void_model.currentData()),
            two_phase_friction_key=str(self.two_phase_friction.currentData()),
            heat_shape_key=str(self.heat_shape.currentData()),
            heat_shape_parameter=self.heat_shape_parameter.value(),
            localized_power_factors=self.localized_power_factors,
            preserve_power_with_local_factors=self.preserve_power_with_local_factors,
            hot_factor_combination_method=self.hot_factor_combination_method,
        )

    @QtCore.Slot()
    def _update_run_mode_controls(self) -> None:
        statistical = self.statistical_mode.isChecked()
        self.samples.setEnabled(statistical)
        self.seed.setEnabled(statistical)
        if self.solution_inspector is not None:
            self.solution_inspector.sync_mode_from_main()

    @QtCore.Slot()
    def run_selected_mode(self) -> None:
        if self.statistical_mode.isChecked():
            self.run_statistics()
        else:
            self.plot_workspace.clear_statistics()
            self.run_case()

    def _rebuild_axial_cursors(self) -> None:
        if self.current_result is None:
            return
        position = float(self.current_result.z_m[self.selected_node])
        self.plot_workspace.rebuild_axial_cursors(position)

    @QtCore.Slot()
    def open_solution_inspector(self) -> None:
        if self.solution_inspector is None:
            from .solution_inspector import SolutionInspector

            self.solution_inspector = SolutionInspector(self)
        self.solution_inspector.refresh()
        self.solution_inspector.show()
        self.solution_inspector.raise_()
        self.solution_inspector.activateWindow()

    @QtCore.Slot()
    def open_hot_factor_editor(self) -> None:
        if self.hot_factor_editor is None:
            from .hot_factor_editor import HotFactorEditor

            self.hot_factor_editor = HotFactorEditor(self)
        else:
            self.hot_factor_editor.load_from_owner()
        self.hot_factor_editor.show()
        self.hot_factor_editor.raise_()
        self.hot_factor_editor.activateWindow()

    @QtCore.Slot()
    def show_about(self) -> None:
        show_about_dialog(self)

    @QtCore.Slot()
    def export_current_csv(self) -> None:
        if self.current_result is None:
            QtWidgets.QMessageBox.information(self, "CSV export", "Run a channel case first.")
            return
        destination, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export current channel result", "subchannel_result.csv",
            "CSV files (*.csv)",
        )
        if not destination:
            return
        if not destination.lower().endswith(".csv"):
            destination += ".csv"
        try:
            write_channel_result_csv(destination, self.current_result)
        except OSError as error:
            QtWidgets.QMessageBox.critical(self, "CSV export failed", str(error))
            return
        QtWidgets.QMessageBox.information(
            self, "CSV export complete", f"Saved {self.current_result.z_m.size} axial nodes to:\n{destination}"
        )

    @QtCore.Slot()
    def run_case(self) -> None:
        try:
            geometry = self._geometry()
            if str(self.progression.currentData()) == "neswc_independent":
                bundle = self.four_channel_model.solve(
                    geometry, self._inputs(), self._four_channel_settings()
                )
                self.current_four_channel_result = bundle
                self.selected_channel = int(self.channel_selector.currentData())
                result = bundle.channels[self.selected_channel]
                self.plot_workspace.update_four_channel(bundle, self.selected_channel)
                for control, ratio in zip(self.channel_flow_factors, bundle.flow_ratios):
                    control.setValue(float(ratio))
                self._update_channel_map(bundle)
            else:
                self.current_four_channel_result = None
                self.plot_workspace.clear_four_channel()
                result = self.model.solve(geometry, self._inputs())
        except Exception as error:
            self.summary.setText(f"Calculation unavailable: {error}")
            return
        self.current_result = result
        self._present_current_result()

    def _present_current_result(self) -> None:
        result = self.current_result
        if result is None:
            return
        self.channel_balance_summary.setText(
            "<b>CHANNEL TOTALS</b><br>"
            f"Heat transferred: {result.deposited_power_W / 1000.0:.2f} kW<br>"
            f"Heated surface area: {result.heated_surface_area_m2:.5f} m&sup2;<br>"
            f"Average surface heat flux: {result.average_surface_heat_flux_W_m2 / 1.0e6:.4f} MW/m&sup2;<br>"
            f"Pressure drop: {result.total_heated_pressure_drop_kpa:.2f} kPa total<br>"
            f"friction / elevation / acceleration: {result.total_friction_pressure_drop_kpa:.2f} / "
            f"{result.total_gravity_pressure_drop_kpa:.2f} / "
            f"{result.total_acceleration_pressure_drop_kpa:.2f} kPa<br><br>"
            "<b>EXIT CONDITIONS</b><br>"
            f"P / T: {result.outlet_pressure_mpa:.4f} MPa / {result.outlet_temperature_C:.2f} &deg;C<br>"
            f"h: {result.outlet_enthalpy_kj_kg:.2f} kJ/kg<br>"
            f"Equilibrium quality / void: {result.outlet_equilibrium_quality:.4f} / "
            f"{result.outlet_void_fraction:.4f}<br>"
            f"Regime: {result.outlet_flow_regime}"
        )
        self.selected_node = min(self.selected_node, result.z_m.size - 1)
        self.plot_workspace.update_deterministic(result, self.selected_node)
        warning = "<br>".join(result.validity_messages) or "All selected correlation checks passed."
        regimes = _node_ranges(result.flow_regime)
        heat_modes = _node_ranges(result.wall_heat_transfer_mode)
        valid_count = int(np.count_nonzero(result.chf_correlation_valid))
        boiling_count = int(np.count_nonzero(result.nucleate_boiling_active))
        void_valid_count = int(np.count_nonzero(result.void_model_valid))
        friction_valid_count = int(np.count_nonzero(result.two_phase_friction_valid))
        material = CLADDING_MATERIALS[str(self.cladding.currentData())]
        onb_text = (
            f"{result.onset_nucleate_boiling_height_m:.3f} m"
            if np.isfinite(result.onset_nucleate_boiling_height_m) else "not reached"
        )
        bulk_text = (
            f"{result.bulk_boiling_height_m:.3f} m"
            if np.isfinite(result.bulk_boiling_height_m) else "not reached"
        )
        self.summary.setText(
            self._four_channel_summary() +
            f"Outlet: {result.bulk_temperature_C[-1]:.2f} °C<br>"
            f"Peak wall: {result.peak_wall_temperature_C:.2f} °C<br>"
            f"Minimum valid DNBR: {result.minimum_dnbr:.3f}<br>"
            f"Selected CHF ({result.selected_chf_key}) valid nodes: {valid_count}/{result.z_m.size}<br>"
            f"Nucleate-boiling nodes: {boiling_count}/{result.z_m.size}<br>"
            f"Heat shape: {AXIAL_HEAT_SHAPES[result.heat_shape_key].label}<br>"
            f"ONB / bulk saturation elevation: {onb_text} / {bulk_text}<br>"
            f"Non-boiling / subcooled-boiling / bulk two-phase lengths: "
            f"{result.nonboiling_length_m:.3f} / {result.subcooled_boiling_length_m:.3f} / "
            f"{result.bulk_two_phase_length_m:.3f} m<br>"
            f"Void model valid nodes: {void_valid_count}/{result.z_m.size}<br>"
            f"Two-phase friction valid nodes: {friction_valid_count}/{result.z_m.size}<br>"
            f"Regimes: {regimes}<br><br>{warning}"
            f"<br>Wall models: {heat_modes}<br>"
            f"Cladding: {material.label}. {material.note}"
        )
        self._update_node_inspector()
        self.update_illustration()

    def _four_channel_summary(self) -> str:
        bundle = self.current_four_channel_result
        if bundle is None:
            return ""
        limiting = bundle.limiting_channel_index
        node = bundle.limiting_node_index
        selected = bundle.settings[self.selected_channel]
        limiting_text = "No channel has an in-range DNBR"
        if limiting is not None and node is not None:
            channel = bundle.channels[limiting]
            limiting_text = (
                f"Limiting channel: {bundle.settings[limiting].label}; node {node + 1} "
                f"at z={channel.z_m[node]:.3f} m; DNBR={channel.dnbr[node]:.3f}"
            )
        return (
            "<b>STAGE 2 — NESWC COMMON-PLENUM CHANNELS</b><br>"
            "Fixed total flow; equalized path pressure drop; no axial crossflow or mixing.<br>"
            f"Balance: {'converged' if bundle.converged else 'NOT CONVERGED'} in "
            f"{bundle.iteration_count} iterations; ΔP spread {bundle.pressure_drop_spread_kpa:.4f} kPa.<br>"
            f"Total flow {bundle.total_mass_flow_kg_s:.4f} kg/s; common ΔP "
            f"{bundle.common_pressure_drop_kpa:.3f} kPa.<br>"
            f"Inspecting: {selected.label} (power ×{selected.power_multiplier:.3f}, "
            f"solved flow ×{bundle.flow_ratios[self.selected_channel]:.3f})<br>"
            f"{limiting_text}<br><br>"
        )

    def _update_channel_map(self, bundle) -> None:
        limiting = bundle.limiting_channel_index
        for index, (button, setting) in enumerate(zip(self.channel_map_buttons, bundle.settings)):
            channel = bundle.channels[index]
            dnbr = "--" if not np.isfinite(channel.minimum_dnbr) else f"{channel.minimum_dnbr:.2f}"
            marker = " ● LIMIT" if index == limiting else ""
            button.setText(
                f"{button.toolTip().split()[2]}  flow×{bundle.flow_ratios[index]:.2f}"
                f"\nDNBR {dnbr}{marker}"
            )
            button.setStyleSheet(
                "QToolButton { border: 2px solid #f85149; }" if index == limiting else ""
            )

    @QtCore.Slot()
    def run_statistics(self) -> None:
        self.run_case()
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            result = run_statistical_hot_channel(
                self.model, self._geometry(), self._inputs(),
                StatisticalSettings(sample_count=self.samples.value(), seed=self.seed.value()),
            )
            self.plot_workspace.update_statistics(result)
            finite = result.minimum_dnbr[np.isfinite(result.minimum_dnbr)]
            if finite.size:
                self.summary.setText(
                    self.summary.text() +
                    f"<br><br>Statistical DNBR: mean {np.mean(finite):.3f}, "
                    f"5th percentile {np.percentile(finite, 5):.3f}; seed {self.seed.value()}."
                )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
