"""Dear PyGui front end for the canonical OpenNuclearSuite reactor simulator.

This intentionally reuses the validated ReactorModel and replaces only the
Tkinter/Matplotlib presentation and scheduling layer.
"""

from __future__ import annotations

import argparse
import math
import time
from datetime import datetime
from pathlib import Path

try:
    import dearpygui.dearpygui as dpg
except ImportError as exc:
    raise SystemExit("Dear PyGui is missing. Run: pip install dearpygui") from exc


DEFAULT_MODEL_DIR = Path(__file__).resolve().parent


def load_backend(model_dir: Path):
    model_dir = model_dir.resolve()
    if not getattr(sys, "frozen", False) and not (model_dir / "reactor_teaching_simulator.py").exists():
        raise SystemExit(f"Reactor model not found in: {model_dir}")
    import sys
    sys.path.insert(0, str(model_dir))
    from reactor_gui_backend import ReactorGUIBackend
    import reactor_teaching_simulator as canonical

    return ReactorGUIBackend, canonical


class ReactorDPG:
    PLOT_POINTS = 2200
    VISIBLE_WINDOW_S = 40.0

    def __init__(self, backend_cls, canonical):
        self.backend = backend_cls()
        self.model = self.backend.model
        self.canonical = canonical
        self.insertion_fn = canonical.rod_insertion_from_withdrawn
        self.fault_keys = canonical.FAULT_KEYS
        self.speed = 1.0
        self.last_frame = time.perf_counter()
        self.physics_credit = 0.0
        self.last_ui = 0.0
        self.last_perf = self.last_frame
        self.frames = 0
        self.steps = 0
        self.fps = 0.0
        self.steps_per_second = 0.0
        self.ui_update_ms = 0.0
        self.syncing = False
        self.splash_until = None
        self.image_sizes = {}
        self.kinetics_labels = {canonical.kinetics_preset_label(name): name for name in canonical.KINETICS_PRESETS}
        self.xenon_labels = {canonical.xenon_preset_label(name): name for name in canonical.XENON_PRESETS}

    @property
    def s(self):
        return self.model.s

    def start(self):
        self.backend.start()

    def pause(self):
        self.backend.pause()

    def scram(self):
        self.backend.scram()

    def reset(self):
        self.backend.reset()
        self.sync_controls()
        self.refresh_ui(force=True)

    def set_mode(self, sender, value, user_data=None):
        if not self.syncing:
            self.backend.set_mode(value)

    def set_rod(self, sender, value, user_data=None):
        if not self.syncing:
            self.backend.set_rod_insertion(value)

    def set_float(self, attr, scale=1.0):
        def callback(sender, value, user_data=None):
            if not self.syncing:
                self.backend.set_control(attr, float(value) * scale)
        return callback

    def set_speed(self, sender, value, user_data=None):
        self.speed = float(value)

    def toggle_fault(self, attr):
        def callback(sender, value, user_data=None):
            self.backend.toggle_fault(attr, bool(value))
        return callback

    def trim(self, pcm):
        self.backend.trim_reactivity(pcm)
        self.refresh_ui(force=True)

    def step(self):
        self.backend.step()
        self.refresh_ui(force=True)

    def export_csv(self, path=None):
        if path is None:
            export_dir = Path.cwd() / "exports"
            export_dir.mkdir(exist_ok=True)
            path = export_dir / f"reactor_sim_run_{datetime.now():%Y%m%d_%H%M%S}.csv"
        path = Path(path)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        rows = self.backend.export_csv(path)
        self.s.add_log(f"CSV export saved: {rows} rows to {path.name}.")
        self.refresh_ui(force=True)

    def export_dialog_callback(self, sender, app_data, user_data=None):
        filepath = app_data.get("file_path_name") if app_data else None
        if filepath:
            self.export_csv(filepath)

    def load_texture(self, tag, path):
        if not path.exists():
            return False
        width, height, _channels, data = dpg.load_image(str(path))
        dpg.add_static_texture(width, height, data, tag=tag, parent="textures")
        self.image_sizes[tag] = (width, height)
        return True

    def scaled_image_size(self, tag, max_width, max_height):
        width, height = self.image_sizes[tag]
        scale = min(max_width / width, max_height / height, 1.0)
        return int(width * scale), int(height * scale)

    def show_about(self):
        dpg.set_value("about_text", self.canonical.ABOUT_MESSAGE)
        dpg.configure_item("about_window", show=True)

    def show_settings(self):
        if self.s.running:
            self.s.add_log("Pause required before changing pedagogical settings.")
            self.refresh_ui(force=True)
            return
        settings = self.s.pedagogical_settings
        for tag, value in (
            ("settings_kinetics", self.canonical.kinetics_preset_label(settings.kinetics_preset)),
            ("settings_xenon", self.canonical.xenon_preset_label(settings.xenon_preset)),
            ("settings_load", settings.load_follow_period_s),
            ("settings_profile", settings.physics_profile),
            ("settings_initial", settings.initial_condition),
            ("settings_cycle", settings.cycle_preset),
        ):
            dpg.set_value(tag, value)
        self.update_settings_availability()
        dpg.configure_item("settings_window", show=True)

    def update_settings_availability(self, *args):
        advanced = dpg.get_value("settings_profile") == "Advanced core physics"
        if not advanced:
            dpg.set_value("settings_initial", "Full-power equilibrium")
            dpg.set_value("settings_cycle", "Steady classroom")
        dpg.configure_item("settings_initial", enabled=advanced)
        dpg.configure_item("settings_cycle", enabled=advanced)

    def restore_default_settings(self):
        defaults = self.canonical.PedagogicalSettings()
        for tag, value in (
            ("settings_kinetics", self.canonical.kinetics_preset_label(defaults.kinetics_preset)),
            ("settings_xenon", self.canonical.xenon_preset_label(defaults.xenon_preset)),
            ("settings_load", defaults.load_follow_period_s),
            ("settings_profile", defaults.physics_profile),
            ("settings_initial", defaults.initial_condition),
            ("settings_cycle", defaults.cycle_preset),
        ):
            dpg.set_value(tag, value)
        self.update_settings_availability()

    def apply_settings(self):
        settings = self.canonical.PedagogicalSettings(
            kinetics_preset=self.kinetics_labels[dpg.get_value("settings_kinetics")],
            xenon_preset=self.xenon_labels[dpg.get_value("settings_xenon")],
            load_follow_period_s=float(dpg.get_value("settings_load")),
            physics_profile=dpg.get_value("settings_profile"),
            initial_condition=dpg.get_value("settings_initial"),
            cycle_preset=dpg.get_value("settings_cycle"),
        )
        self.backend.apply_settings(settings)
        dpg.configure_item("settings_window", show=False)
        self.sync_controls()
        self.refresh_ui(force=True)

    def set_source_strength(self, sender, value, user_data=None):
        if self.s.pedagogical_settings.advanced_physics:
            source = self.backend.set_control("source_strength", 10.0 ** float(value))
            self.s.add_log(f"External source set to {source:.2e} model units.")

    def diagnostics_text(self):
        s = self.s
        advanced = s.pedagogical_settings.advanced_physics
        components = (
            ("Rod bank", s.rho_rods), ("SCRAM protection", s.rho_scram), ("Manual trim", s.rho_manual),
            ("Fuel Doppler", s.rho_fuel), ("Moderator temperature", s.rho_moderator_temp),
            ("Moderator density", s.rho_density), ("Void", s.rho_void),
            ("Boron", s.rho_boron), ("Xe-135", s.rho_xe), ("Sm-149", s.rho_sm),
            ("Cycle depletion", s.rho_depletion if advanced else 0.0),
        )
        balance = "\n".join(f"{name:<24} {1e5 * value:+9.1f} pcm" for name, value in components)
        multiplication = "infinite/critical" if math.isinf(s.subcritical_multiplication) else f"{s.subcritical_multiplication:.2f}"
        return (
            f"Profile: {s.pedagogical_settings.physics_profile} | {s.pedagogical_settings.initial_condition}\n\n"
            f"REACTIVITY BALANCE\n{balance}\n{'-' * 39}\n{'TOTAL':<24} {s.reactivity_pcm:+9.1f} pcm\n\n"
            f"POISONS / EXPOSURE\nI-135 {s.I:12.5f}   Xe-135 {s.Xe:12.5f} ({1e5*s.rho_xe:+.1f} pcm)\n"
            f"Pm-149 {s.Pm:11.5f}   Sm-149 {s.Sm:11.5f} ({1e5*s.rho_sm:+.1f} pcm)\n"
            f"Exposure {s.exposure_efpd:.2f}/{s.cycle_length_efpd:.0f} EFPD   Boron {s.boron_ppm:.0f} ppm\n\n"
            f"STARTUP INSTRUMENTATION\nRange {s.instrument_range}   Log level {s.log_neutron_level:.3f}\n"
            f"External source {s.source_strength:.5e}   Multiplication {multiplication}"
        )

    def show_diagnostics(self):
        dpg.configure_item("diagnostics_window", show=True)
        self.refresh_diagnostics()

    def refresh_diagnostics(self):
        if not dpg.does_item_exist("diagnostics_window"):
            return
        dpg.set_value("diagnostics_text", self.diagnostics_text())
        advanced = self.s.pedagogical_settings.advanced_physics
        dpg.configure_item("source_strength", enabled=advanced)
        if advanced:
            dpg.set_value("source_strength", math.log10(max(self.s.source_strength, 1e-8)))
        positions = list(range(101))
        withdrawn = [100.0 - value for value in positions]
        integral = [1e5 * self.canonical.rod_reactivity(value, advanced) for value in withdrawn]
        differential = [-self.canonical.differential_rod_worth_pcm_per_pct(value, advanced) for value in withdrawn]
        dpg.set_value("rod_integral_series", [positions, integral])
        dpg.set_value("rod_differential_series", [positions, differential])
        dpg.set_axis_limits("rod_x_axis", 0, 100)

    def build(self):
        dpg.create_context()
        with dpg.texture_registry(tag="textures"):
            pass
        repository_root = DEFAULT_MODEL_DIR.parents[1]
        self.load_texture("banner_texture", repository_root / "utm.fkt.logo.png")
        self.load_texture("splash_texture", repository_root / "assets" / "UTM.logo.png")
        regular_font = Path("C:/Windows/Fonts/segoeui.ttf")
        bold_font = Path("C:/Windows/Fonts/segoeuib.ttf")
        with dpg.font_registry():
            if regular_font.exists():
                dpg.add_font(str(regular_font), 14, tag="font_regular")
                dpg.add_font(str(regular_font), 16, tag="font_small")
            if bold_font.exists():
                dpg.add_font(str(bold_font), 23, tag="font_header")
                dpg.add_font(str(bold_font), 28, tag="font_splash_title")
        dpg.create_viewport(title="Reactor Physics and Kinetics Simulator", width=1480, height=900)

        with dpg.theme() as dark_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (13, 18, 24))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (17, 24, 32))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (27, 38, 49))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (29, 78, 112))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 4)
        with dpg.theme() as splash_theme:
            with dpg.theme_component(dpg.mvWindowAppItem):
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)

        with dpg.window(tag="primary", label="Reactor Physics Simulator", no_close=True, no_collapse=True):
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingFixedFit, borders_innerV=False):
                dpg.add_table_column(init_width_or_weight=480)
                dpg.add_table_column(init_width_or_weight=105)
                dpg.add_table_column(init_width_or_weight=850)
                with dpg.table_row():
                    with dpg.group(indent=17):
                        title = dpg.add_text("NUCLEAR REACTOR CONTROL PANEL - V7", color=(238, 245, 251))
                        subtitle = dpg.add_text("Open Nuclear Engineering Teaching Suite", color=(174, 189, 202))
                        if dpg.does_item_exist("font_header"):
                            dpg.bind_item_font(title, "font_header")
                        if dpg.does_item_exist("font_small"):
                            dpg.bind_item_font(subtitle, "font_small")
                    dpg.add_button(label="ABOUT", callback=lambda *args: self.show_about(), width=82, height=32)
                    if dpg.does_item_exist("banner_texture"):
                        dpg.add_image("banner_texture", width=850, height=85)
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label="START", callback=lambda *args: self.start(), width=105)
                dpg.add_button(label="PAUSE", callback=lambda *args: self.pause(), width=105)
                dpg.add_button(label="SCRAM", callback=lambda *args: self.scram(), width=105)
                dpg.add_button(label="RESET", callback=lambda *args: self.reset(), width=105)
                dpg.add_spacer(width=15)
                dpg.add_text("STATUS: PAUSED", tag="status", color=(90, 220, 140))
                dpg.add_spacer(width=20)
                dpg.add_text("Render: -- FPS | Physics: -- steps/s | UI update: -- ms", tag="perf", color=(90, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("HIGH PWR", tag="lamp_power")
                dpg.add_text("HI TEMP", tag="lamp_temp")
                dpg.add_text("LOW FLOW", tag="lamp_flow")
                dpg.add_text("TRIP", tag="lamp_trip")

            with dpg.group(horizontal=True):
                with dpg.child_window(tag="operator_pane", width=390, height=-1, border=True, horizontal_scrollbar=True, resizable_x=True):
                    dpg.add_text("OPERATOR CONTROLS", color=(110, 205, 255))
                    dpg.add_combo(("manual", "auto", "load_follow"), default_value="manual", tag="mode", label="Mode", callback=self.set_mode)
                    dpg.add_slider_float(label="Rod insertion %", tag="rod", min_value=0, max_value=100, callback=self.set_rod)
                    dpg.add_slider_float(label="Power target %", tag="target", min_value=30, max_value=120, callback=self.set_float("setpoint", 0.01))
                    dpg.add_slider_float(label="Coolant flow %", tag="flow", min_value=20, max_value=120, callback=self.set_float("coolantFlow"))
                    dpg.add_slider_float(label="Heat sink %", tag="sink", min_value=30, max_value=120, callback=self.set_float("heatSink"))
                    dpg.add_slider_float(label="Manual reactivity pcm", tag="rho", min_value=-500, max_value=500, callback=self.set_float("rho_manual", 1e-5))
                    dpg.add_slider_float(label="Boron ppm", tag="boron", min_value=0, max_value=1000, callback=self.set_float("boron_ppm"))
                    dpg.add_slider_float(label="Detector noise %", tag="noise", min_value=0, max_value=8, callback=self.set_float("noiseAmp"))
                    dpg.add_slider_float(label="Simulation speed", default_value=1, min_value=0.25, max_value=8, format="%.2fx", callback=self.set_speed)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="-5 pcm", callback=lambda *args: self.trim(-5))
                        dpg.add_button(label="+5 pcm", callback=lambda *args: self.trim(5))
                        dpg.add_button(label="STEP 1 s", callback=lambda *args: self.step())
                    dpg.add_button(label="EXPORT CSV", callback=lambda *args: dpg.configure_item("export_dialog", show=True), width=-1)
                    dpg.add_button(label="INSTRUCTOR: PEDAGOGICAL SETTINGS", callback=lambda *args: self.show_settings(), width=-1)
                    dpg.add_button(label="OPEN CORE PHYSICS DIAGNOSTICS", callback=lambda *args: self.show_diagnostics(), width=-1)
                    dpg.add_text("", tag="scaling_status", color=(255, 224, 160), wrap=350)
                    dpg.add_separator()
                    dpg.add_text("FAULT INJECTION", color=(255, 190, 70))
                    for label, attr in (
                        ("Stuck rod", "fault_stuck_rod"),
                        ("Partial SCRAM", "fault_partial_scram"),
                        ("Pump trip", "fault_pump_trip"),
                        ("Heat-sink loss", "fault_heat_sink_loss"),
                        ("Detector bias", "fault_detector_bias"),
                        ("Frozen detector", "fault_frozen_detector"),
                        ("Boron dilution", "fault_boron_dilution"),
                        ("Auto controller failure", "fault_auto_failure"),
                        ("Low-flow trip fail", "fault_low_flow_trip_fail"),
                    ):
                        dpg.add_checkbox(label=label, tag=attr, callback=self.toggle_fault(attr))
                    dpg.add_slider_float(label="Fault severity %", tag="severity", default_value=60, min_value=0, max_value=100, callback=self.set_float("fault_severity"))
                    dpg.add_separator()
                    dpg.add_text("LIVE READOUT", color=(110, 205, 255))
                    dpg.add_text("", tag="readout", wrap=300)

                with dpg.child_window(tag="plant_pane", width=1020, height=-1, border=True, horizontal_scrollbar=True, resizable_x=True, no_scrollbar=False):
                    with dpg.group(horizontal=True):
                        with dpg.child_window(width=500, height=285, border=True):
                            dpg.add_text("PRIMARY SYSTEM MIMIC", color=(110, 205, 255))
                            dpg.add_drawlist(width=470, height=235, tag="mimic")
                        with dpg.child_window(width=-1, height=285, border=True):
                            dpg.add_text("INSTRUMENTS", color=(110, 205, 255))
                            for tag, label in (("power_bar", "NEUTRON POWER"), ("heat_bar", "TOTAL HEAT"), ("flow_bar", "COOLANT FLOW"), ("temp_bar", "FUEL TEMPERATURE")):
                                dpg.add_text(label)
                                dpg.add_progress_bar(tag=tag, default_value=0.0, overlay="--", width=-1)
                            dpg.add_text("", tag="reactivity_text")
                            dpg.add_text("", tag="period_text")

                    with dpg.plot(label="GPU strip chart (40-second rolling window)", height=520, width=1120, anti_aliased=False):
                        dpg.add_plot_legend()
                        x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Simulation time (s)", tag="x_axis")
                        y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Percent / scaled temperature", tag="y_axis")
                        dpg.add_line_series([], [], label="Measured power %", parent=y_axis, tag="power_series")
                        dpg.add_line_series([], [], label="True power %", parent=y_axis, tag="true_power_series")
                        dpg.add_line_series([], [], label="Total heat %", parent=y_axis, tag="heat_series")
                        dpg.add_line_series([], [], label="Decay heat %", parent=y_axis, tag="decay_series")
                        dpg.add_line_series([], [], label="Target %", parent=y_axis, tag="target_series")
                        dpg.add_line_series([], [], label="Fuel temp / 10", parent=y_axis, tag="temp_series")
                    dpg.add_spacer(height=120, width=1140)

        with dpg.window(tag="about_window", label="About — Open Nuclear Engineering Teaching Suite", show=False, modal=True, width=720, height=650):
            dpg.add_input_text(tag="about_text", multiline=True, readonly=True, width=-1, height=560)
            dpg.add_button(label="CLOSE", callback=lambda *args: dpg.configure_item("about_window", show=False), width=100)

        with dpg.file_dialog(
            tag="export_dialog", show=False, modal=True, directory_selector=False,
            callback=self.export_dialog_callback, default_path=str(Path.cwd()),
            default_filename=f"reactor_sim_run_{datetime.now():%Y%m%d_%H%M%S}.csv",
            width=760, height=460,
        ):
            dpg.add_file_extension(".csv", color=(100, 220, 140))
            dpg.add_file_extension(".*")

        with dpg.window(tag="settings_window", label="Instructor — Pedagogical Settings", show=False, modal=True, width=680, height=500, no_resize=True):
            dpg.add_text("These controls alter the model equations, not wall-clock simulation speed.", wrap=620)
            dpg.add_combo(tuple(self.kinetics_labels), tag="settings_kinetics", label="Kinetics preset", width=420)
            dpg.add_combo(tuple(self.xenon_labels), tag="settings_xenon", label="Xenon timescale", width=420)
            dpg.add_slider_float(tag="settings_load", label="Load-follow period (s)", min_value=60, max_value=600, format="%.0f s", width=420)
            dpg.add_separator()
            dpg.add_combo(self.canonical.PHYSICS_PROFILES, tag="settings_profile", label="Core-physics detail", callback=self.update_settings_availability, width=420)
            dpg.add_combo(self.canonical.INITIAL_CONDITIONS, tag="settings_initial", label="Initial condition", width=420)
            dpg.add_combo(tuple(self.canonical.CYCLE_PRESETS), tag="settings_cycle", label="Exposure state", width=420)
            dpg.add_text("Applying settings resets the run and initializes delayed-neutron and Xe/I state consistently.", wrap=620)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Restore validated defaults", callback=lambda *args: self.restore_default_settings())
                dpg.add_button(label="Cancel", callback=lambda *args: dpg.configure_item("settings_window", show=False))
                dpg.add_button(label="Apply and reset", callback=lambda *args: self.apply_settings())

        with dpg.window(tag="diagnostics_window", label="Core Physics Diagnostics", show=False, width=780, height=720):
            dpg.add_input_text(tag="diagnostics_text", multiline=True, readonly=True, width=-1, height=350)
            with dpg.plot(label="Control-rod worth", height=230, width=-1, anti_aliased=False):
                dpg.add_plot_axis(dpg.mvXAxis, label="Rod bank inserted (%)", tag="rod_x_axis")
                rod_y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Worth (pcm / pcm per %)", tag="rod_y_axis")
                dpg.add_line_series([], [], label="Integral worth", parent=rod_y_axis, tag="rod_integral_series")
                dpg.add_line_series([], [], label="Differential worth", parent=rod_y_axis, tag="rod_differential_series")
            dpg.add_slider_float(tag="source_strength", label="External source log10(model units)", min_value=-8, max_value=-3, callback=self.set_source_strength, width=500)
            dpg.add_button(label="CLOSE", callback=lambda *args: dpg.configure_item("diagnostics_window", show=False))

        if dpg.does_item_exist("splash_texture"):
            window_width = 790
            window_height = 387
            with dpg.window(
                tag="startup_splash", no_title_bar=True, no_resize=True,
                no_move=True, modal=True, width=window_width, height=window_height,
            ):
                with dpg.drawlist(width=790, height=387):
                    dpg.draw_rectangle((0, 0), (789, 386), color=(125, 18, 56), fill=(15, 19, 25), thickness=2)
                    dpg.draw_image("splash_texture", (36, 24), (756, 265))
                    dpg.draw_text((172, 292), "Open Nuclear Engineering Teaching Suite", tag="splash_title", color=(243, 245, 247), size=32)
                    dpg.draw_text((262, 337), "Reactor Physics and Kinetics Simulator", tag="splash_module", color=(199, 209, 219), size=20)
            dpg.bind_item_theme("startup_splash", splash_theme)

        dpg.bind_theme(dark_theme)
        if dpg.does_item_exist("font_regular"):
            dpg.bind_font("font_regular")
        dpg.set_primary_window("primary", True)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        if dpg.does_item_exist("startup_splash"):
            dpg.set_item_pos("startup_splash", ((1480 - window_width) // 2, (900 - window_height) // 2))
            self.splash_until = time.perf_counter() + 3.0
        self.sync_controls()
        self.refresh_ui(force=True)

    def sync_controls(self):
        self.syncing = True
        try:
            dpg.set_value("mode", self.s.mode)
            dpg.set_value("rod", self.insertion_fn(self.s.rod_pos))
            dpg.set_value("target", 100 * self.s.setpoint)
            dpg.set_value("flow", self.s.coolantFlow)
            dpg.set_value("sink", self.s.heatSink)
            dpg.set_value("rho", 1e5 * self.s.rho_manual)
            dpg.set_value("boron", self.s.boron_ppm)
            dpg.set_value("noise", self.s.noiseAmp)
            dpg.set_value("severity", self.s.fault_severity)
            for attr in self.fault_keys:
                dpg.set_value(attr, bool(getattr(self.s, attr)))
        finally:
            self.syncing = False

    def draw_mimic(self):
        s = self.s
        dpg.delete_item("mimic", children_only=True)
        power = min(max(s.powerPct / 150.0, 0.0), 1.0)
        core_color = (int(40 + 215 * power), int(100 + 100 * (1 - power)), 45, 255)
        coolant = (40, 155, 240, 255) if s.coolantFlow >= 35 else (255, 100, 40, 255)
        dpg.draw_rectangle((45, 35), (175, 205), color=(150, 170, 185), fill=(30, 40, 48), thickness=3, parent="mimic")
        dpg.draw_rectangle((75, 68), (145, 178), color=core_color, fill=(*core_color[:3], 90), thickness=3, parent="mimic")
        dpg.draw_text((79, 108), "CORE", color=(235, 240, 245), size=22, parent="mimic")
        rod_y = 70 + 1.05 * self.insertion_fn(s.rod_pos)
        for x in (88, 110, 132):
            dpg.draw_line((x, 42), (x, rod_y), color=(220, 220, 220), thickness=5, parent="mimic")
        dpg.draw_line((175, 70), (285, 70), color=coolant, thickness=10, parent="mimic")
        dpg.draw_line((285, 70), (285, 185), color=coolant, thickness=10, parent="mimic")
        dpg.draw_line((285, 185), (175, 185), color=coolant, thickness=10, parent="mimic")
        dpg.draw_circle((355, 128), 53, color=(140, 170, 185), fill=(28, 38, 48), thickness=3, parent="mimic")
        dpg.draw_text((315, 115), "STEAM\nGEN.", color=(235, 240, 245), size=18, parent="mimic")
        dpg.draw_line((285, 70), (325, 85), color=coolant, thickness=10, parent="mimic")
        dpg.draw_line((325, 170), (285, 185), color=coolant, thickness=10, parent="mimic")
        mimic_status = f"{s.powerPct:6.2f}% power   {s.fuelT:5.1f} C fuel   {s.coolantFlow:4.0f}% flow"
        measured = dpg.get_text_size(mimic_status)
        scaled_width = measured[0] * 18.0 / 14.0 if measured and measured[0] > 0 else 390.0
        dpg.draw_text(((470.0 - scaled_width) / 2.0, 7), mimic_status, color=(120, 220, 255), size=18, parent="mimic")
        if s.scram:
            dpg.draw_text((190, 105), "SCRAM", color=(255, 45, 45), size=32, parent="mimic")

    def refresh_ui(self, force=False):
        started = time.perf_counter()
        s = self.s
        status = "SCRAM" if s.scram else ("RUNNING" if s.running else "PAUSED")
        dpg.set_value("status", f"STATUS: {status}   |   SIM TIME {s.time:07.2f} s")
        dpg.set_value("perf", f"Render: {self.fps:5.1f} FPS | Physics: {self.steps_per_second:6.0f} steps/s | UI update: {self.ui_update_ms:5.2f} ms")
        period = "stable" if not math.isfinite(s.period) else f"{s.period:.2f} s"
        dpg.set_value("readout", f"Measured / true power: {s.measuredPct:7.2f} / {s.powerPct:7.2f} %\nTotal / decay heat: {s.heatPct:7.2f} / {s.decayPct:7.2f} %\nFuel / clad / coolant: {s.fuelT:6.1f} / {s.cladT:6.1f} / {s.coolT:6.1f} C\nRod insertion: {self.insertion_fn(s.rod_pos):6.1f} %\nReactivity: {s.reactivity_pcm:+7.1f} pcm\nI / Xe index: {s.I:.3f} / {s.Xe:.3f}\nEvents: {s.logText[-1]}")
        for tag, value, maximum, label in (("power_bar", s.measuredPct, 150, "%"), ("heat_bar", s.heatPct, 150, "%"), ("flow_bar", s.coolantFlow, 120, "%"), ("temp_bar", s.fuelT, 900, " C")):
            dpg.set_value(tag, min(max(value / maximum, 0), 1))
            dpg.configure_item(tag, overlay=f"{value:7.2f}{label}")
        dpg.set_value("reactivity_text", f"Reactivity: {s.reactivity_pcm:+8.1f} pcm")
        dpg.set_value("period_text", f"Reactor period: {period}")
        settings = s.pedagogical_settings
        scaling = (
            "PEDAGOGICAL SCALING: VALIDATED CLASSROOM DEFAULTS"
            if settings.is_baseline else
            f"ACTIVE: {settings.kinetics_preset} | {settings.xenon_preset} | {settings.physics_profile}"
        )
        dpg.set_value("scaling_status", scaling)
        lamp_off = (105, 112, 120)
        dpg.configure_item("lamp_power", color=(255, 70, 70) if s.powerPct > 0.95 * 100 * s.tripHighPower else lamp_off)
        dpg.configure_item("lamp_temp", color=(255, 180, 50) if s.fuelT > 0.95 * s.tripHighFuelTemp else lamp_off)
        dpg.configure_item("lamp_flow", color=(255, 180, 50) if s.coolantFlow < 1.05 * s.tripLowFlow else lamp_off)
        dpg.configure_item("lamp_trip", color=(255, 40, 40) if s.scram else lamp_off)
        canonical_readout = "\n".join(self.model.compose_readout())
        dpg.set_value("readout", canonical_readout)

        valid = ~__import__("numpy").isnan(s.tHist)
        idx = __import__("numpy").flatnonzero(valid)[-self.PLOT_POINTS:]
        x = s.tHist[idx].tolist()
        for tag, data in (
            ("power_series", s.pHist), ("true_power_series", s.truePHist),
            ("heat_series", s.heatHist), ("decay_series", s.decayHist),
            ("target_series", s.targetHist), ("temp_series", s.tfHist),
        ):
            dpg.set_value(tag, [x, data[idx].tolist()])
        if x:
            t_now = float(x[-1])
            if t_now <= self.VISIBLE_WINDOW_S:
                xmin, xmax = 0.0, self.VISIBLE_WINDOW_S
            else:
                xmin, xmax = t_now - self.VISIBLE_WINDOW_S, t_now
            dpg.set_axis_limits("x_axis", xmin, xmax)
        else:
            dpg.set_axis_limits("x_axis", 0.0, self.VISIBLE_WINDOW_S)
        dpg.set_axis_limits("y_axis", 0, max(160, min(320, max(s.powerPct, s.heatPct) * 1.15)))
        self.draw_mimic()
        self.sync_controls()
        if dpg.is_item_shown("diagnostics_window"):
            self.refresh_diagnostics()
        self.ui_update_ms = (time.perf_counter() - started) * 1000

    def run(self):
        self.build()
        while dpg.is_dearpygui_running():
            now = time.perf_counter()
            if self.splash_until is not None and now >= self.splash_until:
                if dpg.does_item_exist("startup_splash"):
                    dpg.delete_item("startup_splash")
                self.splash_until = None
            real_dt = min(now - self.last_frame, 0.10)
            self.last_frame = now
            self.frames += 1

            if self.s.running:
                self.steps += self.backend.advance_elapsed(real_dt, self.speed)

            if now - self.last_ui >= 0.10:
                self.refresh_ui()
                self.last_ui = now
            if now - self.last_perf >= 1.0:
                elapsed = now - self.last_perf
                self.fps = self.frames / elapsed
                self.steps_per_second = self.steps / elapsed
                self.frames = self.steps = 0
                self.last_perf = now

            dpg.render_dearpygui_frame()
        dpg.destroy_context()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    args = parser.parse_args()
    backend_cls, canonical = load_backend(args.model_dir)
    ReactorDPG(backend_cls, canonical).run()


if __name__ == "__main__":
    main()
