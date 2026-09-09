"""Reusable PyQtGraph plot construction and update adapter."""

from __future__ import annotations

import math
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PySide6 import QtCore, QtGui, QtWidgets


class OrthographicGLViewWidget(gl.GLViewWidget):
    """GL view with engineering-drawing projection and gentler controls."""

    def __init__(self) -> None:
        super().__init__(rotationMethod="euler")
        self.orthographic_scale = 100.0

    def projectionMatrix(self, region, viewport):  # noqa: N802 - Qt/PyQtGraph API
        x0, y0, width, height = viewport
        half_width = max(self.orthographic_scale, 1.0e-6)
        half_height = half_width * height / max(width, 1.0)
        left = half_width * ((region[0] - x0) * (2.0 / width) - 1.0)
        right = half_width * ((region[0] + region[2] - x0) * (2.0 / width) - 1.0)
        bottom = half_height * ((region[1] - y0) * (2.0 / height) - 1.0)
        top = half_height * ((region[1] + region[3] - y0) * (2.0 / height) - 1.0)
        matrix = QtGui.QMatrix4x4()
        distance = max(float(self.opts["distance"]), 1.0)
        matrix.ortho(left, right, bottom, top, distance * 0.001, distance * 1000.0)
        return matrix

    def wheelEvent(self, event):  # noqa: N802 - Qt API
        steps = event.angleDelta().y() / 120.0
        self.orthographic_scale *= 0.84**steps
        self.orthographic_scale = min(max(self.orthographic_scale, 1.0), 1.0e6)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt API
        position = event.position() if hasattr(event, "position") else event.localPos()
        if not hasattr(self, "mousePos"):
            self.mousePos = position
        difference = position - self.mousePos
        self.mousePos = position
        buttons = event.buttons()
        pan_requested = bool(event.modifiers() & QtCore.Qt.ShiftModifier)
        if buttons == QtCore.Qt.LeftButton and not pan_requested:
            self.orbit(-difference.x() * 0.35, difference.y() * 0.35)
        elif buttons in (QtCore.Qt.RightButton, QtCore.Qt.MiddleButton) or pan_requested:
            scale = 2.0 * self.orthographic_scale / max(self.width(), 1)
            self.pan(-difference.x() * scale, difference.y() * scale, 0.0, relative="view")
        event.accept()


