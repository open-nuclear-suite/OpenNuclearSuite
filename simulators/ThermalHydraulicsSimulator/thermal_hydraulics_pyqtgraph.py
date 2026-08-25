"""Full-featured PySide6/PyQtGraph thermal-hydraulics simulator UI."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

from thermal_hydraulics_gui_backend import (
    CONTROL_LIMITS, DEMO_SCRIPTS, SCENARIOS, ThermalHydraulicsGUIBackend,
)


STYLE = """
QWidget { background:#0d1218; color:#edf4fa; font:14px 'Segoe UI'; }
QGroupBox { border:1px solid #40505d; border-radius:5px; margin-top:10px; padding-top:9px; font-weight:bold; color:#67c7ff; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }
QPushButton { background:#343a40; border:1px solid #3f464d; border-radius:17px; min-height:34px; padding:0 12px; }
QPushButton:hover { background:#286c99; } QPushButton:pressed { background:#13384f; }
QWidget#commandBar QPushButton { font-size:12px; padding:0 7px; }
QSlider::groove:horizontal { height:7px; background:#293945; border-radius:3px; }
QSlider::handle:horizontal { width:17px; margin:-5px 0; background:#67c7ff; border-radius:8px; }
QProgressBar { border:1px solid #40505d; border-radius:3px; text-align:center; background:#18222b; }
QProgressBar::chunk { background:#247eb0; }
QPlainTextEdit { background:#101820; border:1px solid #40505d; font-family:Consolas; }
QTabWidget::pane { border:1px solid #40505d; }
QTabBar::tab { background:#17232d; padding:7px 13px; } QTabBar::tab:selected { background:#1d4e70; }
"""

ABOUT = """Open Nuclear Engineering Teaching Suite

Created and maintained by maxisnote.

Questions, feedback, and reports of how the simulator is being used are welcome.

Email: maxisnote2@gmail.com

Thank you for using the Open Nuclear Engineering Teaching Suite."""

SLIDER_SPECS = (
    ("rod", "Rod insertion %", 1), ("trim", "Fine reactivity pcm", 1),
    ("boron", "Soluble boron ppm", 1), ("pump", "Primary pump %", 1),
    ("sg", "SG heat removal %", 1), ("break", "LOCA break size %", 1),
    ("eccs", "Manual ECCS %", 1), ("afw", "Auxiliary feedwater %", 1),
    ("porv", "PORV / relief %", 1), ("spray", "Pressurizer spray %", 1),
    ("heater", "Pressurizer heater %", 1), ("rhr", "RHR cooldown %", 1),
    ("noise", "Instrument noise %", 10), ("speed", "Simulation speed", 10),
)


def configure_plot(plot, title, y_label):
    plot.setTitle(title)
    plot.setLabel("bottom", "Simulation time", units="s")
    plot.setLabel("left", y_label)
    plot.addLegend()
    plot.showGrid(x=True, y=True, alpha=.25)


class ScalablePlotWidget(pg.PlotWidget):
    """Keep a mouse-wheel zoom until the user double-clicks to reset it."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_scaled = False
        self.setMouseEnabled(x=True, y=True)
        self.getViewBox().sigRangeChangedManually.connect(self._mark_user_scaled)

    def _mark_user_scaled(self, *_args):
        self.user_scaled = True

    def wheelEvent(self, event):
        self.user_scaled = True
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.user_scaled = False
        self.enableAutoRange(x=True, y=True)
        super().mouseDoubleClickEvent(event)


class PlantMimic(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sim = None
        self.setMinimumSize(490, 215)
        self.setMaximumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def refresh(self, sim):
        self.sim = sim
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.sim is None:
            return
        s, painter = self.sim.state, QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min(self.width() / 490, self.height() / 215)
        painter.translate((self.width()-490*scale)/2, (self.height()-215*scale)/2)
        painter.scale(scale, scale)
        coolant = QColor("#239bf5") if s.M > .65 else QColor("#ff5f23")
        steel, vessel = QColor("#a0afb9"), QColor("#1c2630")
        painter.setPen(QPen(steel, 3)); painter.setBrush(vessel); painter.drawRect(40, 35, 130, 155)
        level_y = 183 - 140 * min(max(s.M, 0), 1)
        fill = QColor(coolant); fill.setAlpha(90)
        painter.setPen(coolant); painter.setBrush(fill); painter.drawRect(50, int(level_y), 110, int(180-level_y))
        painter.setPen(QPen(coolant, 10))
        for a, b in (((170,60),(280,60)),((280,60),(280,170)),((280,170),(170,170)),((280,60),(335,75)),((335,155),(280,170))):
            painter.drawLine(*a, *b)
        painter.setPen(QPen(steel, 3)); painter.setBrush(vessel); painter.drawEllipse(310, 60, 110, 110)
        painter.setPen(QColor("#f0f0f5")); painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        painter.drawText(70, 118, "CORE"); painter.drawText(326, 108, "STEAM"); painter.drawText(336, 130, "GEN.")
        painter.setPen(QColor("#78dcff")); painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(8, 20, f"{s.P:5.2f} MPa   {100*s.M:5.1f}% inventory   {100*s.void_fraction:4.1f}% void")
        if self.sim.eccs_is_active():
            painter.setPen(QPen(QColor("#46ff78"), 8)); painter.drawLine(105, 15, 105, 35)
            painter.setPen(QColor("#46ff78")); painter.drawText(118, 29, "ECCS")
        if self.sim.control_vars["break"].get() > 0:
            painter.setPen(QPen(QColor("#ff5023"), 6)); painter.drawLine(190, 170, 210, 205)
            painter.setPen(QColor("#ff5a28")); painter.drawText(215, 202, "BREAK")


class HotChannelDialog(QDialog):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Representative 1-D Hot Channel — PyQtGraph")
        self.resize(1180, 820)
        layout = QVBoxLayout(self)
        self.summary = QLabel("Calculating hot channel..."); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        tabs = QTabWidget(); layout.addWidget(tabs)
        self.axial = ScalablePlotWidget(); configure_plot(self.axial, "Axial hot-channel temperatures", "Temperature (°C)")
        self.axial.setLabel("bottom", "Distance from inlet", units="m")
        self.fuel = self.axial.plot(pen=pg.mkPen("#b576d8", width=2), name="Fuel centre")
        self.clad = self.axial.plot(pen=pg.mkPen("#ff6655", width=2), name="Clad surface")
        self.cool = self.axial.plot(pen=pg.mkPen("#55aaff", width=2), name="Bulk coolant")
        self.sat = self.axial.plot(pen=pg.mkPen("#55cc77", width=2, style=Qt.PenStyle.DashLine), name="Saturation")
        tabs.addTab(self.axial, "Axial temperatures")
        self.chf = ScalablePlotWidget(); configure_plot(self.chf, "Local heat flux, W-3 CHF, and DNBR", "Heat flux (MW/m²)")
        self.chf.setLabel("bottom", "Distance from inlet", units="m")
        self.flux = self.chf.plot(pen=pg.mkPen("#ff9933", width=2), name="Actual heat flux")
        self.chf_line = self.chf.plot(pen=pg.mkPen("#22ccee", width=2), name="W-3 CHF")
        self.invalid_chf = self.chf.plot([], [], pen=None, symbol="x", symbolPen=pg.mkPen("#ff5577", width=2), symbolSize=9, name="W-3 out of range")
        plot_item = self.chf.getPlotItem(); plot_item.showAxis("right")
        self.dnbr_view = pg.ViewBox(); plot_item.scene().addItem(self.dnbr_view)
        self.dnbr_view.sigRangeChangedManually.connect(lambda *_args: setattr(self.chf, "user_scaled", True))
        plot_item.getAxis("right").linkToView(self.dnbr_view); plot_item.getAxis("right").setLabel("DNBR (-)")
        self.dnbr_view.setXLink(plot_item)
        self.dnbr = pg.PlotCurveItem(pen=pg.mkPen("#eeeeee", width=2)); self.dnbr_view.addItem(self.dnbr)
        plot_item.legend.addItem(self.dnbr, "DNBR")
        self.dnbr_limit = pg.InfiniteLine(pos=1, angle=0, pen=pg.mkPen("#ff5577", width=1, style=Qt.PenStyle.DashLine)); self.dnbr_view.addItem(self.dnbr_limit)
        plot_item.vb.sigResized.connect(self._sync_dnbr_axis); self._sync_dnbr_axis()
        tabs.addTab(self.chf, "CHF and DNBR")
        self.trend = ScalablePlotWidget(); configure_plot(self.trend, "Transient hot-channel response — rolling 40 s", "Temperature (°C)")
        self.tf = self.trend.plot(pen=pg.mkPen("#b576d8", width=2), name="Peak fuel")
        self.tc = self.trend.plot(pen=pg.mkPen("#ff6655", width=2), name="Peak clad")
        self.to = self.trend.plot(pen=pg.mkPen("#55aaff", width=2), name="Outlet")
        tabs.addTab(self.trend, "Transient trends")
        self.nodes = QPlainTextEdit(); self.nodes.setReadOnly(True); self.nodes.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        tabs.addTab(self.nodes, "Axial node data")
        close = QPushButton("CLOSE"); close.clicked.connect(self.close); layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _sync_dnbr_axis(self):
        plot_item = self.chf.getPlotItem()
        self.dnbr_view.setGeometry(plot_item.vb.sceneBoundingRect())
        self.dnbr_view.linkedViewChanged(plot_item.vb, self.dnbr_view.XAxis)

    def refresh(self, sim):
        result, s = sim.hot_channel_result, sim.state
        if result is None:
            self.summary.setText(f"Hot-channel calculation unavailable: {sim.hot_channel_error or 'awaiting a valid model state'}")
            return
        idx = result.minimum_dnbr_index
        dnbr = "unavailable" if idx is None else f"{result.minimum_dnbr:.2f} at z={result.z_m[idx]:.2f} m"
        warning = f" Warning: {result.phase_warning}" if result.phase_warning else ""
        self.summary.setText(f"{result.z_m.size}-node representative channel | Peak fuel {s.hot_peak_fuel_C:.1f} °C | Peak clad {s.hot_peak_clad_C:.1f} °C | Outlet {s.hot_outlet_C:.1f} °C | Minimum W-3 DNBR {dnbr}.{warning}")
        z = result.z_m
        self.fuel.setData(z, result.fuel_centerline_temperature_C); self.clad.setData(z, result.clad_surface_temperature_C)
        self.cool.setData(z, result.bulk_temperature_C); self.sat.setData(z, result.saturation_temperature_C)
        chf = result.critical_heat_flux_W_m2/1e6
        self.flux.setData(z, result.surface_heat_flux_W_m2/1e6); self.chf_line.setData(z, chf); self.dnbr.setData(z, result.dnbr)
        invalid = ~result.chf_correlation_valid
        self.invalid_chf.setData(z[invalid], np.zeros(np.count_nonzero(invalid)))
        finite_dnbr = result.dnbr[np.isfinite(result.dnbr)]
        if not self.chf.user_scaled:
            self.dnbr_view.setYRange(0, max(3, min(10, 1.5*float(np.nanmax(finite_dnbr)))) if finite_dnbr.size else 6, padding=0)
        h, t = s.hist, np.asarray(s.hist.t)
        self.tf.setData(t, h.hot_fuel); self.tc.setData(t, h.hot_clad); self.to.setData(t, h.hot_outlet)
        if t.size and not self.trend.user_scaled: self.trend.setXRange(max(0, t[-1]-40), max(40, t[-1]), padding=0)
        rows = ["Node | z (m) | P (MPa) | h (kJ/kg) | Coolant C | Clad C | Fuel C | Quality | Eq. quality | q MW/m² | CHF MW/m² | DNBR"]
        for i, zv in enumerate(z):
            quality = "--" if np.isnan(result.quality[i]) else f"{result.quality[i]:.4f}"
            local_dnbr = result.dnbr[i]
            rows.append(f"{i+1:4d} | {zv:5.3f} | {result.pressure_mpa[i]:7.3f} | {result.enthalpy_kj_kg[i]:9.2f} | {result.bulk_temperature_C[i]:9.2f} | {result.clad_surface_temperature_C[i]:6.2f} | {result.fuel_centerline_temperature_C[i]:6.2f} | {quality:>7} | {result.equilibrium_quality[i]:10.4f} | {result.surface_heat_flux_W_m2[i]/1e6:7.3f} | {result.critical_heat_flux_W_m2[i]/1e6:8.3f} | {'--' if np.isnan(local_dnbr) else f'{local_dnbr:.3f}'}")
        self.nodes.setPlainText("\n".join(rows))


class MainWindow(QMainWindow):
    PLOT_POINTS = 1000

    def __init__(self, model_dir=None):
        super().__init__()
        self.backend = ThermalHydraulicsGUIBackend(model_dir) if model_dir else ThermalHydraulicsGUIBackend()
        self.speed, self.freeze_chart, self.syncing = 1.0, False, False
        self.last_tick = self.last_perf = time.perf_counter()
        self.steps = self.refreshes = 0; self.steps_s = self.refresh_hz = self.ui_ms = 0.0
        self.setWindowTitle("Thermal-Hydraulics and LOCA Teaching Simulator — PyQtGraph")
        self.resize(1520, 920); self.setStyleSheet(STYLE)
        pg.setConfigOptions(antialias=False, useOpenGL=True, background="#0b1117", foreground="#dceaf4")
        self._build_ui()
        self.hot = HotChannelDialog()
        self.physics_timer = QTimer(self, interval=16); self.physics_timer.timeout.connect(self.tick); self.physics_timer.start()
        self.ui_timer = QTimer(self, interval=100); self.ui_timer.timeout.connect(self.refresh); self.ui_timer.start()
        self.sync_controls(); self.refresh()

    @property
    def sim(self): return self.backend.sim

    @property
    def state(self): return self.backend.state

    def _button(self, text, callback, layout):
        button = QPushButton(text); button.clicked.connect(callback); layout.addWidget(button); return button

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root); outer = QVBoxLayout(root)
        header = QHBoxLayout(); outer.addLayout(header)
        heading = QVBoxLayout(); header.addLayout(heading, 1)
        title = QLabel("LIGHT WATER REACTOR THERMAL-HYDRAULICS TRAINING PANEL"); title.setStyleSheet("font-size:23px;font-weight:bold")
        heading.addWidget(title); heading.addWidget(QLabel("Open Nuclear Engineering Teaching Suite"))
        self._button("ABOUT", lambda: QMessageBox.information(self, "About — Open Nuclear Engineering Teaching Suite", ABOUT), header)
        command_widget = QWidget(); command_widget.setObjectName("commandBar")
        commands = QHBoxLayout(command_widget); commands.setContentsMargins(0, 0, 0, 0); commands.setSpacing(4); outer.addWidget(command_widget)
        sim_group = QGroupBox("SIMULATION"); sim_bar = QHBoxLayout(sim_group); commands.addWidget(sim_group)
        scenario_group = QGroupBox("SCENARIOS"); scenario_bar = QHBoxLayout(scenario_group); commands.addWidget(scenario_group)
        output_group = QGroupBox("ANALYSIS AND OUTPUT"); output_bar = QHBoxLayout(output_group); commands.addWidget(output_group)
        for bar in (sim_bar, scenario_bar, output_bar):
            bar.setContentsMargins(5, 10, 5, 5); bar.setSpacing(4)
        for text, fn in (("START", self.backend.start), ("PAUSE", self.backend.pause), ("SCRAM", self.scram), ("RESET", self.reset), ("STEP 1 s", self.step), ("FREEZE", self.toggle_freeze)):
            button = self._button(text, fn, sim_bar)
            if text == "FREEZE": self.freeze_button = button
        for name in SCENARIOS: self._button(name, lambda _=False, n=name: self.scenario(n), scenario_bar)
        self._button("EXPORT CSV", self.export_csv, output_bar)
        self._button("HOT CHANNEL", self.show_hot, output_bar)
        self._button("SUMMARY", self.show_summary, output_bar)
        status_row = QHBoxLayout(); outer.addLayout(status_row)
        self.status = QLabel(); self.status.setStyleSheet("color:#5adc8c;font-weight:bold"); status_row.addWidget(self.status)
        self.perf = QLabel(); self.perf.setStyleSheet("color:#5ac8ff"); status_row.addWidget(self.perf); status_row.addStretch()
        splitter = QSplitter(); outer.addWidget(splitter, 1)
        splitter.addWidget(self._build_operator_pane()); splitter.addWidget(self._build_plant_pane()); splitter.setSizes([390, 1110])

    def _build_operator_pane(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); controls = QWidget(); scroll.setWidget(controls); form = QVBoxLayout(controls)
        self.sliders, self.slider_values = {}, {}
        primary = QGroupBox("CORE / PRIMARY CONTROLS"); pform = QVBoxLayout(primary); form.addWidget(primary)
        safety = QGroupBox("SAFETY / SUPPORT"); sform = QVBoxLayout(safety); form.addWidget(safety)
        for index, (key, label, scale) in enumerate(SLIDER_SPECS):
            target = pform if index < 6 else sform
            row = QWidget(); layout = QVBoxLayout(row); layout.setContentsMargins(0, 1, 0, 1)
            value = QLabel(); slider = QSlider(Qt.Orientation.Horizontal)
            lo, hi = CONTROL_LIMITS[key]; slider.setRange(round(lo*scale), round(hi*scale))
            slider.valueChanged.connect(lambda raw, k=key, sc=scale: self.control_changed(k, raw/sc))
            layout.addWidget(QLabel(label)); layout.addWidget(value); layout.addWidget(slider); target.addWidget(row)
            self.sliders[key], self.slider_values[key] = slider, value
        self.checks = {}
        for key, label in (("eccs", "Auto ECCS logic"), ("trip", "Auto reactor trip"), ("hot_channel", "Couple axial hot channel")):
            check = QCheckBox(label); check.toggled.connect(lambda enabled, k=key: self.automatic_changed(k, enabled)); sform.addWidget(check); self.checks[key] = check
        demo_box = QGroupBox("TEACHING DEMONSTRATION"); demo_layout = QVBoxLayout(demo_box)
        self.demo_combo = QComboBox(); self.demo_combo.addItems(DEMO_SCRIPTS); demo_layout.addWidget(self.demo_combo)
        self.demo_button = QPushButton("START DEMO"); self.demo_button.clicked.connect(self.toggle_demo); demo_layout.addWidget(self.demo_button)
        self.demo_stage = QLabel("Manual control"); self.demo_stage.setWordWrap(True); demo_layout.addWidget(self.demo_stage); form.addWidget(demo_box)
        readout_box = QGroupBox("LIVE READOUT"); read_layout = QVBoxLayout(readout_box); self.readout = QLabel(); self.readout.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); self.readout.setStyleSheet("font-family:Consolas"); read_layout.addWidget(self.readout); form.addWidget(readout_box)
        events_box = QGroupBox("EVENT TIMELINE"); events_layout = QVBoxLayout(events_box); clear = QPushButton("CLEAR"); clear.clicked.connect(self.clear_events); events_layout.addWidget(clear, alignment=Qt.AlignmentFlag.AlignRight)
        self.events = QPlainTextEdit(); self.events.setReadOnly(True); self.events.setMinimumHeight(180); events_layout.addWidget(self.events); form.addWidget(events_box); form.addStretch()
        return scroll

    def _build_plant_pane(self):
        panel = QWidget(); layout = QVBoxLayout(panel); top = QHBoxLayout(); layout.addLayout(top)
        upper_panel_height = 270
        mimic_box = QGroupBox("PRIMARY LOOP / INVENTORY MIMIC"); mimic_layout = QVBoxLayout(mimic_box); self.mimic = PlantMimic(); mimic_layout.addWidget(self.mimic); mimic_box.setFixedHeight(upper_panel_height); top.addWidget(mimic_box, 1, alignment=Qt.AlignmentFlag.AlignTop)
        limits_box = QGroupBox("PROTECTION AND THERMAL LIMITS"); limits = QVBoxLayout(limits_box); limits.setSpacing(2); limits.setContentsMargins(9, 12, 9, 7); limits_box.setFixedHeight(upper_panel_height); top.addWidget(limits_box, 1, alignment=Qt.AlignmentFlag.AlignTop)
        self.bars = {}
        for key, label in (("power", "REACTOR POWER"), ("inventory", "PRIMARY INVENTORY"), ("pressure", "PRESSURE"), ("clad", "CLAD TEMPERATURE"), ("dnbr", "AXIAL DNBR MARGIN")):
            metric_label = QLabel(label); metric_label.setStyleSheet("font-size:12px"); limits.addWidget(metric_label)
            bar = QProgressBar(); bar.setRange(0, 1000); bar.setFixedHeight(17); limits.addWidget(bar); self.bars[key] = bar
        self.alarms = QLabel(); self.alarms.setWordWrap(True); self.alarms.setStyleSheet("color:#ffbd46;font-weight:bold"); limits.addWidget(self.alarms)
        tabs = QTabWidget(); layout.addWidget(tabs, 1)
        self.power_plot = ScalablePlotWidget(); configure_plot(self.power_plot, "Power and decay heat — rolling 40 s", "Percent nominal")
        self.power = self.power_plot.plot(pen=pg.mkPen("#55aaff", width=2), name="Power %"); self.decay = self.power_plot.plot(pen=pg.mkPen("#ff9933", width=2), name="Decay heat %"); tabs.addTab(self.power_plot, "Power / decay heat")
        self.temp_plot = ScalablePlotWidget(); configure_plot(self.temp_plot, "Fuel, clad, and coolant temperatures", "Temperature (°C)")
        self.fuel = self.temp_plot.plot(pen=pg.mkPen("#b576d8", width=2), name="Fuel"); self.clad = self.temp_plot.plot(pen=pg.mkPen("#ff6655", width=2), name="Clad"); self.cool = self.temp_plot.plot(pen=pg.mkPen("#55aaff", width=2), name="Coolant"); self.hot_clad = self.temp_plot.plot(pen=pg.mkPen("#ffcc44", width=2), name="Axial peak clad"); tabs.addTab(self.temp_plot, "Temperatures")
        self.pressure_plot = ScalablePlotWidget(); configure_plot(self.pressure_plot, "Pressure, inventory, and void", "MPa / scaled fraction")
        self.pressure = self.pressure_plot.plot(pen=pg.mkPen("#55aaff", width=2), name="Pressure MPa"); self.inventory = self.pressure_plot.plot(pen=pg.mkPen("#55dd88", width=2), name="Inventory / 10"); self.void = self.pressure_plot.plot(pen=pg.mkPen("#ff9933", width=2), name="Void / 10"); tabs.addTab(self.pressure_plot, "Pressure / inventory")
        return panel

    def control_changed(self, key, value):
        if self.syncing: return
        if key == "speed": self.speed = value
        else: self.backend.set_control(key, value)
        self.slider_values[key].setText(f"{value:.1f}{'x' if key == 'speed' else ''}")

    def automatic_changed(self, key, enabled):
        if not self.syncing: self.backend.set_automatic(key, enabled)

    def sync_controls(self):
        self.syncing = True
        try:
            for key, _label, scale in SLIDER_SPECS:
                value = self.speed if key == "speed" else self.sim.control_vars[key].get()
                self.sliders[key].setValue(round(value*scale)); self.slider_values[key].setText(f"{value:.1f}{'x' if key == 'speed' else ''}")
            for check, value in (("eccs", self.sim.auto_eccs_var.get()), ("trip", self.sim.auto_trip_var.get()), ("hot_channel", self.sim.hot_channel_coupling_var.get())): self.checks[check].setChecked(bool(value))
        finally: self.syncing = False

    def scram(self): self.backend.scram(); self.sync_controls()

    def toggle_demo(self):
        if self.backend.demo_mode: self.backend.stop_demo()
        else: self.backend.start_demo(self.demo_combo.currentText())
        self.sync_controls(); self.refresh()

    def reset(self): self.backend.reset(); self.speed = 1.0; self.sync_controls(); self.refresh()

    def scenario(self, name): self.backend.select_scenario(name); self.sync_controls(); self.refresh()

    def step(self):
        running = self.backend.running; self.backend.running = True
        self.backend.advance_elapsed(1.0, 1.0, max_steps=20); self.backend.running = running; self.refresh()

    def toggle_freeze(self):
        self.freeze_chart = not self.freeze_chart; self.freeze_button.setText("UNFREEZE" if self.freeze_chart else "FREEZE")

    def clear_events(self):
        self.sim.events.clear(); self.sim.last_event_time.clear(); self.sim.event_snapshot = self.sim.current_event_state(); self.refresh()

    def show_hot(self): self.hot.show(); self.hot.raise_(); self.hot.activateWindow(); self.hot.refresh(self.sim)

    def show_summary(self):
        s = self.state
        text = (f"Scenario: {s.scenario_name}\nSimulation time: {s.t:.2f} s\nPower: {100*s.n:.2f} %\nPressure: {s.P:.3f} MPa\nInventory: {100*s.M:.2f} %\nVoid fraction: {100*s.void_fraction:.2f} %\nFuel / clad / coolant: {s.Tf:.1f} / {s.Tcl:.1f} / {s.Tc:.1f} °C\nBoiling regime: {s.boiling_regime}\nCHF ratio: {s.chf_ratio:.3f}\nRecorded events: {len(self.sim.events)}")
        QMessageBox.information(self, "Scenario Summary", text)

    def export_csv(self, path=None):
        if not path:
            default = Path.cwd() / "exports" / f"thermal_hydraulics_{datetime.now():%Y%m%d_%H%M%S}.csv"
            path, _ = QFileDialog.getSaveFileName(self, "Export simulation history", str(default), "CSV files (*.csv)")
        if not path: return
        path = Path(path).with_suffix(".csv"); path.parent.mkdir(parents=True, exist_ok=True)
        columns = ("t", "pow", "dec", "Tf", "Tcl", "Tc", "P", "M", "void", "flow", "rho", "hot_clad")
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream); writer.writerow(columns); writer.writerows(zip(*(getattr(self.state.hist, name) for name in columns)))
        self.sim.record_event("CSV", f"Exported history to {path.name}"); self.refresh()

    def closeEvent(self, event): self.hot.close(); super().closeEvent(event)

    def tick(self):
        now = time.perf_counter(); elapsed = min(now-self.last_tick, .1); self.last_tick = now
        self.steps += self.backend.advance_elapsed(elapsed, self.speed)
        if now-self.last_perf >= 1:
            span = now-self.last_perf; self.steps_s, self.refresh_hz = self.steps/span, self.refreshes/span
            self.steps = self.refreshes = 0; self.last_perf = now

    @staticmethod
    def finite(value, fallback=0.0): return float(value) if np.isfinite(value) else fallback

    def refresh(self):
        began = time.perf_counter(); self.refreshes += 1
        s, h = self.state, self.state.hist; status = "RUNNING" if self.backend.running else "PAUSED"
        if s.trip: status = "TRIP / " + status
        self.status.setText(f"STATUS: {status} | {s.scenario_name} | SIM TIME {s.t:07.2f} s")
        self.demo_button.setText("STOP DEMO" if self.backend.demo_mode else "START DEMO")
        self.demo_stage.setText(self.sim.demo_stage or "Manual control")
        self.perf.setText(f"UI {self.refresh_hz:4.1f} Hz | Physics {self.steps_s:6.0f} steps/s | Refresh {self.ui_ms:5.2f} ms")
        decay, flow, rho = (h.dec[-1] if h.dec else 6.5), (h.flow[-1] if h.flow else 100), (h.rho[-1] if h.rho else 0)
        dnbr = self.finite(s.hot_min_dnbr, float("nan")); dnbr_text = "unavailable" if not np.isfinite(dnbr) else f"{dnbr:.2f}"
        event = "None" if not self.sim.events else f"{self.sim.events[-1].category}: {self.sim.events[-1].message}"
        self.readout.setText(f"Power / decay: {100*s.n:7.2f} / {decay:6.2f} %\nPressure: {s.P:7.2f} MPa\nInventory / void: {100*s.M:6.1f} / {100*s.void_fraction:5.1f} %\nFuel / clad / coolant: {s.Tf:6.0f} / {s.Tcl:6.0f} / {s.Tc:6.1f} °C\nEffective flow: {flow:6.1f} %\nReactivity: {rho:+7.0f} pcm\nBoiling: {s.boiling_regime}\nCHF ratio / axial MDNBR: {s.chf_ratio:.2f} / {dnbr_text}\nLatest event: {event}")
        self.events.setPlainText("\n".join(f"{item.time_s:7.1f} s  {item.category:<10}  {item.message}" for item in self.sim.events))
        metrics = (("power",100*s.n,150,"%"),("inventory",100*s.M,120,"%"),("pressure",s.P,18," MPa"),("clad",s.Tcl,1200," °C"),("dnbr",min(dnbr,3) if np.isfinite(dnbr) else 0,3,""))
        for key, value, maximum, unit in metrics:
            self.bars[key].setValue(round(1000*min(max(value/maximum,0),1))); self.bars[key].setFormat(f"{value:7.2f}{unit}" if np.isfinite(value) else "unavailable")
        alarms = []
        if s.trip: alarms.append("REACTOR TRIP")
        if self.sim.eccs_is_active(): alarms.append("ECCS ACTIVE")
        if s.M < self.sim.c.invLow: alarms.append("LOW INVENTORY")
        if s.Tcl > self.sim.c.cladWarn: alarms.append("HIGH CLAD TEMP")
        if s.chf_ratio >= 1: alarms.append("CHF EXCEEDED")
        self.alarms.setText(" | ".join(alarms) if alarms else "No active protection alarms")
        self.mimic.refresh(self.sim); self.sync_controls()
        if h.t and not self.freeze_chart:
            x = np.asarray(h.t)[-self.PLOT_POINTS:]; count = len(x)
            self.power.setData(x, np.asarray(h.pow)[-count:]); self.decay.setData(x, np.asarray(h.dec)[-count:])
            self.fuel.setData(x, np.asarray(h.Tf)[-count:]); self.clad.setData(x, np.asarray(h.Tcl)[-count:]); self.cool.setData(x, np.asarray(h.Tc)[-count:]); self.hot_clad.setData(x, np.asarray(h.hot_clad)[-count:])
            self.pressure.setData(x, np.asarray(h.P)[-count:]); self.inventory.setData(x, np.asarray(h.M)[-count:]/10); self.void.setData(x, np.asarray(h.void)[-count:]/10)
            limits = max(0, x[-1]-40), max(40, x[-1])
            for plot in (self.power_plot, self.temp_plot, self.pressure_plot):
                if not plot.user_scaled: plot.setXRange(*limits, padding=0)
            if not self.power_plot.user_scaled: self.power_plot.setYRange(0, max(120, 1.15*max(h.pow)), padding=0)
            if not self.temp_plot.user_scaled: self.temp_plot.setYRange(0, min(2300, max(1000, 1.1*max(h.Tf))), padding=0)
            if not self.pressure_plot.user_scaled: self.pressure_plot.setYRange(0, 18, padding=0)
        if self.hot.isVisible(): self.hot.refresh(self.sim)
        self.ui_ms = (time.perf_counter()-began)*1000


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--model-dir", type=Path)
    args = parser.parse_args(); app = QApplication(sys.argv[:1]); window = MainWindow(args.model_dir); window.show(); raise SystemExit(app.exec())


if __name__ == "__main__": main()
