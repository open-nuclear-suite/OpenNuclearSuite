#!/usr/bin/env python3
"""
LWR Thermal-Hydraulics / LOCA Teaching Simulator - Python version
-----------------------------------------------------------------
Author: Mohsin Mohd Sies
Affiliation: Nuclear Engineering Program, Faculty of Chemical and Energy
    Engineering, Universiti Teknologi Malaysia
Contact: mohsin.sies@gmail.com
Repository: https://github.com/open-nuclear-suite/OpenNuclearSuite
License: MIT

Purpose: undergraduate teaching demonstration of coupled point kinetics,
decay heat, coolant inventory, pressure, heat removal, ECCS and LOCA trends.

This is NOT a licensing, safety-analysis, best-estimate, or design code.
It is a simplified lumped-parameter classroom model intended to help students
see qualitative behaviour during normal operation, SBLOCA, LBLOCA, loss of
flow, loss of heat sink and station blackout.

Translated from the Octave teaching simulator v2 to Python/Tkinter.

Requirements:
    Python 3.9+
    numpy
    matplotlib

Run:
    python simulators/thermal_hydraulics_simulator.py
"""

from __future__ import annotations

import csv
import math
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Deque, Dict, List, Optional, TextIO, Tuple

import numpy as np

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


import matplotlib
try:
    matplotlib.use("TkAgg")
except ImportError:
    # Allows syntax/import checks in headless environments. The GUI still needs
    # a normal desktop Python with Tkinter and Matplotlib's Tk backend.
    pass
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# ---------------------------------------------------------------------------
# Branding and startup splash
# ---------------------------------------------------------------------------

PROJECT_NAME = "Open Nuclear Engineering Teaching Suite"
LOGO_FILENAME = "UTM.logo.png"


