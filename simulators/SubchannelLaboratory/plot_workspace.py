"""Tabbed PyQtGraph analysis workspace with synchronized axial selection."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from .chf_correlations import CHF_CORRELATIONS


class AnalysisPlotWorkspace(QtWidgets.QWidget):
    def __init__(self, graphs, parent=None) -> None:
        super().__init__(parent)
        self.graphs = graphs
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.selected_node_strip = QtWidgets.QLabel("Selected node: calculation pending")
        self.selected_node_strip.setObjectName("statusPanel")
        self.selected_node_strip.setWordWrap(True)
        self.selected_node_strip.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.selected_node_strip)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.temperature_plot = graphs.line_plot("Axial temperatures", "Height (m)", "Temperature (°C)")
        self.heat_profile_plot = graphs.line_plot(
            "Axial heat-rate distribution", "Heated height (m)", "Linear heat rate (kW/m)"
        )
        self.margin_plot = graphs.line_plot(
            "CHF, applied heat flux, and margin", "Heated height (m)", "MW/m² or DNBR"
        )
        self.phase_plot = graphs.line_plot(
            "Phase and correlation state", "Height (m)", "Quality / void fraction"
        )
        self.pressure_drop_plot = graphs.line_plot(
            "Cumulative pressure-drop decomposition", "Heated height (m)", "Pressure drop (kPa)"
        )
        self.hydraulic_local_plot = graphs.line_plot(
            "Local hydraulic response", "Heated height (m)", "Node ΔP (kPa) / multiplier"
        )
        self.histogram = graphs.line_plot(
            "Statistical minimum DNBR", "Minimum DNBR", "Samples"
        )
        self.wall_temperature_histogram = graphs.line_plot(
            "Statistical peak wall temperature", "Peak wall temperature (°C)", "Samples"
        )
        for title, first, second in (
            ("Thermal", self.temperature_plot, self.heat_profile_plot),
            ("Boiling / CHF", self.margin_plot, self.phase_plot),
            ("Hydraulics", self.pressure_drop_plot, self.hydraulic_local_plot),
            ("Statistics", self.histogram, self.wall_temperature_histogram),
        ):
            splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(6)
            splitter.addWidget(first)
            splitter.addWidget(second)
            splitter.setSizes([360, 360])
            self.tabs.addTab(splitter, title)
        self.tabs.setTabEnabled(3, False)
        self.axial_plots = (
            self.temperature_plot, self.heat_profile_plot, self.margin_plot,
            self.phase_plot, self.pressure_drop_plot, self.hydraulic_local_plot,
        )
        self.axial_cursors: dict[object, pg.InfiniteLine] = {}

    def rebuild_axial_cursors(self, position: float) -> None:
        self.axial_cursors.clear()
        for plot in self.axial_plots:
            cursor = pg.InfiniteLine(
                pos=position,
                angle=90,
                movable=False,
                pen=pg.mkPen("#d7e3ec", width=1, style=QtCore.Qt.DotLine),
            )
            plot.addItem(cursor)
            self.axial_cursors[plot] = cursor

    def set_axial_cursor(self, position: float) -> None:
        for cursor in self.axial_cursors.values():
            cursor.setPos(position)

    def set_node_summary(self, result, index: int, dnbr_text: str) -> None:
        self.selected_node_strip.setText(
            f"Selected node {index + 1}/{result.z_m.size} | z={result.z_m[index]:.3f} m | "
            f"{result.flow_regime[index]} | x={result.equilibrium_quality[index]:.4f} | "
            f"void={result.void_fraction[index]:.4f} | DNBR={dnbr_text}"
        )

    def clear_statistics(self) -> None:
        self.histogram.clear()
        self.wall_temperature_histogram.clear()
        self.tabs.setTabEnabled(3, False)

    def update_deterministic(self, result, selected_node: int) -> None:
        """Populate every axial plot from one deterministic channel result."""
        self.graphs.set_lines(self.temperature_plot, [
            ("Coolant", result.z_m, result.bulk_temperature_C, "#58a6ff"),
            ("Saturation", result.z_m, result.saturation_temperature_C, "#d29922"),
            ("Wall", result.z_m, result.wall_temperature_C, "#f85149"),
            ("Clad inner", result.z_m, result.inner_clad_temperature_C, "#f0b429"),
        ])
        self.graphs.set_lines(self.heat_profile_plot, [
            ("Base linear heat", result.z_m,
             result.base_linear_heat_rate_W_m / 1000.0, "#6e7681"),
            ("Linear heat rate", result.z_m, result.linear_heat_rate_W_m / 1000.0, "#f0b429"),
        ])
        colors = {
            "tong_w3": "#d29922", "biasi": "#bc8cff", "bowring": "#39c5cf",
            "groeneveld_2006": "#58a6ff", "epri_1": "#ff9e64",
        }
        plot_labels = {
            "tong_w3": "Tong W-3", "biasi": "Biasi", "bowring": "Bowring",
            "groeneveld_2006": "Groeneveld 2006 LUT", "epri_1": "EPRI-1",
        }
        margin_lines = [
            ("Applied heat flux (MW/m²)", result.z_m,
             result.surface_heat_flux_W_m2 / 1.0e6, "#f85149"),
        ]
        for key, values in result.chf_predictions_W_m2.items():
            label = plot_labels.get(key, CHF_CORRELATIONS[key].label)
            suffix = " [selected]" if key == result.selected_chf_key else ""
            margin_lines.append(
                (f"{label} CHF{suffix} (MW/m²)", result.z_m, values / 1.0e6,
                 colors.get(key, "#d7e3ec"))
            )
        selected_label = plot_labels.get(
            result.selected_chf_key, CHF_CORRELATIONS[result.selected_chf_key].label
        )
        margin_lines.append(
            (f"{selected_label} DNBR", result.z_m, result.dnbr, "#3fb950")
        )
        self.graphs.set_lines(self.margin_plot, margin_lines)
        self._add_chf_limiting_markers(result, colors)
        self.graphs.set_lines(self.phase_plot, [
            ("Equilibrium quality", result.z_m, result.equilibrium_quality, "#bc8cff"),
            ("Void fraction", result.z_m, result.void_fraction, "#39c5cf"),
            ("Slip ratio", result.z_m, result.slip_ratio, "#d29922"),
            ("Void model valid (1/0)", result.z_m, result.void_model_valid.astype(float), "#3fb950"),
        ])
        self._add_transition_markers(result)
        self.graphs.set_lines(self.pressure_drop_plot, [
            ("Friction", result.z_m, result.cumulative_friction_pressure_drop_kpa, "#58a6ff"),
            ("Elevation", result.z_m, result.cumulative_gravity_pressure_drop_kpa, "#d29922"),
            ("Acceleration", result.z_m, result.cumulative_acceleration_pressure_drop_kpa, "#bc8cff"),
            ("Total", result.z_m, result.cumulative_pressure_drop_kpa, "#3fb950"),
        ])
        self.graphs.set_lines(self.hydraulic_local_plot, [
            ("Node friction ΔP", result.z_m, result.friction_pressure_drop_kpa, "#58a6ff"),
            ("Node elevation ΔP", result.z_m, result.gravity_pressure_drop_kpa, "#d29922"),
            ("Node acceleration ΔP", result.z_m, result.acceleration_pressure_drop_kpa, "#bc8cff"),
            ("Two-phase multiplier", result.z_m, result.two_phase_friction_multiplier, "#3fb950"),
        ])
        self.rebuild_axial_cursors(float(result.z_m[selected_node]))

    def _add_transition_markers(self, result) -> None:
        for position, label, color in (
            (result.onset_nucleate_boiling_height_m, "ONB", "#f85149"),
            (result.bulk_boiling_height_m, "x=0", "#58a6ff"),
        ):
            if np.isfinite(position):
                self.phase_plot.addItem(pg.InfiniteLine(
                    pos=position,
                    angle=90,
                    pen=pg.mkPen(color, width=1, style=QtCore.Qt.DashLine),
                    label=label,
                    labelOpts={"position": 0.92, "color": color},
                ))

    def _add_chf_limiting_markers(self, result, colors: dict[str, str]) -> None:
        for key, values in result.chf_predictions_W_m2.items():
            ratios = np.divide(
                values,
                result.surface_heat_flux_W_m2,
                out=np.full_like(values, np.nan),
                where=result.surface_heat_flux_W_m2 > 0.0,
            )
            if np.all(~np.isfinite(ratios)):
                continue
            index = int(np.nanargmin(ratios))
            color = colors.get(key, "#d7e3ec")
            self.margin_plot.addItem(pg.InfiniteLine(
                pos=float(result.z_m[index]),
                angle=90,
                pen=pg.mkPen(color, width=1, style=QtCore.Qt.DotLine),
            ))

    def update_statistics(self, result) -> None:
        self.graphs.set_histogram(self.histogram, result.minimum_dnbr)
        self.graphs.set_histogram(
            self.wall_temperature_histogram, result.peak_wall_temperature_C
        )
        self.tabs.setTabEnabled(3, True)