class PyQtGraphHandler:
    def __init__(self) -> None:
        pg.setConfigOptions(antialias=True, background="#10151c", foreground="#e6edf3")

    def line_plot(self, title: str, x_label: str, y_label: str) -> pg.PlotWidget:
        plot = pg.PlotWidget(title=title)
        plot.setLabel("bottom", x_label)
        plot.setLabel("left", y_label)
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.addLegend(offset=(8, 8))
        return plot

    @staticmethod
    def subchannel_3d_view() -> OrthographicGLViewWidget:
        view = OrthographicGLViewWidget()
        view.setMinimumHeight(280)
        view.setCameraPosition(distance=8.0, elevation=22.0, azimuth=35.0)
        view.setBackgroundColor("white")
        return view

    @staticmethod
    def set_four_pin_subchannel_3d(
        view: gl.GLViewWidget,
        pitch_m: float,
        rod_outer_diameter_m: float,
        heated_length_m: float,
        unheated_inlet_length_m: float,
        unheated_outlet_length_m: float,
        node_count: int,
        clad_color: str,
        regimes: tuple[str, ...] | None = None,
        selected_node: int | None = None,
    ) -> None:
        """Populate an orbitable four-pin channel in millimetre-scaled coordinates."""
        for item in list(view.items):
            view.removeItem(item)
        scale = 1000.0
        pitch = pitch_m * scale
        diameter = rod_outer_diameter_m * scale
        # Compress axial scale so a 3.66 m rod remains inspectable beside a 12 mm pitch.
        total_length_m = heated_length_m + unheated_inlet_length_m + unheated_outlet_length_m
        shown_length = max(5.0 * pitch, total_length_m * scale / 25.0)
        axial_scale = shown_length / total_length_m
        heated_start = unheated_inlet_length_m * axial_scale
        shown_heated_length = heated_length_m * axial_scale
        line_color = (0.08, 0.08, 0.08, 1.0)
        secondary_color = (0.42, 0.42, 0.42, 1.0)
        dimension_color = QtGui.QColor("#202020")
        font = QtGui.QFont("Arial", 9)
        half = pitch / 2.0
        radius = diameter / 2.0
        arc_steps = 14

        def inward_arc(center_x: float, center_y: float, start: float, stop: float) -> np.ndarray:
            angles = np.linspace(start, stop, arc_steps)
            return np.column_stack((
                center_x + radius * np.cos(angles),
                center_y + radius * np.sin(angles),
            ))

        # Counter-clockwise coolant boundary: straight gap segments connected
        # by concave quarter-circle arcs along the four rod surfaces.
        coolant_boundary = np.vstack((
            inward_arc(half, -half, math.pi, math.pi / 2.0),
            inward_arc(half, half, -math.pi / 2.0, -math.pi),
            inward_arc(-half, half, 0.0, -math.pi / 2.0),
            inward_arc(-half, -half, math.pi / 2.0, 0.0),
        ))
        boundary_count = coolant_boundary.shape[0]
        bottom_center = 2 * boundary_count
        top_center = bottom_center + 1
        vertices = np.vstack((
            np.column_stack((coolant_boundary, np.zeros(boundary_count))),
            np.column_stack((coolant_boundary, np.full(boundary_count, shown_length))),
            np.array([[0.0, 0.0, 0.0], [0.0, 0.0, shown_length]]),
        ))
        faces: list[list[int]] = []
        for index in range(boundary_count):
            next_index = (index + 1) % boundary_count
            faces.extend((
                [bottom_center, next_index, index],
                [top_center, boundary_count + index, boundary_count + next_index],
                [index, next_index, boundary_count + next_index],
                [index, boundary_count + next_index, boundary_count + index],
            ))
        coolant = gl.GLMeshItem(
            meshdata=gl.MeshData(vertexes=vertices, faces=np.asarray(faces, dtype=int)),
            color=(0.20, 0.65, 0.95, 0.24), smooth=False,
            drawFaces=True, drawEdges=False, shader="balloon",
            glOptions="translucent",
        )
        view.addItem(coolant)
        rod_mesh = gl.MeshData.cylinder(
            rows=2, cols=32, radius=[diameter / 2.0, diameter / 2.0],
            length=shown_length,
        )
        clad_rgba = pg.mkColor(clad_color).getRgbF()
        theta = np.linspace(0.0, 2.0 * math.pi, 80)
        for x in (-pitch / 2.0, pitch / 2.0):
            for y in (-pitch / 2.0, pitch / 2.0):
                solid_rod = gl.GLMeshItem(
                    meshdata=rod_mesh, smooth=True, drawFaces=True, drawEdges=True,
                    edgeColor=line_color,
                    color=(clad_rgba[0], clad_rgba[1], clad_rgba[2], 1.0),
                    shader="shaded", glOptions="opaque",
                )
                solid_rod.translate(x, y, 0.0)
                view.addItem(solid_rod)
                for z_plane in (0.0, shown_length):
                    circle = np.column_stack((
                        x + diameter * 0.5 * np.cos(theta),
                        y + diameter * 0.5 * np.sin(theta),
                        np.full(theta.size, z_plane),
                    ))
                    view.addItem(gl.GLLinePlotItem(
                        pos=circle, color=line_color, width=1.4, antialias=True,
                    ))
                for radial_angle in (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi):
                    edge_x = x + diameter * 0.5 * math.cos(radial_angle)
                    edge_y = y + diameter * 0.5 * math.sin(radial_angle)
                    view.addItem(gl.GLLinePlotItem(
                        pos=np.array([[edge_x, edge_y, 0.0], [edge_x, edge_y, shown_length]]),
                        color=line_color, width=1.0, antialias=True,
                    ))

        boundary_color = (0.10, 0.45, 0.68, 1.0)
        corners = np.array([
            [-pitch / 2.0, -pitch / 2.0], [pitch / 2.0, -pitch / 2.0],
            [pitch / 2.0, pitch / 2.0], [-pitch / 2.0, pitch / 2.0],
        ])
        plane_indices = np.unique(np.linspace(0, node_count, min(node_count + 1, 13), dtype=int))
        for index in plane_indices:
            z = heated_start + shown_heated_length * index / node_count
            points = np.column_stack((np.vstack((corners, corners[0])), np.full(5, z)))
            view.addItem(gl.GLLinePlotItem(pos=points, color=secondary_color, width=1.0, antialias=True))
        for corner in corners:
            points = np.array([[corner[0], corner[1], 0.0], [corner[0], corner[1], shown_length]])
            view.addItem(gl.GLLinePlotItem(pos=points, color=boundary_color, width=1.4, antialias=True))

        def add_dimension(start, end, label, text_position) -> None:
            view.addItem(gl.GLLinePlotItem(
                pos=np.array([start, end], dtype=float), color=line_color,
                width=1.5, antialias=True,
            ))
            direction = np.array(end, dtype=float) - np.array(start, dtype=float)
            length = np.linalg.norm(direction)
            if length > 0.0:
                direction /= length
                if abs(direction[2]) > 0.8:
                    tick = np.array([1.0, 0.0, 0.0]) * max(pitch * 0.08, 0.8)
                else:
                    tick = np.array([-direction[1], direction[0], 0.0]) * max(pitch * 0.08, 0.8)
                for endpoint in (np.array(start, dtype=float), np.array(end, dtype=float)):
                    view.addItem(gl.GLLinePlotItem(
                        pos=np.array([endpoint - tick, endpoint + tick]), color=line_color,
                        width=1.2, antialias=True,
                    ))
            view.addItem(gl.GLTextItem(
                pos=np.array(text_position, dtype=float), color=dimension_color,
                text=label, font=font,
            ))

        bottom_y = -pitch / 2.0
        add_dimension(
            (-pitch / 2.0, bottom_y, 0.0), (pitch / 2.0, bottom_y, 0.0),
            f"pitch {pitch:.2f} mm", (0.0, bottom_y - diameter * 0.75, 0.0),
        )
        add_dimension(
            (-pitch / 2.0 - diameter / 2.0, bottom_y, 0.0),
            (-pitch / 2.0 + diameter / 2.0, bottom_y, 0.0),
            f"OD {diameter:.2f} mm", (-pitch / 2.0, bottom_y + diameter * 0.65, 0.0),
        )
        dimension_x = pitch * 1.05
        add_dimension(
            (dimension_x, pitch / 2.0, heated_start),
            (dimension_x, pitch / 2.0, heated_start + shown_heated_length),
            f"heated {heated_length_m:.3f} m",
            (dimension_x + diameter * 0.35, pitch / 2.0, heated_start + shown_heated_length / 2.0),
        )
        perimeter = math.pi * rod_outer_diameter_m * scale
        flow_area = (pitch_m**2 - math.pi * rod_outer_diameter_m**2 / 4.0) * 1.0e6
        hydraulic_diameter = 4.0 * flow_area / perimeter
        notes = (
            f"Pw={perimeter:.2f} mm\nA={flow_area:.2f} mm²\nDh={hydraulic_diameter:.2f} mm"
        )
        view.addItem(gl.GLTextItem(
            pos=np.array((-pitch * 1.25, pitch * 1.35, shown_length * 0.55)),
            color=dimension_color, text=notes, font=font,
        ))

        if regimes:
            palette = {
                "single-phase liquid": (0.35, 0.65, 1.0, 1.0),
                "subcooled nucleate boiling": (1.0, 0.65, 0.15, 1.0),
                "bulk two-phase": (0.85, 0.35, 0.85, 1.0),
            }
            for index, regime in enumerate(regimes):
                z0 = heated_start + index * shown_heated_length / node_count
                z1 = heated_start + (index + 1) * shown_heated_length / node_count
                view.addItem(gl.GLLinePlotItem(
                    pos=np.array([[0.0, 0.0, z0], [0.0, 0.0, z1]]),
                    color=palette.get(regime, (0.5, 0.5, 0.5, 1.0)),
                    width=4.0, antialias=True,
                ))
        if selected_node is not None:
            z = heated_start + (selected_node + 0.5) * shown_heated_length / node_count
            selected_boundary = np.vstack((coolant_boundary, coolant_boundary[0]))
            square = np.column_stack((selected_boundary, np.full(selected_boundary.shape[0], z)))
            view.addItem(gl.GLLinePlotItem(
                pos=square, color=(1.0, 0.25, 0.2, 1.0), width=3.0, antialias=True,
            ))
        extent = max(3.0 * pitch, shown_length)
        view.setCameraPosition(
            pos=QtGui.QVector3D(0.0, 0.0, shown_length / 2.0),
            distance=extent * 4.0, elevation=18.0, azimuth=35.0,
        )
        if isinstance(view, OrthographicGLViewWidget):
            view.orthographic_scale = max(1.5 * pitch, shown_length * 0.62)
            view.update()

    @staticmethod
    def set_neswc_channels_3d(
        view: gl.GLViewWidget,
        pitch_m: float,
        rod_outer_diameter_m: float,
        heated_length_m: float,
        unheated_inlet_length_m: float,
        unheated_outlet_length_m: float,
        node_count: int,
        clad_color: str,
        regimes: tuple[tuple[str, ...], ...] | None = None,
        selected_channel: int = 0,
        limiting_channel: int | None = None,
        selected_node: int | None = None,
    ) -> None:
        """Draw the original center cell with north/east/south/west neighbors."""
        for item in list(view.items):
            view.removeItem(item)
        scale = 1000.0
        pitch = pitch_m * scale
        diameter = rod_outer_diameter_m * scale
        total_length_m = heated_length_m + unheated_inlet_length_m + unheated_outlet_length_m
        shown_length = max(6.0 * pitch, total_length_m * scale / 25.0)
        axial_scale = shown_length / total_length_m
        heated_start = unheated_inlet_length_m * axial_scale
        shown_heated = heated_length_m * axial_scale
        clad_rgba = pg.mkColor(clad_color).getRgbF()
        rod_mesh = gl.MeshData.cylinder(
            rows=2, cols=28, radius=[diameter / 2.0, diameter / 2.0], length=shown_length
        )
        centers = ((0.0, pitch), (pitch, 0.0), (0.0, -pitch),
                   (-pitch, 0.0), (0.0, 0.0))
        rod_centers = sorted({
            (cx + dx, cy + dy)
            for cx, cy in centers
            for dx in (-pitch / 2, pitch / 2)
            for dy in (-pitch / 2, pitch / 2)
        })
        for x, y in rod_centers:
            rod = gl.GLMeshItem(
                meshdata=rod_mesh, smooth=True, drawFaces=True, drawEdges=True,
                edgeColor=(0.08, 0.08, 0.08, 1.0),
                color=(*clad_rgba[:3], 1.0), shader="shaded", glOptions="opaque",
            )
            rod.translate(x, y, 0.0)
            view.addItem(rod)

        labels = ("N", "E", "S", "W", "C")
        palette = {
            "single-phase liquid": (0.35, 0.65, 1.0, 1.0),
            "subcooled nucleate boiling": (1.0, 0.65, 0.15, 1.0),
            "bulk two-phase": (0.85, 0.35, 0.85, 1.0),
        }
        for channel, ((cx, cy), label) in enumerate(zip(centers, labels)):
            corners = np.array([
                [cx - pitch / 2, cy - pitch / 2], [cx + pitch / 2, cy - pitch / 2],
                [cx + pitch / 2, cy + pitch / 2], [cx - pitch / 2, cy + pitch / 2],
                [cx - pitch / 2, cy - pitch / 2],
            ])
            is_selected = channel == selected_channel
            is_limiting = channel == limiting_channel
            color = ((1.0, 0.25, 0.2, 1.0) if is_limiting else
                     (0.10, 0.80, 0.90, 1.0) if is_selected else
                     (0.10, 0.45, 0.68, 0.75))
            width = 3.5 if is_selected or is_limiting else 1.4
            for z in (heated_start, heated_start + shown_heated):
                view.addItem(gl.GLLinePlotItem(
                    pos=np.column_stack((corners, np.full(5, z))),
                    color=color, width=width, antialias=True,
                ))
            for corner in corners[:4]:
                view.addItem(gl.GLLinePlotItem(
                    pos=np.array([[corner[0], corner[1], heated_start],
                                  [corner[0], corner[1], heated_start + shown_heated]]),
                    color=color, width=width, antialias=True,
                ))
            if regimes is not None:
                for node, regime in enumerate(regimes[channel]):
                    z0 = heated_start + node * shown_heated / node_count
                    z1 = heated_start + (node + 1) * shown_heated / node_count
                    view.addItem(gl.GLLinePlotItem(
                        pos=np.array([[cx, cy, z0], [cx, cy, z1]]),
                        color=palette.get(regime, (0.5, 0.5, 0.5, 1.0)),
                        width=4.0, antialias=True,
                    ))
            text = label + ("  LIMIT" if is_limiting else "")
            view.addItem(gl.GLTextItem(
                pos=np.array((cx, cy, heated_start + shown_heated + 0.05 * shown_length)),
                color=QtGui.QColor("#d62728" if is_limiting else "#202020"),
                text=text, font=QtGui.QFont("Arial", 9),
            ))

        if selected_node is not None:
            cx, cy = centers[selected_channel]
            z = heated_start + (selected_node + 0.5) * shown_heated / node_count
            half = pitch / 2
            outline = np.array([
                [cx-half, cy-half, z], [cx+half, cy-half, z], [cx+half, cy+half, z],
                [cx-half, cy+half, z], [cx-half, cy-half, z],
            ])
            view.addItem(gl.GLLinePlotItem(
                pos=outline, color=(0.95, 0.95, 0.2, 1.0), width=4.0, antialias=True
            ))
        extent = max(4.0 * pitch, shown_length)
        view.setCameraPosition(
            pos=QtGui.QVector3D(0.0, 0.0, shown_length / 2.0),
            distance=extent * 4.0, elevation=22.0, azimuth=35.0,
        )
        if isinstance(view, OrthographicGLViewWidget):
            view.orthographic_scale = max(2.2 * pitch, shown_length * 0.62)
            view.update()

    @staticmethod
    def set_lines(plot: pg.PlotWidget, series: list[tuple[str, np.ndarray, np.ndarray, str]]) -> None:
        plot.clear()
        plot.addLegend(offset=(8, 8))
        for name, x, y, color in series:
            plot.plot(x, y, pen=pg.mkPen(color, width=2), name=name)

    @staticmethod
    def set_histogram(plot: pg.PlotWidget, values: np.ndarray, color: str = "#d29922") -> None:
        plot.clear()
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return
        counts, edges = np.histogram(finite, bins=min(30, max(5, int(np.sqrt(finite.size)))))
        item = pg.BarGraphItem(
            x=(edges[:-1] + edges[1:]) / 2.0,
            height=counts,
            width=np.diff(edges) * 0.9,
            brush=pg.mkBrush(color),
        )
        plot.addItem(item)

    @staticmethod
    def set_four_pin_subchannel(
        plot: pg.PlotWidget,
        pitch_m: float,
        rod_outer_diameter_m: float,
        clad_inner_diameter_m: float,
        rotation_degrees: float,
        clad_color: str,
    ) -> None:
        """Draw a zoomable four-pin subchannel cross-section."""
        plot.clear()
        plot.setAspectLocked(True)
        angle = math.radians(rotation_degrees)
        rotation = np.array([
            [math.cos(angle), -math.sin(angle)],
            [math.sin(angle), math.cos(angle)],
        ])
        centers = np.array([
            [-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5],
        ]) * pitch_m
        centers = centers @ rotation.T
        theta = np.linspace(0.0, 2.0 * math.pi, 100)
        for center in centers:
            for diameter, color, width in (
                (rod_outer_diameter_m, clad_color, 3),
                (clad_inner_diameter_m, "#f0b429", 2),
            ):
                x = center[0] + diameter * 0.5 * np.cos(theta)
                y = center[1] + diameter * 0.5 * np.sin(theta)
                plot.plot(x * 1000.0, y * 1000.0, pen=pg.mkPen(color, width=width))
        polygon = np.vstack((centers, centers[0]))
        plot.plot(
            polygon[:, 0] * 1000.0, polygon[:, 1] * 1000.0,
            pen=pg.mkPen("#39c5cf", width=2, style=QtCore.Qt.DashLine),
        )
        marker = pg.ScatterPlotItem([0.0], [0.0], size=12, brush=pg.mkBrush("#39c5cf"))
        plot.addItem(marker)
        label = pg.TextItem("subchannel", color="#39c5cf", anchor=(0.5, 1.2))
        label.setPos(0.0, 0.0)
        plot.addItem(label)
        plot.setLabel("bottom", "x", units="mm")
        plot.setLabel("left", "y", units="mm")
        plot.enableAutoRange()


def ensure_qt_application() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