def find_logo_path() -> Optional[Path]:
    """Return the first available UTM logo path."""
    candidates = [
        Path(__file__).resolve().parent / LOGO_FILENAME,
        Path(__file__).resolve().parent.parent / "assets" / LOGO_FILENAME,
        Path.cwd() / LOGO_FILENAME,
        Path.cwd() / "assets" / LOGO_FILENAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_logo_image(
    master: tk.Misc, max_width: int, max_height: Optional[int] = None
) -> Optional[tk.PhotoImage]:
    """Load the complete UTM logo and fit it proportionally inside a box.

    Pillow is used when available for smooth, exact resizing. If Pillow is not
    installed, Tkinter's built-in PNG loader is used with integer subsampling.
    Neither path crops the image; the full crest, UTM lettering, and university
    name remain visible.
    """
    logo_path = find_logo_path()
    if logo_path is None:
        return None

    max_width = max(1, int(max_width))
    max_height = None if max_height is None else max(1, int(max_height))

    if Image is not None and ImageTk is not None:
        try:
            with Image.open(logo_path) as source:
                logo = source.convert("RGBA")
                height_limit = max_height if max_height is not None else logo.height
                logo.thumbnail((max_width, height_limit), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(logo, master=master)
        except (OSError, ValueError):
            pass

    try:
        image = tk.PhotoImage(master=master, file=str(logo_path))
        width_ratio = image.width() / max_width
        height_ratio = image.height() / max_height if max_height is not None else 1.0
        reduction = max(1, math.ceil(max(width_ratio, height_ratio)))
        if reduction > 1:
            image = image.subsample(reduction, reduction)
        return image
    except tk.TclError:
        return None

def show_startup_splash(
    root: tk.Tk, module_name: str, duration_ms: int = 2000
) -> None:
    """Show a centred, borderless project splash, then reveal the dashboard."""
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg="#202226")
    try:
        splash.attributes("-topmost", True)
    except tk.TclError:
        pass

    border = tk.Frame(splash, bg="#7d1238", padx=3, pady=3)
    border.pack(fill="both", expand=True)
    panel = tk.Frame(border, bg="#15181d", padx=34, pady=24)
    panel.pack(fill="both", expand=True)

    splash.logo_image = load_logo_image(splash, max_width=720, max_height=245)
    if splash.logo_image is not None:
        tk.Label(panel, image=splash.logo_image, bg="#15181d", bd=0).pack(pady=(0, 18))
    else:
        tk.Label(
            panel, text="UTM", bg="#7d1238", fg="white",
            font=("Segoe UI", 34, "bold"), padx=34, pady=8,
        ).pack(pady=(0, 18))

    tk.Label(
        panel, text=PROJECT_NAME, bg="#15181d", fg="#f3f5f7",
        font=("Segoe UI", 21, "bold"),
    ).pack()
    tk.Label(
        panel, text=module_name, bg="#15181d", fg="#c7d1db",
        font=("Segoe UI", 11),
    ).pack(pady=(8, 0))

    splash.update_idletasks()
    width = splash.winfo_reqwidth()
    height = splash.winfo_reqheight()
    x = max(0, (splash.winfo_screenwidth() - width) // 2)
    y = max(0, (splash.winfo_screenheight() - height) // 2)
    splash.geometry(f"{width}x{height}+{x}+{y}")

    def close_splash() -> None:
        if splash.winfo_exists():
            splash.destroy()
        root.deiconify()
        root.lift()
        try:
            root.focus_force()
        except tk.TclError:
            pass

    root.after(duration_ms, close_splash)


# ---------------------------------------------------------------------------
# Constants and state
# ---------------------------------------------------------------------------


@dataclass
class Constants:
    # Nominal LWR / PWR-like teaching reference values.
    Pnom_MW: float = 3000.0
    Tsink: float = 295.0
    TrefFuel: float = 850.0
    TrefClad: float = 335.0
    TrefCool: float = 305.0
    Pref: float = 15.5
    Mref: float = 1.0

    # 6-group delayed neutron data, representative U-235 thermal spectrum.
    beta_i: np.ndarray = field(
        default_factory=lambda: np.array(
            [0.000215, 0.001424, 0.001274, 0.002568, 0.000748, 0.000273],
            dtype=float,
        )
    )
    lambda_i: np.ndarray = field(
        default_factory=lambda: np.array([0.0124, 0.0305, 0.111, 0.301, 1.14, 3.01], dtype=float)
    )
    # Effective prompt generation time is deliberately enlarged for a stable,
    # slow classroom simulator. Use licensed codes for real transient analysis.
    Lambda: float = 0.055

    # Simple decay heat groups. Fractions sum to about 6.5 percent at full power.
    decay_frac: np.ndarray = field(default_factory=lambda: np.array([0.030, 0.025, 0.010], dtype=float))
    decay_lambda: np.ndarray = field(default_factory=lambda: np.array([0.0030, 0.0300, 0.2500], dtype=float))

    # Lumped thermal capacities and conductances in MW/degC or MW*s/degC.
    Cfuel: float = 950.0
    Cclad: float = 145.0
    Ccool: float = 650.0

    # Reactivity coefficients. Units are delta-k/k per degC.
    alpha_f: float = -3.5e-5
    alpha_m: float = -2.0e-5
    boron_worth: float = -0.8e-5
    boron_ref: float = 1000.0
    rod_worth_pcm: float = 3000.0

    # Simplified inventory and pressure model coefficients.
    break_coeff: float = 0.014
    porv_coeff: float = 0.007
    evap_coeff: float = 1.0e-5
    eccs_coeff: float = 0.010
    press_tau: float = 18.0
    pbreak_coeff: float = 0.17
    pporv_coeff: float = 0.45

    # Classroom warning limits only.
    cladWarn: float = 650.0
    cladTrip: float = 1200.0
    pressHigh: float = 16.7
    invLow: float = 0.65

    @property
    def beta(self) -> float:
        return float(np.sum(self.beta_i))

    @property
    def prompt_frac(self) -> float:
        # Keeps initial total heat approximately equal to Pnom_MW.
        return float(1.0 - np.sum(self.decay_frac))

    @property
    def Kfc(self) -> float:
        return self.Pnom_MW / (self.TrefFuel - self.TrefClad)

    @property
    def Kcc_nom(self) -> float:
        return self.Pnom_MW / (self.TrefClad - self.TrefCool)

    @property
    def Ksg_nom(self) -> float:
        return self.Pnom_MW / (self.TrefCool - self.Tsink)


@dataclass
class History:
    maxlen: int = 1600
    t: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pow: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    dec: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    Tf: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    Tcl: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    Tc: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    P: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    M: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    rho: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    flow: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))

    def as_array(self, name: str) -> np.ndarray:
        return np.array(getattr(self, name), dtype=float)

    def clear(self) -> None:
        for name in ("t", "pow", "dec", "Tf", "Tcl", "Tc", "P", "M", "rho", "flow"):
            getattr(self, name).clear()


@dataclass
class State:
    c: Constants
    t: float = 0.0
    n: float = 1.0
    Ci: np.ndarray = field(init=False)
    Di: np.ndarray = field(init=False)
    Tf: float = field(init=False)
    Tcl: float = field(init=False)
    Tc: float = field(init=False)
    P: float = field(init=False)
    M: float = field(init=False)
    trip: bool = False
    autoECCS: bool = True
    scenario_name: str = "Normal operation"
    hist: History = field(default_factory=History)

    def __post_init__(self) -> None:
        self.Ci = self.c.beta_i / (self.c.Lambda * self.c.lambda_i)
        self.Di = self.c.decay_frac / self.c.decay_lambda
        self.Tf = self.c.TrefFuel
        self.Tcl = self.c.TrefClad
        self.Tc = self.c.TrefCool
        self.P = self.c.Pref
        self.M = self.c.Mref

    def reset(self) -> None:
        c = self.c
        self.t = 0.0
        self.n = 1.0
        self.Ci = c.beta_i / (c.Lambda * c.lambda_i)
        self.Di = c.decay_frac / c.decay_lambda
        self.Tf = c.TrefFuel
        self.Tcl = c.TrefClad
        self.Tc = c.TrefCool
        self.P = c.Pref
        self.M = c.Mref
        self.trip = False
        self.autoECCS = True
        self.scenario_name = "Normal operation"
        self.hist.clear()


# ---------------------------------------------------------------------------
# GUI application
# ---------------------------------------------------------------------------


class LWRTeachingSimulator:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.c = Constants()
        self.state = State(self.c)

        self.running = False
        self.freeze_chart = False
        self.last_wall_time = time.perf_counter()
        self.after_id: str | None = None

        self.root.title("LWR Thermal-Hydraulics / LOCA Teaching Simulator - Python")
        self.root.geometry("1420x820")
        self.root.minsize(1150, 680)
        self.root.configure(bg="#202226")

        self.control_vars: Dict[str, tk.DoubleVar] = {}
        self.value_labels: Dict[str, ttk.Label] = {}
        self.readout_vars: Dict[str, tk.StringVar] = {}
        self.lamps: Dict[str, tk.Label] = {}

        self.auto_eccs_var = tk.BooleanVar(value=True)
        self.auto_trip_var = tk.BooleanVar(value=True)

        self.demo_mode = False
        self.demo_script_var = tk.StringVar(value="SBLOCA recovery")
        self.demo_stage = ""
        self.demo_start_t = 0.0

        self.csv_logging = False
        self.csv_file: Optional[TextIO] = None
        self.csv_writer: Optional[csv.writer] = None
        self.csv_path: Optional[str] = None
        self.csv_last_logged_t = -1.0e9
        self.csv_log_interval = 0.5  # simulation seconds between rows
        self.log_button: Optional[ttk.Button] = None
        self.log_status_var = tk.StringVar(value="CSV logging: off")

        self._make_style()
        self._build_gui()
        self.refresh_all(force=True)
        self._schedule_loop()

    # ----------------------------- GUI building -----------------------------

    def _make_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background="#202226")
        style.configure("Panel.TFrame", background="#2a2d33")
        style.configure("Title.TLabel", background="#0e1013", foreground="#f4f4f4", font=("Segoe UI", 12, "bold"))
        style.configure("PanelTitle.TLabel", background="#2a2d33", foreground="#f4f4f4", font=("Segoe UI", 11, "bold"))
        style.configure("Text.TLabel", background="#2a2d33", foreground="#e8e8e8", font=("Segoe UI", 9))
        style.configure("Small.TLabel", background="#2a2d33", foreground="#e8e8e8", font=("Segoe UI", 8))
        style.configure("Green.TLabel", background="#101114", foreground="#42ff64", font=("Consolas", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 9, "bold"))
        style.configure("Danger.TButton", font=("Segoe UI", 9, "bold"), foreground="#ffffff", background="#a00000")
        style.configure("TCheckbutton", background="#2a2d33", foreground="#e8e8e8", font=("Segoe UI", 9))

    def _build_gui(self) -> None:
        header = tk.Frame(self.root, bg="#0e1013")
        header.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(12, 8))

        title_block = tk.Frame(header, bg="#0e1013")
        title_block.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=8)
        tk.Label(
            title_block,
            bg="#0e1013", fg="#f4f4f4",
            font=("Segoe UI", 12, "bold"), anchor="w",
            text="LIGHT WATER REACTOR THERMAL-HYDRAULICS TRAINING PANEL  |  Point kinetics + lumped LOCA model",
        ).pack(anchor="w")
        tk.Label(
            title_block, text=PROJECT_NAME, bg="#0e1013", fg="#b8c2cc",
            font=("Segoe UI", 9), anchor="w",
        ).pack(anchor="w", pady=(3, 0))

        self.utm_logo_image = load_logo_image(self.root, max_width=320, max_height=108)
        if self.utm_logo_image is not None:
            tk.Label(
                header, image=self.utm_logo_image, bg="#0e1013", bd=0,
            ).pack(side=tk.RIGHT, padx=(12, 14), pady=5)
        else:
            tk.Label(
                header, text="UTM", bg="#7d1238", fg="white",
                font=("Segoe UI", 18, "bold"), padx=18, pady=6,
            ).pack(side=tk.RIGHT, padx=(12, 14), pady=5)

        main = ttk.Frame(self.root, style="TFrame")
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))

        plot_frame = ttk.Frame(main, style="TFrame")
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        panel = ttk.Frame(main, style="Panel.TFrame", padding=12)
        panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        panel.configure(width=620)

        ttk.Label(panel, style="PanelTitle.TLabel", text="CONTROL PANEL").pack(anchor="w", pady=(0, 8))

        self._build_plots(plot_frame)
        self._build_controls(panel)

    def _build_plots(self, parent: ttk.Frame) -> None:
        self.fig = Figure(figsize=(7.2, 7.5), dpi=100, facecolor="#202226")
        self.ax_power = self.fig.add_subplot(311)
        self.ax_temp = self.fig.add_subplot(312)
        self.ax_press = self.fig.add_subplot(313)
        self.fig.subplots_adjust(left=0.10, right=0.97, top=0.96, bottom=0.07, hspace=0.42)

        for ax in (self.ax_power, self.ax_temp, self.ax_press):
            ax.set_facecolor("#f6f6f6")
            ax.grid(True, alpha=0.35)
            # White title, axis-label and tick text improves readability on the dark figure background.
            ax.title.set_color("white")
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
            ax.tick_params(axis="both", colors="white")
            for spine in ax.spines.values():
                spine.set_color("white")

        (self.line_pow,) = self.ax_power.plot([], [], linewidth=1.4, label="Noisy indicated power")
        (self.line_dec,) = self.ax_power.plot([], [], linewidth=1.0, label="Decay heat")
        self.ax_power.set_xlabel("time (s)", color="white")
        self.ax_power.set_ylabel("Power (%)", color="white")
        self.ax_power.set_title("Strip chart: indicated power and decay heat", color="white")
        self._style_legend(self.ax_power.legend(loc="upper right"))

        (self.line_tf,) = self.ax_temp.plot([], [], linewidth=1.0, label="Fuel")
        (self.line_tcl,) = self.ax_temp.plot([], [], linewidth=1.4, label="Clad / PCT indicator")
        (self.line_tc,) = self.ax_temp.plot([], [], linewidth=1.0, label="Coolant")
        self.ax_temp.set_xlabel("time (s)", color="white")
        self.ax_temp.set_ylabel("Temperature (degC)", color="white")
        self.ax_temp.set_title("Fuel, cladding and primary coolant lumped temperatures", color="white")
        self._style_legend(self.ax_temp.legend(loc="upper right"))

        (self.line_p,) = self.ax_press.plot([], [], linewidth=1.3, label="Pressure (MPa)")
        (self.line_m,) = self.ax_press.plot([], [], linewidth=1.3, label="Inventory x10 (%)")
        self.ax_press.set_xlabel("time (s)", color="white")
        self.ax_press.set_ylabel("MPa or scaled inventory", color="white")
        self.ax_press.set_title("Primary pressure and coolant inventory", color="white")
        self._style_legend(self.ax_press.legend(loc="upper right"))

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    @staticmethod
    def _style_legend(legend) -> None:
        """Make Matplotlib legends readable against the dark simulator background."""
        frame = legend.get_frame()
        frame.set_facecolor("#202226")
        frame.set_edgecolor("#70747a")
        frame.set_alpha(0.90)
        for text in legend.get_texts():
            text.set_color("white")

    def _build_controls(self, parent: ttk.Frame) -> None:
        button_frame = ttk.Frame(parent, style="Panel.TFrame")
        button_frame.pack(fill=tk.X, pady=(0, 8))

        self.run_button = ttk.Button(button_frame, text="START", command=self.toggle_run)
        self.run_button.grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(button_frame, text="RESET", command=self.reset_sim).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(button_frame, text="SCRAM", style="Danger.TButton", command=self.scram_now).grid(row=0, column=2, sticky="ew", padx=2)
        ttk.Button(button_frame, text="STEP 1 s", command=self.step_once).grid(row=0, column=3, sticky="ew", padx=2)
        self.freeze_button = ttk.Button(button_frame, text="FREEZE CHART", command=self.toggle_freeze)
        self.freeze_button.grid(row=0, column=4, sticky="ew", padx=2)
        for col in range(5):
            button_frame.columnconfigure(col, weight=1)

        ttk.Label(parent, style="Text.TLabel", font=("Segoe UI", 10, "bold"), text="Scenario presets").pack(anchor="w", pady=(6, 4))
        scenario_frame = ttk.Frame(parent, style="Panel.TFrame")
        scenario_frame.pack(fill=tk.X, pady=(0, 10))
        scenarios: List[Tuple[str, Callable[[], None]]] = [
            ("NORMAL", self.scenario_normal),
            ("SBLOCA", self.scenario_sbloc),
            ("LBLOCA", self.scenario_lbloc),
            ("LOFA", self.scenario_lofa),
            ("LOHS", self.scenario_lohs),
            ("SBO", self.scenario_sbo),
        ]
        for i, (label, command) in enumerate(scenarios):
            ttk.Button(scenario_frame, text=label, command=command).grid(row=0, column=i, sticky="ew", padx=2)
            scenario_frame.columnconfigure(i, weight=1)

        demo_frame = ttk.Frame(parent, style="Panel.TFrame")
        demo_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(demo_frame, style="Text.TLabel", text="Demo mode").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.demo_combo = ttk.Combobox(
            demo_frame,
            textvariable=self.demo_script_var,
            state="readonly",
            width=24,
            values=("SBLOCA recovery", "LBLOCA ECCS response", "Loss of heat sink recovery", "Station blackout recovery"),
        )
        self.demo_combo.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        self.demo_button = ttk.Button(demo_frame, text="START DEMO", command=self.toggle_demo)
        self.demo_button.grid(row=0, column=2, sticky="ew", padx=(0, 6))
        self.log_button = ttk.Button(demo_frame, text="START CSV LOG", command=self.toggle_csv_logging)
        self.log_button.grid(row=0, column=3, sticky="ew")
        demo_frame.columnconfigure(1, weight=1)

        ttk.Label(parent, style="Small.TLabel", textvariable=self.log_status_var).pack(anchor="w", pady=(0, 6))

        columns = ttk.Frame(parent, style="Panel.TFrame")
        columns.pack(fill=tk.X)
        left = ttk.Frame(columns, style="Panel.TFrame")
        right = ttk.Frame(columns, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        columns.columnconfigure(0, weight=1)
        columns.columnconfigure(1, weight=1)

        ttk.Label(left, style="Text.TLabel", font=("Segoe UI", 9, "bold"), text="Core / primary controls").pack(anchor="w", pady=(0, 2))
        ttk.Label(right, style="Text.TLabel", font=("Segoe UI", 9, "bold"), text="Safety / support controls").pack(anchor="w", pady=(0, 2))

        self.make_slider(left, "rod", "Control rod insertion", 0, 100, 0, " %")
        self.make_slider(left, "trim", "Fine reactivity trim", -500, 500, 0, " pcm")
        self.make_slider(left, "boron", "Soluble boron", 0, 2500, 1000, " ppm")
        self.make_slider(left, "pump", "RCP / primary flow", 0, 120, 100, " %")
        self.make_slider(left, "sg", "SG heat removal", 0, 140, 100, " %")
        self.make_slider(left, "break", "LOCA break size", 0, 100, 0, " %")
        self.make_slider(left, "eccs", "ECCS injection", 0, 100, 0, " %")

        self.make_slider(right, "afw", "Aux feedwater", 0, 100, 0, " %")
        self.make_slider(right, "porv", "PORV / relief valve", 0, 100, 0, " %")
        self.make_slider(right, "spray", "Pressurizer spray", 0, 100, 0, " %")
        self.make_slider(right, "heater", "Pressurizer heater", 0, 100, 0, " %")
        self.make_slider(right, "rhr", "RHR cooldown", 0, 100, 0, " %")
        self.make_slider(right, "noise", "Instrument noise", 0, 10, 2, " %")
        self.make_slider(right, "speed", "Simulation speed", 0.2, 20, 5, " x")

        checks = ttk.Frame(parent, style="Panel.TFrame")
        checks.pack(fill=tk.X, pady=(8, 4))
        ttk.Checkbutton(checks, text="Auto ECCS logic", variable=self.auto_eccs_var, command=self._sync_auto_eccs).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(checks, text="Auto reactor trip", variable=self.auto_trip_var).grid(row=0, column=1, sticky="w", padx=(35, 0))

        lamp_frame = ttk.Frame(parent, style="Panel.TFrame")
        lamp_frame.pack(fill=tk.X, pady=(4, 8))
        for i, name in enumerate(("REACTOR TRIP", "ECCS ACTIVE", "LOW INVENTORY", "HIGH CLAD TEMP")):
            lamp = tk.Label(
                lamp_frame,
                text=f" {name}",
                font=("Segoe UI", 8, "bold"),
                fg="#c8c8c8",
                bg="#1e1e1e",
                anchor="w",
                padx=4,
                pady=4,
            )
            lamp.grid(row=0, column=i, sticky="ew", padx=3)
            lamp_frame.columnconfigure(i, weight=1)
            self.lamps[name] = lamp

        readout_frame = ttk.Frame(parent, style="Panel.TFrame")
        readout_frame.pack(fill=tk.X, pady=(4, 8))
        left_ro = ttk.Frame(readout_frame, style="Panel.TFrame")
        right_ro = ttk.Frame(readout_frame, style="Panel.TFrame")
        left_ro.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right_ro.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        readout_frame.columnconfigure(0, weight=1)
        readout_frame.columnconfigure(1, weight=1)

        for key, label in (("pow", "POWER"), ("dec", "DECAY"), ("flow", "FLOW"), ("p", "PRESS")):
            self.make_readout(left_ro, key, label)
        for key, label in (("inv", "INV"), ("tcl", "CLAD"), ("tfuel", "FUEL"), ("rho", "RHO")):
            self.make_readout(right_ro, key, label)

        self.status_var = tk.StringVar(value="")
        status = tk.Label(
            parent,
            textvariable=self.status_var,
            wraplength=570,
            justify=tk.LEFT,
            anchor="w",
            font=("Segoe UI", 9),
            fg="#f4f4f4",
            bg="#101114",
            padx=8,
            pady=8,
        )
        status.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

    def make_slider(
        self,
        parent: ttk.Frame,
        key: str,
        label: str,
        minimum: float,
        maximum: float,
        value: float,
        unit: str,
    ) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, pady=3)

        label_row = ttk.Frame(frame, style="Panel.TFrame")
        label_row.pack(fill=tk.X)
        ttk.Label(label_row, style="Small.TLabel", text=label).pack(side=tk.LEFT, anchor="w")
        val_label = ttk.Label(label_row, style="Green.TLabel", anchor="e", width=12)
        val_label.pack(side=tk.RIGHT, anchor="e")

        var = tk.DoubleVar(value=value)
        self.control_vars[key] = var
        self.value_labels[key] = val_label

        scale = ttk.Scale(
            frame,
            from_=minimum,
            to=maximum,
            orient=tk.HORIZONTAL,
            variable=var,
            command=lambda _v, k=key, u=unit: self.update_slider_readout(k, u),
        )
        scale.pack(fill=tk.X)
        self.update_slider_readout(key, unit)

    def make_readout(self, parent: ttk.Frame, key: str, label: str) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, style="Text.TLabel", font=("Segoe UI", 8, "bold"), text=label, width=7).pack(side=tk.LEFT)
        var = tk.StringVar(value="---")
        self.readout_vars[key] = var
        ttk.Label(frame, style="Green.TLabel", textvariable=var, anchor="e").pack(side=tk.LEFT, fill=tk.X, expand=True)

    def update_slider_readout(self, key: str, unit: str) -> None:
        val = self.control_vars[key].get()
        if unit == " ppm":
            txt = f"{val:4.0f}{unit}"
        elif unit == " pcm":
            txt = f"{val:5.0f}{unit}"
        elif unit == " x":
            txt = f"{val:4.1f}{unit}"
        else:
            txt = f"{val:4.0f}{unit}"
        self.value_labels[key].configure(text=txt)

    # ----------------------------- Callbacks ------------------------------

    def toggle_run(self) -> None:
        self.running = not self.running
        if self.running:
            self.run_button.configure(text="PAUSE")
            self.last_wall_time = time.perf_counter()
        else:
            self.run_button.configure(text="START")

    def reset_sim(self) -> None:
        self.running = False
        self.demo_mode = False
        if hasattr(self, "demo_button"):
            self.demo_button.configure(text="START DEMO")
        self.demo_stage = ""
        self.run_button.configure(text="START")
        self.state.reset()
        self.set_slider("rod", 0)
        self.set_slider("trim", 0)
        self.set_slider("boron", 1000)
        self.set_slider("pump", 100)
        self.set_slider("sg", 100)
        self.set_slider("break", 0)
        self.set_slider("eccs", 0)
        self.set_slider("afw", 0)
        self.set_slider("porv", 0)
        self.set_slider("spray", 0)
        self.set_slider("heater", 0)
        self.set_slider("rhr", 0)
        self.set_slider("noise", 2)
        self.set_slider("speed", 5)
        self.auto_eccs_var.set(True)
        self.auto_trip_var.set(True)
        self.state.autoECCS = True
        self.refresh_all(force=True)

    def set_slider(self, key: str, value: float) -> None:
        self.control_vars[key].set(float(value))
        # Need unit for label update; infer from existing label text or key.
        units = {
            "trim": " pcm",
            "boron": " ppm",
            "speed": " x",
            "rod": " %",
            "pump": " %",
            "sg": " %",
            "break": " %",
            "eccs": " %",
            "afw": " %",
            "porv": " %",
            "spray": " %",
            "heater": " %",
            "rhr": " %",
            "noise": " %",
        }
        self.update_slider_readout(key, units[key])

    def scram_now(self) -> None:
        self.state.trip = True
        self.set_slider("rod", 100)
        self.set_slider("trim", 0)
        self.refresh_all(force=False)

    def step_once(self) -> None:
        for _ in range(20):
            self.step_model(0.05)
        self.refresh_all(force=False)

    def toggle_freeze(self) -> None:
        self.freeze_chart = not self.freeze_chart
        self.freeze_button.configure(text="UNFREEZE CHART" if self.freeze_chart else "FREEZE CHART")

    def _sync_auto_eccs(self) -> None:
        self.state.autoECCS = bool(self.auto_eccs_var.get())

    # ----------------------------- Demo mode ------------------------------

    def toggle_demo(self) -> None:
        if self.demo_mode:
            self.stop_demo()
        else:
            self.start_demo()

    def start_demo(self) -> None:
        """Start a deterministic teaching demonstration with an initiating fault and response."""
        self.running = False
        self.state.reset()
        self.scenario_normal()
        self.demo_mode = True
        self.demo_stage = "Demo armed: initial full-power operation"
        self.demo_start_t = self.state.t
        self.state.scenario_name = f"Demo: {self.demo_script_var.get()}"
        self.demo_button.configure(text="STOP DEMO")
        self.running = True
        self.run_button.configure(text="PAUSE")
        self.last_wall_time = time.perf_counter()
        self.refresh_all(force=True)

    def stop_demo(self) -> None:
        self.demo_mode = False
        self.demo_stage = "Demo stopped; manual control returned"
        if hasattr(self, "demo_button"):
            self.demo_button.configure(text="START DEMO")
        self.refresh_all(force=False)

    def set_controls(self, **kwargs: float) -> None:
        """Set controls only when they differ enough to avoid unnecessary GUI churn."""
        for key, value in kwargs.items():
            if key in self.control_vars and abs(self.control_vars[key].get() - float(value)) > 0.05:
                self.set_slider(key, float(value))

    def apply_demo_mode(self) -> None:
        if not self.demo_mode:
            return

        s = self.state
        rel = s.t - self.demo_start_t
        script = self.demo_script_var.get()
        s.scenario_name = f"Demo: {script}"

        if script == "SBLOCA recovery":
            if rel < 20:
                self.demo_stage = "Normal full-power operation before the fault."
                self.set_controls(rod=0, trim=0, boron=1000, pump=100, sg=100)
                self.set_slider("break", 0)
            elif rel < 35:
                self.demo_stage = "Fault inserted: small-break LOCA. Primary inventory and pressure begin to fall."
                self.set_controls(pump=75, sg=100, eccs=0, afw=0, porv=0, spray=0, rhr=0)
                self.set_slider("break", 12)
            elif rel < 65:
                self.demo_stage = "Protection response: reactor trip, rods inserted, decay heat remains."
                s.trip = True
                self.set_controls(rod=100, trim=0, pump=60, sg=100, eccs=0, afw=20, porv=0, spray=0, rhr=0)
                self.set_slider("break", 12)
            elif rel < 120:
                self.demo_stage = "Safety response: ECCS and auxiliary feedwater recover inventory and heat removal."
                s.trip = True
                self.set_controls(rod=100, pump=60, sg=100, eccs=65, afw=55, porv=0, spray=0, rhr=0)
                self.set_slider("break", 12)
            elif rel < 170:
                self.demo_stage = "Cooldown response: controlled depressurization prepares for residual heat removal."
                self.set_controls(eccs=55, afw=75, porv=18, spray=35, rhr=0)
                self.set_slider("break", 8)
            elif rel < 240:
                self.demo_stage = "Long-term response: break isolated in the model; RHR removes decay heat at low pressure."
                self.set_controls(eccs=35, afw=55, porv=8, spray=20, rhr=80)
                self.set_slider("break", 0)
            else:
                self.demo_stage = "Demo complete: plant stabilized in shutdown cooling. Manual control returned."
                self.stop_demo()

        elif script == "LBLOCA ECCS response":
            if rel < 15:
                self.demo_stage = "Normal full-power operation before the large-break LOCA."
                self.set_controls(rod=0, trim=0, pump=100, sg=100, eccs=0, afw=0, porv=0, spray=0, rhr=0)
                self.set_slider("break", 0)
            elif rel < 30:
                self.demo_stage = "Fault inserted: large break causes rapid depressurization and inventory loss."
                s.trip = True
                self.set_controls(rod=100, pump=0, sg=60, eccs=0, afw=0, porv=0, spray=0, rhr=0)
                self.set_slider("break", 70)
            elif rel < 90:
                self.demo_stage = "Emergency response: accumulators/LPSI surrogate inject strongly after pressure falls."
                s.trip = True
                self.set_controls(rod=100, pump=0, sg=60, eccs=100, afw=40, porv=0, spray=0, rhr=0)
                self.set_slider("break", 70)
            elif rel < 150:
                self.demo_stage = "Recovery response: break area is reduced and ECCS refloods the core."
                self.set_controls(eccs=100, afw=60, rhr=40)
                self.set_slider("break", 35)
            elif rel < 230:
                self.demo_stage = "Long-term cooling: break isolated, ECCS reduced, RHR maintains decay-heat removal."
                self.set_controls(eccs=45, afw=50, rhr=90, spray=20, porv=5)
                self.set_slider("break", 0)
            else:
                self.demo_stage = "Demo complete: long-term cooling established. Manual control returned."
                self.stop_demo()

        elif script == "Loss of heat sink recovery":
            if rel < 20:
                self.demo_stage = "Normal operation with steam generator heat removal available."
                self.set_controls(rod=0, trim=0, pump=100, sg=100, eccs=0, afw=0, porv=0, spray=0, rhr=0)
                self.set_slider("break", 0)
            elif rel < 45:
                self.demo_stage = "Fault inserted: main heat sink lost; pressure and coolant temperature rise."
                s.trip = True
                self.set_controls(rod=100, pump=80, sg=0, eccs=0, afw=0, porv=0, spray=0, rhr=0)
            elif rel < 90:
                self.demo_stage = "Operator response: auxiliary feedwater restores secondary-side heat removal."
                s.trip = True
                self.set_controls(rod=100, pump=80, sg=0, afw=90, spray=20, porv=0, eccs=0, rhr=0)
            elif rel < 150:
                self.demo_stage = "Pressure control: spray/PORV manage pressure while AFW removes decay heat."
                self.set_controls(afw=95, spray=55, porv=12, pump=60, rhr=0)
            elif rel < 230:
                self.demo_stage = "Cooldown: primary system depressurized enough for RHR contribution."
                self.set_controls(afw=60, spray=25, porv=8, pump=40, rhr=75)
            else:
                self.demo_stage = "Demo complete: decay heat removal restored. Manual control returned."
                self.stop_demo()

        elif script == "Station blackout recovery":
            if rel < 15:
                self.demo_stage = "Normal operation before loss of offsite and onsite AC power."
                self.set_controls(rod=0, trim=0, pump=100, sg=100, eccs=0, afw=0, porv=0, spray=0, rhr=0)
                self.set_slider("break", 0)
                self.auto_eccs_var.set(True)
            elif rel < 45:
                self.demo_stage = "Fault inserted: station blackout. Reactor trips; pumps and active injection are unavailable."
                s.trip = True
                self.auto_eccs_var.set(False)
                self.set_controls(rod=100, pump=0, sg=8, eccs=0, afw=10, porv=0, spray=0, heater=0, rhr=0)
            elif rel < 90:
                self.demo_stage = "Coping response: turbine-driven/portable feedwater surrogate removes some decay heat."
                s.trip = True
                self.set_controls(rod=100, pump=0, sg=8, eccs=0, afw=45, porv=0, spray=0, rhr=0)
            elif rel < 140:
                self.demo_stage = "Recovery response: power/injection restored; controlled depressurization begins."
                self.auto_eccs_var.set(True)
                self.set_controls(eccs=55, afw=80, porv=12, spray=25, pump=25, rhr=0)
            elif rel < 220:
                self.demo_stage = "Shutdown cooling: RHR becomes available as pressure falls."
                self.set_controls(eccs=45, afw=60, porv=10, spray=25, pump=35, rhr=85)
            else:
                self.demo_stage = "Demo complete: AC recovery and shutdown cooling established. Manual control returned."
                self.stop_demo()

    # ----------------------------- CSV logging ----------------------------

    def toggle_csv_logging(self) -> None:
        if self.csv_logging:
            self.stop_csv_logging()
        else:
            self.start_csv_logging()

    def start_csv_logging(self) -> None:
        default_name = f"lwr_th_loca_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(
            title="Save simulator CSV log",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            self.csv_file = open(path, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(self.csv_header())
            self.csv_file.flush()
            self.csv_path = path
            self.csv_last_logged_t = -1.0e9
            self.csv_logging = True
            if self.log_button is not None:
                self.log_button.configure(text="STOP CSV LOG")
            self.log_status_var.set(f"CSV logging: on → {path}")
        except OSError as exc:
            messagebox.showerror("CSV logging error", f"Could not open CSV file:\n{exc}")
            self.csv_logging = False

    def stop_csv_logging(self) -> None:
        if self.csv_file is not None:
            try:
                self.csv_file.flush()
                self.csv_file.close()
            finally:
                self.csv_file = None
                self.csv_writer = None
        self.csv_logging = False
        if self.log_button is not None:
            self.log_button.configure(text="START CSV LOG")
        if self.csv_path:
            self.log_status_var.set(f"CSV logging: saved → {self.csv_path}")
        else:
            self.log_status_var.set("CSV logging: off")

    @staticmethod
    def csv_header() -> List[str]:
        return [
            "time_s", "scenario", "demo_stage", "power_percent", "decay_heat_percent",
            "fuel_temp_C", "clad_temp_C", "coolant_temp_C", "pressure_MPa",
            "inventory_percent", "rho_pcm", "flow_percent", "trip", "auto_eccs", "auto_trip",
            "rod_percent", "trim_pcm", "boron_ppm", "pump_percent", "sg_percent",
            "break_percent", "eccs_percent", "afw_percent", "porv_percent", "spray_percent",
            "heater_percent", "rhr_percent",
        ]

    def write_csv_row(self, indicated_power: float, decay_frac_now: float, rho_total: float, flow_eff: float) -> None:
        if not self.csv_logging or self.csv_writer is None or self.csv_file is None:
            return
        s = self.state
        if s.t - self.csv_last_logged_t < self.csv_log_interval:
            return
        self.csv_last_logged_t = s.t
        row = [
            f"{s.t:.3f}", s.scenario_name, self.demo_stage, f"{indicated_power:.5g}", f"{100.0 * decay_frac_now:.5g}",
            f"{s.Tf:.5g}", f"{s.Tcl:.5g}", f"{s.Tc:.5g}", f"{s.P:.5g}",
            f"{100.0 * s.M:.5g}", f"{rho_total * 1.0e5:.5g}", f"{100.0 * flow_eff:.5g}",
            int(s.trip), int(self.auto_eccs_var.get()), int(self.auto_trip_var.get()),
            f"{self.control_vars['rod'].get():.5g}", f"{self.control_vars['trim'].get():.5g}",
            f"{self.control_vars['boron'].get():.5g}", f"{self.control_vars['pump'].get():.5g}",
            f"{self.control_vars['sg'].get():.5g}", f"{self.control_vars['break'].get():.5g}",
            f"{self.control_vars['eccs'].get():.5g}", f"{self.control_vars['afw'].get():.5g}",
            f"{self.control_vars['porv'].get():.5g}", f"{self.control_vars['spray'].get():.5g}",
            f"{self.control_vars['heater'].get():.5g}", f"{self.control_vars['rhr'].get():.5g}",
        ]
        self.csv_writer.writerow(row)
        if int(s.t * 10) % 20 == 0:
            self.csv_file.flush()

    # ----------------------------- Scenarios ------------------------------

    def scenario_normal(self) -> None:
        self.state.scenario_name = "Normal operation"
        self.state.trip = False
        self.set_slider("rod", 0)
        self.set_slider("trim", 0)
        self.set_slider("boron", 1000)
        self.set_slider("pump", 100)
        self.set_slider("sg", 100)
        self.set_slider("break", 0)
        self.set_slider("eccs", 0)
        self.set_slider("afw", 0)
        self.set_slider("porv", 0)
        self.set_slider("spray", 0)
        self.set_slider("heater", 0)
        self.set_slider("rhr", 0)
        self.auto_eccs_var.set(True)
        self.auto_trip_var.set(True)
        self.state.autoECCS = True
        self.refresh_all(force=False)

    def scenario_sbloc(self) -> None:
        self.state.scenario_name = "Small-break LOCA"
        self.state.trip = True
        self.set_slider("rod", 100)
        self.set_slider("trim", 0)
        self.set_slider("pump", 60)
        self.set_slider("sg", 100)
        self.set_slider("break", 12)
        self.set_slider("eccs", 0)
        self.set_slider("afw", 0)
        self.set_slider("porv", 0)
        self.set_slider("spray", 0)
        self.set_slider("heater", 0)
        self.set_slider("rhr", 0)
        self.auto_eccs_var.set(True)
        self.state.autoECCS = True
        self.refresh_all(force=False)

    def scenario_lbloc(self) -> None:
        self.state.scenario_name = "Large-break LOCA"
        self.state.trip = True
        self.set_slider("rod", 100)
        self.set_slider("trim", 0)
        self.set_slider("pump", 0)
        self.set_slider("sg", 60)
        self.set_slider("break", 70)
        self.set_slider("eccs", 0)
        self.set_slider("afw", 0)
        self.set_slider("porv", 0)
        self.set_slider("spray", 0)
        self.set_slider("heater", 0)
        self.set_slider("rhr", 0)
        self.auto_eccs_var.set(True)
        self.state.autoECCS = True
        self.refresh_all(force=False)

    def scenario_lofa(self) -> None:
        self.state.scenario_name = "Loss of flow accident"
        self.state.trip = True
        self.set_slider("rod", 100)
        self.set_slider("trim", 0)
        self.set_slider("pump", 0)
        self.set_slider("sg", 100)
        self.set_slider("break", 0)
        self.set_slider("eccs", 0)
        self.set_slider("afw", 0)
        self.set_slider("porv", 0)
        self.set_slider("spray", 0)
        self.set_slider("heater", 0)
        self.set_slider("rhr", 0)
        self.refresh_all(force=False)

    def scenario_lohs(self) -> None:
        self.state.scenario_name = "Loss of heat sink"
        self.state.trip = True
        self.set_slider("rod", 100)
        self.set_slider("trim", 0)
        self.set_slider("pump", 80)
        self.set_slider("sg", 0)
        self.set_slider("break", 0)
        self.set_slider("eccs", 0)
        self.set_slider("afw", 0)
        self.set_slider("porv", 0)
        self.set_slider("spray", 0)
        self.set_slider("heater", 0)
        self.set_slider("rhr", 0)
        self.refresh_all(force=False)

    def scenario_sbo(self) -> None:
        self.state.scenario_name = "Station blackout"
        self.state.trip = True
        self.set_slider("rod", 100)
        self.set_slider("trim", 0)
        self.set_slider("pump", 0)
        self.set_slider("sg", 8)
        self.set_slider("break", 0)
        self.set_slider("eccs", 0)
        self.set_slider("afw", 10)
        self.set_slider("porv", 0)
        self.set_slider("spray", 0)
        self.set_slider("heater", 0)
        self.set_slider("rhr", 0)
        self.auto_eccs_var.set(False)
        self.state.autoECCS = False
        self.refresh_all(force=False)

    # ----------------------------- Main loop ------------------------------

    def _schedule_loop(self) -> None:
        self.after_id = self.root.after(30, self._loop)

    def _loop(self) -> None:
        try:
            if self.running:
                now = time.perf_counter()
                wall_dt = now - self.last_wall_time
                self.last_wall_time = now
                wall_dt = max(0.01, min(wall_dt, 0.20))
                sim_dt = wall_dt * self.control_vars["speed"].get()
                nsub = max(1, int(math.ceil(sim_dt / 0.05)))
                dt = sim_dt / nsub
                for _ in range(nsub):
                    self.apply_demo_mode()
                    self.step_model(dt)
                self.refresh_all(force=False)
            else:
                self.last_wall_time = time.perf_counter()
        finally:
            self._schedule_loop()

    # ---------------------------- Model equations -------------------------

    @staticmethod
    def clamp(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    def pressure_eccs_factor(self, P: float) -> float:
        # Classroom-scale ECCS effectiveness increases continuously as system
        # pressure falls, avoiding numerical jumps at the teaching thresholds.
        if P > 14.0:
            f = 0.05
        elif P > 8.0:
            f = 0.05 + 0.65 * (14.0 - P) / 6.0
        elif P > 2.0:
            f = 0.70 + 0.30 * (8.0 - P) / 6.0
        else:
            f = 1.0
        return self.clamp(f, 0.05, 1.0)

    def step_model(self, dt: float) -> None:
        c = self.c
        s = self.state

        # Controls.
        rod_pct = self.control_vars["rod"].get()
        trim_pcm = self.control_vars["trim"].get()
        boron_ppm = self.control_vars["boron"].get()
        pump_pct = self.control_vars["pump"].get()
        sg_pct = self.control_vars["sg"].get()
        break_pct = self.control_vars["break"].get()
        eccs_pct = self.control_vars["eccs"].get()
        afw_pct = self.control_vars["afw"].get()
        porv_pct = self.control_vars["porv"].get()
        spray_pct = self.control_vars["spray"].get()
        heat_pct = self.control_vars["heater"].get()
        rhr_pct = self.control_vars["rhr"].get()

        # Automatic trip from high power, low inventory, high pressure, or high clad temp.
        if bool(self.auto_trip_var.get()):
            if (s.n > 1.18) or (s.P > c.pressHigh) or (s.M < 0.82) or (s.Tcl > c.cladWarn):
                s.trip = True

        if s.trip:
            rod_pct = 100.0
            trim_pcm = min(trim_pcm, 0.0)
            self.set_slider("rod", rod_pct)
            self.set_slider("trim", trim_pcm)

        # Reactivity in delta-k/k.
        rho_rods = -(c.rod_worth_pcm * rod_pct / 100.0) * 1e-5
        rho_trim = trim_pcm * 1e-5
        rho_boron = c.boron_worth * (boron_ppm - c.boron_ref)
        rho_f = c.alpha_f * (s.Tf - c.TrefFuel)
        rho_m = c.alpha_m * (s.Tc - c.TrefCool)
        rho_total = rho_rods + rho_trim + rho_boron + rho_f + rho_m
        rho_total = self.clamp(rho_total, -0.12, 0.012)

        # Six-group point kinetics.
        dn = ((rho_total - c.beta) / c.Lambda) * s.n + float(np.sum(c.lambda_i * s.Ci))
        dCi = (c.beta_i / c.Lambda) * s.n - c.lambda_i * s.Ci
        s.n += dt * dn
        s.Ci += dt * dCi
        s.n = self.clamp(s.n, 0.0, 2.5)
        s.Ci = np.maximum(s.Ci, 0.0)

        # Decay heat groups. At steady 100 percent power, prompt + decay heat = Pnom.
        dDi = c.decay_frac * s.n - c.decay_lambda * s.Di
        s.Di += dt * dDi
        s.Di = np.maximum(s.Di, 0.0)
        decay_frac_now = float(np.sum(c.decay_lambda * s.Di))

        Qfiss = c.Pnom_MW * c.prompt_frac * s.n
        Qdec = c.Pnom_MW * decay_frac_now
        Qgen = Qfiss + Qdec

        # Flow and inventory-dependent heat transfer.
        pump = max(0.0, pump_pct / 100.0)
        natural_circ = 0.035 + 0.08 * self.clamp(s.M, 0.0, 1.0)
        flow_eff = max(natural_circ, pump * math.sqrt(max(s.M, 0.02)))

        # Heat transfer collapses as inventory falls and the core uncovers.
        if s.M >= 0.75:
            coverage = 1.0
        elif s.M >= 0.35:
            coverage = 0.20 + 0.80 * (s.M - 0.35) / 0.40
        else:
            coverage = max(0.04, 0.20 * s.M / 0.35)

        two_phase_boost = 1.0 + 0.35 * self.clamp((s.Tc - 315.0) / 60.0, 0.0, 1.0)
        Kcc = c.Kcc_nom * coverage * (0.20 + 0.80 * flow_eff) * two_phase_boost
        Kcc = max(1.5, Kcc)

        Qfc = c.Kfc * (s.Tf - s.Tcl)
        Qcc = Kcc * (s.Tcl - s.Tc)

        # Steam generator / heat sink removal. AFW can partially restore secondary-side removal.
        sg = max(0.0, sg_pct / 100.0)
        afw = max(0.0, afw_pct / 100.0)
        sg_effective = min(1.40, sg + 0.65 * afw)
        Ksg = c.Ksg_nom * sg_effective * (0.20 + 0.80 * flow_eff) * max(0.05, min(1.2, s.M))
        Qsg = max(0.0, Ksg * (s.Tc - c.Tsink))

        # ECCS logic.
        s.autoECCS = bool(self.auto_eccs_var.get())
        auto_eccs = 0.0
        if s.autoECCS:
            if ((s.P < 12.0 and s.M < 0.92) or (s.Tcl > 450.0)):
                auto_eccs = max(auto_eccs, 0.35)
            if s.P < 4.5 and s.M < 1.05:
                auto_eccs = max(auto_eccs, 0.85)
            if s.P < 2.0 and s.M < 1.10:
                auto_eccs = max(auto_eccs, 1.00)
        eccs = max(eccs_pct / 100.0, auto_eccs)

        # Break flow, relief/PORV flow, and boiling inventory loss.
        brk = max(0.0, break_pct / 100.0)
        porv = max(0.0, porv_pct / 100.0)
        break_out = c.break_coeff * brk * math.sqrt(max(s.P - 0.10, 0.0))
        porv_out = c.porv_coeff * porv * math.sqrt(max(s.P - 0.10, 0.0))
        heat_imbalance = max(0.0, Qcc - Qsg)
        evap_loss = c.evap_coeff * heat_imbalance * self.clamp((s.Tc - 320.0) / 80.0, 0.0, 1.0)
        eccs_in = c.eccs_coeff * eccs * self.pressure_eccs_factor(s.P)

        s.M += dt * (eccs_in - break_out - porv_out - evap_loss)
        s.M = self.clamp(s.M, 0.05, 1.20)

        # ECCS and pressurizer spray cool the primary coolant by cold-water mixing surrogate.
        Teccs = 35.0
        Qeccs_cool = 0.0
        if eccs > 0.0:
            Qeccs_cool = 2400.0 * eccs * self.pressure_eccs_factor(s.P) * max(0.0, (s.Tc - Teccs) / 300.0)

        spray = max(0.0, spray_pct / 100.0)
        Qspray_cool = 350.0 * spray * max(0.0, (s.Tc - 60.0) / 300.0)

        # RHR/shutdown cooling is intentionally made mostly useful at low pressure.
        rhr = max(0.0, rhr_pct / 100.0)
        rhr_available = self.clamp((3.5 - s.P) / 2.5, 0.0, 1.0)
        Qrhr = 1800.0 * rhr * rhr_available * max(0.0, (s.Tc - 60.0) / 280.0)

        # Thermal ODEs.
        Ccool_eff = c.Ccool * max(0.08, s.M)
        dTf = (Qgen - Qfc) / c.Cfuel
        dTcl = (Qfc - Qcc) / c.Cclad
        dTc = (Qcc - Qsg - Qeccs_cool - Qspray_cool - Qrhr) / Ccool_eff

        s.Tf += dt * dTf
        s.Tcl += dt * dTcl
        s.Tc += dt * dTc
        s.Tf = self.clamp(s.Tf, 20.0, 2800.0)
        s.Tcl = self.clamp(s.Tcl, 20.0, 2200.0)
        s.Tc = self.clamp(s.Tc, 20.0, 650.0)

        # Pressure ODE. This is a compressed-water / flashing surrogate.
        pTarget = c.Pref + 0.045 * (s.Tc - c.TrefCool) + 7.0 * (s.M - 1.0)
        pTarget = self.clamp(pTarget, 0.10, 17.5)
        dp = (pTarget - s.P) / c.press_tau
        dp -= c.pbreak_coeff * brk * math.sqrt(max(s.P - 0.10, 0.0))
        dp -= c.pporv_coeff * porv * math.sqrt(max(s.P - 0.10, 0.0))
        dp -= 0.35 * spray * max(0.0, (s.P - 0.1) / 15.0)
        dp += 0.18 * max(0.0, heat_pct / 100.0) * max(0.0, (17.2 - s.P) / 15.0)
        dp += 0.28 * eccs_in
        s.P += dt * dp
        s.P = self.clamp(s.P, 0.10, 17.5)

        s.t += dt
        self.append_history(decay_frac_now, rho_total, flow_eff)

    def append_history(self, decay_frac_now: float, rho_total: float, flow_eff: float) -> None:
        s = self.state
        hist = s.hist
        noise_pct = self.control_vars["noise"].get() / 100.0
        indicated_power = max(0.0, 100.0 * s.n * (1.0 + noise_pct * np.random.randn()))

        hist.t.append(s.t)
        hist.pow.append(indicated_power)
        hist.dec.append(100.0 * decay_frac_now)
        hist.Tf.append(s.Tf)
        hist.Tcl.append(s.Tcl)
        hist.Tc.append(s.Tc)
        hist.P.append(s.P)
        hist.M.append(100.0 * s.M)
        hist.rho.append(rho_total * 1.0e5)
        hist.flow.append(100.0 * flow_eff)

        self.write_csv_row(indicated_power, decay_frac_now, rho_total, flow_eff)

    # ----------------------------- Screen update --------------------------

    def refresh_all(self, force: bool) -> None:
        if force or not self.freeze_chart:
            self.update_plots()
        self.update_readouts()

    @staticmethod
    def nanmax(v: np.ndarray, default: float = 1.0) -> float:
        if v.size == 0 or np.all(np.isnan(v)):
            return default
        return float(np.nanmax(v))

    def update_plots(self) -> None:
        hist = self.state.hist

        # Match the reactor simulator's strip-recorder behaviour: keep a fixed
        # 40-second time span so transient details do not become compressed as
        # the run grows longer. The chart initially shows 0-40 s, then scrolls
        # forward using absolute simulation time.
        visible_window_s = 40.0

        if len(hist.t) < 2:
            for line in (self.line_pow, self.line_dec, self.line_tf, self.line_tcl, self.line_tc, self.line_p, self.line_m):
                line.set_data([], [])
            for ax in (self.ax_power, self.ax_temp, self.ax_press):
                ax.set_xlim(0.0, visible_window_s)
            self.canvas.draw_idle()
            return

        x = hist.as_array("t")
        t_now = float(x[-1])
        if t_now <= visible_window_s:
            xmin, xmax = 0.0, visible_window_s
        else:
            xmin, xmax = t_now - visible_window_s, t_now

        pow_y = hist.as_array("pow")
        dec_y = hist.as_array("dec")
        self.line_pow.set_data(x, pow_y)
        self.line_dec.set_data(x, dec_y)
        y_max_power = max(120.0, 1.15 * self.nanmax(np.concatenate([pow_y, dec_y, np.array([110.0])]), 120.0))
        self.ax_power.set_xlim(xmin, xmax)
        self.ax_power.set_ylim(0.0, y_max_power)

        Tf_y = hist.as_array("Tf")
        Tcl_y = hist.as_array("Tcl")
        Tc_y = hist.as_array("Tc")
        self.line_tf.set_data(x, Tf_y)
        self.line_tcl.set_data(x, Tcl_y)
        self.line_tc.set_data(x, Tc_y)
        y_max_temp = max(450.0, min(2200.0, 1.10 * self.nanmax(np.concatenate([Tf_y, Tcl_y, Tc_y, np.array([400.0])]), 450.0)))
        self.ax_temp.set_xlim(xmin, xmax)
        self.ax_temp.set_ylim(0.0, y_max_temp)

        P_y = hist.as_array("P")
        M_y = hist.as_array("M") / 10.0
        self.line_p.set_data(x, P_y)
        self.line_m.set_data(x, M_y)
        self.ax_press.set_xlim(xmin, xmax)
        self.ax_press.set_ylim(0.0, 18.0)

        self.canvas.draw_idle()

    def update_readouts(self) -> None:
        s = self.state
        hist = s.hist
        if len(hist.t) > 0:
            rho_pcm = hist.rho[-1]
            flow_pct = hist.flow[-1]
            decay_pct = hist.dec[-1]
        else:
            rho_pcm = 0.0
            flow_pct = 100.0
            decay_pct = 6.5

        self.readout_vars["pow"].set(f"{100.0 * s.n:7.2f} %")
        self.readout_vars["dec"].set(f"{decay_pct:7.2f} %")
        self.readout_vars["flow"].set(f"{flow_pct:7.1f} %")
        self.readout_vars["p"].set(f"{s.P:7.2f} MPa")
        self.readout_vars["inv"].set(f"{100.0 * s.M:7.1f} %")
        self.readout_vars["tcl"].set(f"{s.Tcl:7.0f} C")
        self.readout_vars["tfuel"].set(f"{s.Tf:7.0f} C")
        self.readout_vars["rho"].set(f"{rho_pcm:7.0f} pcm")

        eccs_on = (
            self.control_vars["eccs"].get() > 1.0
            or (bool(self.auto_eccs_var.get()) and (((s.P < 12.0 and s.M < 0.92) or s.Tcl > 450.0)))
        )
        self.set_lamp("REACTOR TRIP", s.trip)
        self.set_lamp("ECCS ACTIVE", eccs_on)
        self.set_lamp("LOW INVENTORY", s.M < self.c.invLow)
        self.set_lamp("HIGH CLAD TEMP", s.Tcl > self.c.cladWarn)

        if s.Tcl > self.c.cladTrip:
            alarm = "SEVERE: cladding temperature above teaching limit. Discuss core uncovery and emergency cooling."
        elif s.M < self.c.invLow:
            alarm = "WARNING: low primary inventory. Heat transfer is degrading; observe PCT response."
        elif s.P > self.c.pressHigh:
            alarm = "WARNING: high primary pressure. Try trip, PORV/spray, AFW, or secondary heat removal."
        elif s.trip:
            alarm = "Reactor trip active. Fission power falls; decay heat remains and must be removed."
        else:
            alarm = "Stable. Try SBLOCA, LBLOCA, LOFA, LOHS or SBO presets, then adjust sliders manually."

        demo_text = f" | Demo: {self.demo_stage}" if self.demo_mode or self.demo_stage else ""
        log_text = " | CSV logging ON" if self.csv_logging else ""
        self.status_var.set(f"t = {s.t:.1f} s | Scenario: {s.scenario_name}{demo_text}{log_text} | {alarm}")

    def set_lamp(self, name: str, on: bool) -> None:
        lamp = self.lamps[name]
        if on:
            lamp.configure(bg="#bf0d05", fg="#ffffff")
        else:
            lamp.configure(bg="#1e1e1e", fg="#c8c8c8")

    def on_close(self) -> None:
        self.running = False
        self.demo_mode = False
        self.stop_csv_logging()
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    app = LWRTeachingSimulator(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    show_startup_splash(
        root,
        module_name="Thermal-Hydraulics and LOCA Simulator",
        duration_ms=2000,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
