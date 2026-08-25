"""Canonical Dear PyGui UI for the OpenNuclearSuite thermal-hydraulics model."""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from types import MethodType

import numpy as np

from thermal_hydraulics_gui_backend import ThermalHydraulicsGUIBackend

try:
    import dearpygui.dearpygui as dpg
except ImportError as exc:
    raise SystemExit("Dear PyGui is missing. Run: pip install dearpygui") from exc


DEFAULT_MODEL_DIR = Path(__file__).resolve().parent


class Value:
    """Minimal Tk variable-compatible value used by the unchanged model."""

    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def build_headless_model(model_dir: Path):
    model_dir = model_dir.resolve()
    if not getattr(sys, "frozen", False) and not (model_dir / "thermal_hydraulics_simulator.py").exists():
        raise SystemExit(f"Thermal-hydraulics model not found in: {model_dir}")
    sys.path.insert(0, str(model_dir))
    import thermal_hydraulics_simulator as th

    sim = th.LWRTeachingSimulator.__new__(th.LWRTeachingSimulator)
    sim.c = th.Constants()
    sim.state = th.State(sim.c)
    sim.steam_tables = th.SteamTables()
    sim.physics = th.ThermalHydraulicsEngine(sim.c, sim.steam_tables)
    sim.hot_channel = th.HotChannelModel(sim.steam_tables)
    sim.hot_channel_result = None
    sim.hot_channel_result_time = float("nan")
    sim.hot_channel_error = None
    sim.hot_channel_update_interval_s = 0.25
    sim.hot_flux_reference_max_MW_m2 = 6.0
    sim.hot_dnbr_reference_max = 6.0
    defaults = {
        "rod": 0.0, "trim": 0.0, "boron": 1000.0, "pump": 100.0,
        "sg": 100.0, "break": 0.0, "eccs": 0.0, "afw": 0.0,
        "porv": 0.0, "spray": 0.0, "heater": 0.0, "rhr": 0.0,
        "noise": 2.0, "speed": 1.0,
    }
    sim.control_vars = {key: Value(value) for key, value in defaults.items()}
    sim.auto_eccs_var = Value(True)
    sim.auto_trip_var = Value(True)
    sim.hot_channel_coupling_var = Value(True)
    sim.events = deque(maxlen=250)
    sim.event_snapshot = {}
    sim.last_event_time = {}
    sim.demo_stage = ""
    sim.csv_logging = False
    sim.csv_writer = sim.csv_file = None
    sim.csv_last_logged_t = -1.0e9

    def set_slider(self, key, value):
        self.control_vars[key].set(float(value))

    sim.set_slider = MethodType(set_slider, sim)
    sim.reset_event_timeline()
    return sim


SCENARIOS = {
    "NORMAL": ("Normal operation", False, True, {"rod": 0, "trim": 0, "boron": 1000, "pump": 100, "sg": 100, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "SBLOCA": ("Small-break LOCA", True, True, {"rod": 100, "trim": 0, "pump": 60, "sg": 100, "break": 12, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LBLOCA": ("Large-break LOCA", True, True, {"rod": 100, "trim": 0, "pump": 0, "sg": 60, "break": 70, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LOFA": ("Loss of flow accident", True, True, {"rod": 100, "trim": 0, "pump": 0, "sg": 100, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LOHS": ("Loss of heat sink", True, True, {"rod": 100, "trim": 0, "pump": 80, "sg": 0, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "SBO": ("Station blackout", True, False, {"rod": 100, "trim": 0, "pump": 0, "sg": 8, "break": 0, "eccs": 0, "afw": 10, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
}


class ThermalHydraulicsDPG:
    PLOT_POINTS = 1000
    DT = 0.05

    def __init__(self, model_dir: Path):
        self.backend = ThermalHydraulicsGUIBackend(model_dir)
        self.model_dir = self.backend.model_dir
        self.sim = self.backend.sim
        self.speed = 1.0
        self.last_frame = time.perf_counter()
        self.last_ui = 0.0
        self.last_perf = self.last_frame
        self.frames = self.steps = 0
        self.fps = self.steps_s = self.ui_ms = 0.0
        self.syncing = False
        self.splash_until = None
        self.image_sizes = {}
        self.freeze_chart = False
        self.hot_axes_fitted = False

    def load_texture(self, tag, path):
        if not path.exists():
            return False
        width, height, _channels, data = dpg.load_image(str(path))
        dpg.add_static_texture(width, height, data, tag=tag, parent="textures")
        self.image_sizes[tag] = (width, height)
        return True

    def show_about(self):
        dpg.configure_item("about_window", show=True)

    def step(self):
        was_running = self.backend.running
        self.backend.running = True
        self.backend.advance_elapsed(1.0, 1.0, max_steps=20)
        self.backend.running = was_running
        self.refresh_ui()

    def toggle_freeze(self):
        self.freeze_chart = not self.freeze_chart
        dpg.configure_item("freeze_button", label="UNFREEZE" if self.freeze_chart else "FREEZE")

    def clear_events(self):
        self.sim.events.clear()
        self.sim.last_event_time.clear()
        self.sim.event_snapshot = self.sim.current_event_state()
        self.refresh_ui()

    def show_summary(self):
        s = self.s
        text = (f"Scenario: {s.scenario_name}\nSimulation time: {s.t:.2f} s\n"
                f"Power: {100*s.n:.2f} %\nPressure: {s.P:.3f} MPa\n"
                f"Inventory: {100*s.M:.2f} %\nVoid fraction: {100*s.void_fraction:.2f} %\n"
                f"Fuel / clad / coolant: {s.Tf:.1f} / {s.Tcl:.1f} / {s.Tc:.1f} °C\n"
                f"Boiling regime: {s.boiling_regime}\nCHF ratio: {s.chf_ratio:.3f}\n"
                f"Recorded events: {len(self.sim.events)}")
        dpg.set_value("summary_text", text)
        dpg.configure_item("summary_window", show=True)

    def show_hot_channel(self):
        dpg.configure_item("hot_window", show=True)
        dpg.focus_item("hot_window")
        self.hot_axes_fitted = False
        self.refresh_hot_channel()

    def refresh_hot_channel(self):
        if not dpg.does_item_exist("hot_window") or not dpg.is_item_shown("hot_window"):
            return
        result, s = self.sim.hot_channel_result, self.s
        if result is None:
            dpg.set_value("hot_summary", f"Hot-channel calculation unavailable: {self.sim.hot_channel_error or 'awaiting a valid model state'}")
            return
        dnbr_index = result.minimum_dnbr_index
        dnbr_text = "unavailable" if dnbr_index is None else f"{result.minimum_dnbr:.2f} at z={result.z_m[dnbr_index]:.2f} m"
        warning = f" Warning: {result.phase_warning}" if result.phase_warning else ""
        dpg.set_value("hot_summary", f"{result.z_m.size}-node representative channel | Peak fuel {s.hot_peak_fuel_C:.1f} °C | Peak clad {s.hot_peak_clad_C:.1f} °C | Outlet {s.hot_outlet_C:.1f} °C | Minimum W-3 DNBR {dnbr_text}.{warning}")
        z = result.z_m.tolist()
        for tag, values in (("hot_fuel_series", result.fuel_centerline_temperature_C), ("hot_clad_series_axial", result.clad_surface_temperature_C), ("hot_bulk_series", result.bulk_temperature_C), ("hot_sat_series", result.saturation_temperature_C), ("hot_flux_series", result.surface_heat_flux_W_m2 / 1e6), ("hot_chf_series", result.critical_heat_flux_W_m2 / 1e6), ("hot_dnbr_series", result.dnbr)):
            dpg.set_value(tag, [z, np.asarray(values).tolist()])
        h = s.hist
        times = list(h.t)
        for tag, values in (("hot_trend_fuel", h.hot_fuel), ("hot_trend_clad", h.hot_clad), ("hot_trend_outlet", h.hot_outlet)):
            dpg.set_value(tag, [times, list(values)])
        self.set_padded_axis_limits("hot_temp_y", result.fuel_centerline_temperature_C, minimum_span=100.0)
        coolant_temperatures = np.concatenate((result.clad_surface_temperature_C, result.bulk_temperature_C, result.saturation_temperature_C))
        self.set_padded_axis_limits("hot_temp_y_right", coolant_temperatures, minimum_span=40.0)
        dpg.set_axis_limits("hot_temp_x", float(result.z_m[0]), float(result.z_m[-1]))
        if times:
            xmax = max(40.0, float(times[-1]))
            xmin = max(0.0, xmax - 40.0)
            dpg.set_axis_limits("hot_trend_x", xmin, xmax)
            self.set_padded_axis_limits("hot_trend_y", h.hot_fuel, minimum_span=100.0)
            self.set_padded_axis_limits("hot_trend_y_right", list(h.hot_clad) + list(h.hot_outlet), minimum_span=40.0)
        if not self.hot_axes_fitted:
            for axis_tag in ("hot_flux_x", "hot_flux_y"):
                dpg.fit_axis_data(axis_tag)
            self.hot_axes_fitted = True
        rows = ["Node | z (m) | P (MPa) | h (kJ/kg) | Coolant C | Clad C | Fuel C | Quality | Eq. quality | q MW/m² | CHF MW/m² | DNBR"]
        for i, z_value in enumerate(result.z_m):
            quality = "--" if np.isnan(result.quality[i]) else f"{result.quality[i]:.4f}"
            chf = result.critical_heat_flux_W_m2[i] / 1e6
            dnbr = result.dnbr[i]
            rows.append(f"{i+1:4d} | {z_value:5.3f} | {result.pressure_mpa[i]:7.3f} | {result.enthalpy_kj_kg[i]:9.2f} | {result.bulk_temperature_C[i]:9.2f} | {result.clad_surface_temperature_C[i]:6.2f} | {result.fuel_centerline_temperature_C[i]:6.2f} | {quality:>7} | {result.equilibrium_quality[i]:10.4f} | {result.surface_heat_flux_W_m2[i]/1e6:7.3f} | {chf:8.3f} | {'--' if np.isnan(dnbr) else f'{dnbr:.3f}'}")
        dpg.set_value("hot_node_table", "\n".join(rows))

    @staticmethod
    def set_padded_axis_limits(axis_tag, values, minimum_span):
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        if not finite.size:
            return
        low, high = float(np.min(finite)), float(np.max(finite))
        span = max(high - low, float(minimum_span))
        midpoint = 0.5 * (low + high)
        padding = 0.08 * span
        dpg.set_axis_limits(axis_tag, midpoint - 0.5 * span - padding, midpoint + 0.5 * span + padding)

    def export_csv(self, path=None):
        if path is None:
            export_dir = Path.cwd() / "exports"
            export_dir.mkdir(exist_ok=True)
            path = export_dir / f"thermal_hydraulics_{datetime.now():%Y%m%d_%H%M%S}.csv"
        path = Path(path).with_suffix(".csv")
        h = self.s.hist
        columns = ("t", "pow", "dec", "Tf", "Tcl", "Tc", "P", "M", "void", "flow", "rho", "hot_clad")
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
            writer.writerows(zip(*(getattr(h, name) for name in columns)))
        self.sim.record_event("CSV", f"Exported history to {path.name}")
        self.refresh_ui()

    def export_dialog_callback(self, sender, app_data, user_data=None):
        if app_data and app_data.get("file_path_name"):
            self.export_csv(app_data["file_path_name"])

    @property
    def s(self):
        return self.sim.state

    def set_control(self, key):
        def callback(sender, value, user_data=None):
            if not self.syncing:
                self.backend.set_control(key, value)
        return callback

    def set_bool(self, name):
        def callback(sender, value, user_data=None):
            key = {"auto_eccs_var": "eccs", "auto_trip_var": "trip", "hot_channel_coupling_var": "hot_channel"}[name]
            self.backend.set_automatic(key, value)
        return callback

    def start(self):
        self.backend.start()

    def pause(self):
        self.backend.pause()

    def scram(self):
        self.backend.scram()
        self.sync_controls()

    def reset(self):
        self.backend.reset()
        self.sim = self.backend.sim
        self.sync_controls()
        self.refresh_ui()

    def scenario(self, name):
        self.backend.select_scenario(name)
        self.sync_controls()
        self.refresh_ui()

    def build(self):
        dpg.create_context()
        with dpg.texture_registry(tag="textures"):
            pass
        regular_font, bold_font = Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf")
        with dpg.font_registry():
            if regular_font.exists():
                dpg.add_font(str(regular_font), 14, tag="font_regular")
                dpg.add_font(str(regular_font), 16, tag="font_small")
            if bold_font.exists(): dpg.add_font(str(bold_font), 23, tag="font_header")
        dpg.create_viewport(title="Thermal-Hydraulics and LOCA Teaching Simulator", width=1520, height=920)
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (12, 17, 23))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (17, 24, 32))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (27, 38, 49))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (29, 78, 112))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 4)
        with dpg.theme() as splash_theme:
            with dpg.theme_component(dpg.mvWindowAppItem):
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)

        with dpg.window(tag="primary", label="Thermal-Hydraulics Simulator", no_close=True, no_collapse=True):
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingFixedFit, borders_innerV=False):
                dpg.add_table_column(init_width_or_weight=520)
                dpg.add_table_column(init_width_or_weight=105)
                dpg.add_table_column(init_width_or_weight=850)
                with dpg.table_row():
                    with dpg.group(indent=17):
                        title = dpg.add_text("LIGHT WATER REACTOR\nTHERMAL-HYDRAULICS TRAINING PANEL", color=(238, 245, 251))
                        subtitle = dpg.add_text("Open Nuclear Engineering Teaching Suite", color=(174, 189, 202))
                        if dpg.does_item_exist("font_header"): dpg.bind_item_font(title, "font_header")
                        if dpg.does_item_exist("font_small"): dpg.bind_item_font(subtitle, "font_small")
                    dpg.add_button(label="ABOUT", callback=lambda *args: self.show_about(), width=82, height=32)
                    if dpg.does_item_exist("banner_texture"): dpg.add_image("banner_texture", width=850, height=85)
            dpg.add_separator()
            with dpg.table(header_row=True, policy=dpg.mvTable_SizingStretchProp, borders_innerV=True, borders_outerH=True, borders_outerV=True):
                dpg.add_table_column(label="SIMULATION", init_width_or_weight=5)
                dpg.add_table_column(label="SCENARIO PRESETS", init_width_or_weight=6)
                dpg.add_table_column(label="ANALYSIS AND OUTPUT", init_width_or_weight=4)
                with dpg.table_row():
                    with dpg.group(horizontal=True):
                        for label, action in (("START", self.start), ("PAUSE", self.pause), ("SCRAM", self.scram), ("RESET", self.reset)):
                            dpg.add_button(label=label, width=76, callback=lambda *args, fn=action: fn())
                        dpg.add_button(label="STEP 1 s", width=82, callback=lambda *args: self.step())
                        dpg.add_button(label="FREEZE", tag="freeze_button", width=82, callback=lambda *args: self.toggle_freeze())
                    with dpg.group(horizontal=True):
                        for name in SCENARIOS:
                            dpg.add_button(label=name, width=68, callback=lambda *args, n=name: self.scenario(n))
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="EXPORT CSV", width=92, callback=lambda *args: dpg.configure_item("export_dialog", show=True))
                        dpg.add_button(label="HOT CHANNEL", width=105, callback=lambda *args: self.show_hot_channel())
                        dpg.add_button(label="SUMMARY", width=82, callback=lambda *args: self.show_summary())
            with dpg.group(horizontal=True):
                dpg.add_text("STATUS: PAUSED", tag="status", color=(90, 220, 140))
                dpg.add_spacer(width=24)
                dpg.add_text("Render -- | Physics -- | UI --", tag="perf", color=(90, 200, 255))

            with dpg.group(horizontal=True):
                with dpg.child_window(tag="operator_pane", width=390, height=-1, border=True, horizontal_scrollbar=True, resizable_x=True, no_scrollbar=False):
                    dpg.add_text("CORE / PRIMARY CONTROLS", color=(110, 205, 255))
                    self.slider("rod", "Rod insertion %", 0, 100)
                    self.slider("trim", "Fine reactivity pcm", -500, 500)
                    self.slider("boron", "Soluble boron ppm", 0, 2500)
                    self.slider("pump", "Primary pump %", 0, 120)
                    self.slider("sg", "SG heat removal %", 0, 140)
                    self.slider("break", "LOCA break size %", 0, 100)
                    dpg.add_separator()
                    dpg.add_text("SAFETY / SUPPORT", color=(255, 190, 70))
                    self.slider("eccs", "Manual ECCS %", 0, 100)
                    self.slider("afw", "Auxiliary feedwater %", 0, 100)
                    self.slider("porv", "PORV / relief %", 0, 100)
                    self.slider("spray", "Pressurizer spray %", 0, 100)
                    self.slider("heater", "Pressurizer heater %", 0, 100)
                    self.slider("rhr", "RHR cooldown %", 0, 100)
                    self.slider("noise", "Instrument noise %", 0, 10)
                    dpg.add_slider_float(label="Simulation speed", tag="speed", min_value=0.2, max_value=20, default_value=1, format="%.1fx", callback=self.speed_cb)
                    dpg.add_checkbox(label="Auto ECCS logic", tag="auto_eccs", default_value=True, callback=self.set_bool("auto_eccs_var"))
                    dpg.add_checkbox(label="Auto reactor trip", tag="auto_trip", default_value=True, callback=self.set_bool("auto_trip_var"))
                    dpg.add_checkbox(label="Couple axial hot channel", tag="hot_coupling", default_value=True, callback=self.set_bool("hot_channel_coupling_var"))
                    dpg.add_separator()
                    dpg.add_text("LIVE READOUT", color=(110, 205, 255))
                    dpg.add_text("", tag="readout", wrap=325)
                    dpg.add_separator()
                    with dpg.group(horizontal=True):
                        dpg.add_text("EVENT TIMELINE", color=(110, 205, 255))
                        dpg.add_button(label="CLEAR", callback=lambda *args: self.clear_events())
                    dpg.add_input_text(tag="event_timeline", multiline=True, readonly=True, width=-1, height=180)
                    dpg.add_spacer(height=80)

                with dpg.child_window(tag="plant_pane", width=1050, height=-1, border=True, horizontal_scrollbar=True, resizable_x=True, no_scrollbar=False):
                    with dpg.group(horizontal=True):
                        with dpg.child_window(width=520, height=265, border=True):
                            dpg.add_text("PRIMARY LOOP / INVENTORY MIMIC", color=(110, 205, 255))
                            dpg.add_drawlist(width=490, height=215, tag="mimic")
                        with dpg.child_window(width=-1, height=265, border=True):
                            dpg.add_text("PROTECTION AND THERMAL LIMITS", color=(110, 205, 255))
                            for tag, label in (("power_bar", "REACTOR POWER"), ("inventory_bar", "PRIMARY INVENTORY"), ("pressure_bar", "PRESSURE"), ("clad_bar", "CLAD TEMPERATURE"), ("dnbr_bar", "AXIAL DNBR MARGIN")):
                                dpg.add_text(label)
                                dpg.add_progress_bar(tag=tag, default_value=0, overlay="--", width=-1)
                            dpg.add_text("", tag="alarms", wrap=500)

                    with dpg.tab_bar():
                        with dpg.tab(label="Power / decay heat"):
                            self.make_plot("power_plot", "Percent nominal", (("pow_series", "Power %"), ("dec_series", "Decay heat %")))
                        with dpg.tab(label="Temperatures"):
                            self.make_plot("temp_plot", "Temperature (C)", (("fuel_series", "Fuel"), ("clad_series", "Clad"), ("cool_series", "Coolant"), ("hot_clad_series", "Axial peak clad")))
                        with dpg.tab(label="Pressure / inventory"):
                            self.make_plot("pressure_plot", "MPa / scaled inventory", (("pressure_series", "Pressure MPa"), ("inventory_series", "Inventory / 10"), ("void_series", "Void / 10")))

        about_message = """Open Nuclear Engineering Teaching Suite

Interactive desktop simulators for teaching reactor physics, kinetics,
thermal-hydraulics, LOCA behavior, and core loading concepts.

Author and maintainer: maxisnote20
Email: maxisnote20@gmail.com
Repository: https://github.com/open-nuclear-suite/OpenNuclearSuite

This software is intended for education and demonstration. It must not be
used for reactor design, licensing, safety analysis, or plant operation."""
        with dpg.window(tag="about_window", label="About — Open Nuclear Engineering Teaching Suite", show=False, modal=True, width=720, height=650):
            dpg.add_input_text(default_value=about_message, multiline=True, readonly=True, width=-1, height=560)
            dpg.add_button(label="CLOSE", callback=lambda *args: dpg.configure_item("about_window", show=False))
        with dpg.window(tag="summary_window", label="Scenario Summary", show=False, width=620, height=430):
            dpg.add_input_text(tag="summary_text", multiline=True, readonly=True, width=-1, height=350)
            dpg.add_button(label="CLOSE", callback=lambda *args: dpg.configure_item("summary_window", show=False))
        with dpg.window(tag="hot_window", label="Representative 1-D Hot Channel", show=False, width=1180, height=820, no_collapse=False, no_resize=False, horizontal_scrollbar=True):
            dpg.add_text("Calculating hot channel...", tag="hot_summary", wrap=1120, color=(220, 235, 245))
            with dpg.tab_bar():
                with dpg.tab(label="Axial temperatures"):
                    with dpg.plot(label="Axial hot-channel temperatures", height=500, width=-1, anti_aliased=False):
                        dpg.add_plot_legend()
                        dpg.add_plot_axis(dpg.mvXAxis, label="Distance from channel inlet (m)", tag="hot_temp_x")
                        fuel_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Fuel centre (°C)", tag="hot_temp_y")
                        coolant_axis = dpg.add_plot_axis(dpg.mvYAxis2, label="Clad / coolant / saturation (°C)", tag="hot_temp_y_right")
                        dpg.add_line_series([], [], label="Fuel centre", parent=fuel_axis, tag="hot_fuel_series")
                        for tag, label in (("hot_clad_series_axial", "Clad surface"), ("hot_bulk_series", "Bulk coolant"), ("hot_sat_series", "Saturation temperature")):
                            dpg.add_line_series([], [], label=label, parent=coolant_axis, tag=tag)
                with dpg.tab(label="CHF and DNBR"):
                    with dpg.plot(label="Local heat flux, W-3 CHF, and DNBR", height=500, width=-1, anti_aliased=False):
                        dpg.add_plot_legend()
                        dpg.add_plot_axis(dpg.mvXAxis, label="Distance from channel inlet (m)", tag="hot_flux_x")
                        axis = dpg.add_plot_axis(dpg.mvYAxis, label="Heat flux (MW/m²) / DNBR", tag="hot_flux_y")
                        dpg.add_line_series([], [], label="Actual heat flux", parent=axis, tag="hot_flux_series")
                        dpg.add_line_series([], [], label="W-3 CHF", parent=axis, tag="hot_chf_series")
                        dpg.add_line_series([], [], label="DNBR", parent=axis, tag="hot_dnbr_series")
                with dpg.tab(label="Transient trends"):
                    with dpg.plot(label="Transient hot-channel response", height=500, width=-1, anti_aliased=False):
                        dpg.add_plot_legend()
                        dpg.add_plot_axis(dpg.mvXAxis, label="Simulation time (s)", tag="hot_trend_x")
                        fuel_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Peak fuel centre (°C)", tag="hot_trend_y")
                        coolant_axis = dpg.add_plot_axis(dpg.mvYAxis2, label="Peak clad / outlet (°C)", tag="hot_trend_y_right")
                        dpg.add_line_series([], [], label="Peak fuel centre", parent=fuel_axis, tag="hot_trend_fuel")
                        dpg.add_line_series([], [], label="Peak clad surface", parent=coolant_axis, tag="hot_trend_clad")
                        dpg.add_line_series([], [], label="Coolant outlet", parent=coolant_axis, tag="hot_trend_outlet")
                with dpg.tab(label="Axial node data"):
                    dpg.add_input_text(tag="hot_node_table", multiline=True, readonly=True, width=1450, height=520)
            dpg.add_button(label="CLOSE", callback=lambda *args: dpg.configure_item("hot_window", show=False))
        with dpg.file_dialog(tag="export_dialog", show=False, modal=True, directory_selector=False, callback=self.export_dialog_callback, default_path=str(Path.cwd()), default_filename=f"thermal_hydraulics_{datetime.now():%Y%m%d_%H%M%S}.csv", width=760, height=460):
            dpg.add_file_extension(".csv", color=(100, 220, 140))
            dpg.add_file_extension(".*")
        if dpg.does_item_exist("splash_texture"):
            window_width, window_height = 790, 387
            with dpg.window(tag="startup_splash", no_title_bar=True, no_resize=True, no_move=True, modal=True, width=window_width, height=window_height):
                with dpg.drawlist(width=790, height=387):
                    dpg.draw_rectangle((0, 0), (789, 386), color=(125, 18, 56), fill=(15, 19, 25), thickness=2)
                    dpg.draw_image("splash_texture", (36, 24), (756, 265))
                    dpg.draw_text((172, 292), "Open Nuclear Engineering Teaching Suite", color=(243, 245, 247), size=32)
                    dpg.draw_text((225, 337), "Thermal-Hydraulics and LOCA Teaching Simulator", color=(199, 209, 219), size=20)
            dpg.bind_item_theme("startup_splash", splash_theme)

        dpg.bind_theme(theme)
        if dpg.does_item_exist("font_regular"): dpg.bind_font("font_regular")
        dpg.set_primary_window("primary", True)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        if dpg.does_item_exist("startup_splash"):
            dpg.set_item_pos("startup_splash", ((1520-window_width)//2, (920-window_height)//2))
            self.splash_until = time.perf_counter() + 3.0
        self.sync_controls()
        self.refresh_ui()

    def slider(self, key, label, lo, hi):
        dpg.add_slider_float(label=label, tag=key, min_value=lo, max_value=hi, callback=self.set_control(key))

    def speed_cb(self, sender, value, user_data=None):
        self.speed = float(value)

    def make_plot(self, tag, y_label, series):
        with dpg.plot(tag=tag, height=-1, width=-1, anti_aliased=False):
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label="Simulation time (s)", tag=f"{tag}_x")
            y = dpg.add_plot_axis(dpg.mvYAxis, label=y_label, tag=f"{tag}_y")
            for series_tag, label in series:
                dpg.add_line_series([], [], label=label, parent=y, tag=series_tag)

    def sync_controls(self):
        self.syncing = True
        try:
            for key, var in self.sim.control_vars.items():
                if dpg.does_item_exist(key):
                    dpg.set_value(key, var.get())
            dpg.set_value("auto_eccs", bool(self.sim.auto_eccs_var.get()))
            dpg.set_value("auto_trip", bool(self.sim.auto_trip_var.get()))
            dpg.set_value("hot_coupling", bool(self.sim.hot_channel_coupling_var.get()))
        finally:
            self.syncing = False

    @staticmethod
    def finite(value, fallback=0.0):
        return float(value) if np.isfinite(value) else fallback

    def draw_mimic(self):
        s = self.s
        dpg.delete_item("mimic", children_only=True)
        coolant = (35, 155, 245, 255) if s.M > 0.65 else (255, 95, 35, 255)
        dpg.draw_rectangle((40, 35), (170, 190), color=(160, 175, 185), fill=(28, 38, 48), thickness=3, parent="mimic")
        level_y = 183 - 140 * min(max(s.M, 0), 1)
        dpg.draw_rectangle((50, level_y), (160, 180), color=coolant, fill=(*coolant[:3], 75), parent="mimic")
        dpg.draw_text((72, 91), "CORE", color=(240, 240, 245), size=22, parent="mimic")
        dpg.draw_line((170, 60), (280, 60), color=coolant, thickness=10, parent="mimic")
        dpg.draw_line((280, 60), (280, 170), color=coolant, thickness=10, parent="mimic")
        dpg.draw_line((280, 170), (170, 170), color=coolant, thickness=10, parent="mimic")
        dpg.draw_circle((365, 115), 55, color=(150, 170, 185), fill=(28, 38, 48), thickness=3, parent="mimic")
        dpg.draw_text((325, 102), "STEAM\nGEN.", color=(240, 240, 245), size=18, parent="mimic")
        dpg.draw_line((280, 60), (335, 75), color=coolant, thickness=10, parent="mimic")
        dpg.draw_line((335, 155), (280, 170), color=coolant, thickness=10, parent="mimic")
        dpg.draw_text((8, 5), f"{s.P:5.2f} MPa   {100*s.M:5.1f}% inventory   {100*s.void_fraction:4.1f}% void", color=(120, 220, 255), size=16, parent="mimic")
        if self.sim.eccs_is_active():
            dpg.draw_line((105, 15), (105, 35), color=(70, 255, 120), thickness=8, parent="mimic")
            dpg.draw_text((118, 15), "ECCS", color=(70, 255, 120), size=16, parent="mimic")
        if self.sim.control_vars["break"].get() > 0:
            dpg.draw_line((190, 170), (210, 205), color=(255, 80, 35), thickness=6, parent="mimic")
            dpg.draw_text((215, 184), "BREAK", color=(255, 90, 40), size=16, parent="mimic")

    def refresh_ui(self):
        began = time.perf_counter()
        s, h = self.s, self.s.hist
        status = "RUNNING" if self.backend.running else "PAUSED"
        if s.trip:
            status = "TRIP / " + status
        dpg.set_value("status", f"STATUS: {status} | {s.scenario_name} | SIM TIME {s.t:07.2f} s")
        dpg.set_value("perf", f"Render {self.fps:5.1f} FPS | Physics {self.steps_s:6.0f} steps/s | UI {self.ui_ms:5.2f} ms")
        decay = h.dec[-1] if h.dec else 6.5
        flow = h.flow[-1] if h.flow else 100.0
        rho = h.rho[-1] if h.rho else 0.0
        dnbr = self.finite(s.hot_min_dnbr, float("nan"))
        dnbr_text = "unavailable" if not np.isfinite(dnbr) else f"{dnbr:.2f}"
        event = "None" if not self.sim.events else f"{self.sim.events[-1].category}: {self.sim.events[-1].message}"
        timeline = "\n".join(f"{item.time_s:7.1f} s  {item.category:<10}  {item.message}" for item in self.sim.events)
        dpg.set_value("event_timeline", timeline)
        dpg.set_value("readout", f"Power / decay: {100*s.n:7.2f} / {decay:6.2f} %\nPressure: {s.P:7.2f} MPa\nInventory / void: {100*s.M:6.1f} / {100*s.void_fraction:5.1f} %\nFuel / clad / coolant: {s.Tf:6.0f} / {s.Tcl:6.0f} / {s.Tc:6.1f} C\nEffective flow: {flow:6.1f} %\nReactivity: {rho:+7.0f} pcm\nBoiling: {s.boiling_regime}\nCHF ratio / axial MDNBR: {s.chf_ratio:.2f} / {dnbr_text}\nLatest event: {event}")
        metrics = (("power_bar", 100*s.n, 150, "%"), ("inventory_bar", 100*s.M, 120, "%"), ("pressure_bar", s.P, 18, " MPa"), ("clad_bar", s.Tcl, 1200, " C"), ("dnbr_bar", min(dnbr, 3.0) if np.isfinite(dnbr) else 0, 3, ""))
        for tag, value, maximum, unit in metrics:
            dpg.set_value(tag, min(max(value / maximum, 0), 1))
            dpg.configure_item(tag, overlay=f"{value:7.2f}{unit}" if np.isfinite(value) else "unavailable")
        alarms = []
        if s.trip: alarms.append("REACTOR TRIP")
        if self.sim.eccs_is_active(): alarms.append("ECCS ACTIVE")
        if s.M < self.sim.c.invLow: alarms.append("LOW INVENTORY")
        if s.Tcl > self.sim.c.cladWarn: alarms.append("HIGH CLAD TEMP")
        if s.chf_ratio >= 1: alarms.append("CHF EXCEEDED")
        dpg.set_value("alarms", " | ".join(alarms) if alarms else "No active protection alarms")

        if h.t and not self.freeze_chart:
            x = list(h.t)[-self.PLOT_POINTS:]
            mapping = (("pow_series", h.pow), ("dec_series", h.dec), ("fuel_series", h.Tf), ("clad_series", h.Tcl), ("cool_series", h.Tc), ("hot_clad_series", h.hot_clad), ("pressure_series", h.P), ("inventory_series", [v/10 for v in h.M]), ("void_series", [v/10 for v in h.void]))
            for tag, values in mapping:
                dpg.set_value(tag, [x, list(values)[-len(x):]])
            xmin, xmax = max(0, x[-1]-40), max(40, x[-1])
            for plot in ("power_plot", "temp_plot", "pressure_plot"):
                dpg.set_axis_limits(f"{plot}_x", xmin, xmax)
            dpg.set_axis_limits("power_plot_y", 0, max(120, 1.15*max(h.pow)))
            dpg.set_axis_limits("temp_plot_y", 0, min(2300, max(1000, 1.1*max(h.Tf))))
            dpg.set_axis_limits("pressure_plot_y", 0, 18)
        self.draw_mimic()
        self.sync_controls()
        self.refresh_hot_channel()
        self.ui_ms = (time.perf_counter() - began) * 1000

    def run(self):
        self.build()
        while dpg.is_dearpygui_running():
            now = time.perf_counter()
            if self.splash_until is not None and now >= self.splash_until:
                if dpg.does_item_exist("startup_splash"):
                    dpg.delete_item("startup_splash")
                self.splash_until = None
            real_dt = min(now - self.last_frame, 0.1)
            self.last_frame = now
            self.frames += 1
            due = self.backend.advance_elapsed(real_dt, self.speed)
            self.steps += due
            if now - self.last_ui >= 0.10:
                self.refresh_ui()
                self.last_ui = now
            if now - self.last_perf >= 1.0:
                elapsed = now - self.last_perf
                self.fps, self.steps_s = self.frames/elapsed, self.steps/elapsed
                self.frames = self.steps = 0
                self.last_perf = now
            dpg.render_dearpygui_frame()
        dpg.destroy_context()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    args = parser.parse_args()
    ThermalHydraulicsDPG(args.model_dir).run()


if __name__ == "__main__":
    main()
