#!/usr/bin/env python3
"""
REACTOR_TEACHING_SIMULATOR_MERGED_V7_CSV_EXPORT.PY

Merged teaching reactor simulator with fault injection, improved display layout, scrollable panes, and CSV export.

Author: Mohsin Mohd Sies
Affiliation: Nuclear Engineering Program, Faculty of Chemical and Energy
    Engineering, Universiti Teknologi Malaysia
Contact: mohsin.sies@gmail.com
Repository: https://github.com/open-nuclear-suite/OpenNuclearSuite
License: MIT

This version combines:
    - The V3C-style visual control-room / plant-mimic interface
    - The V2 Basic physics additions: soluble boron, iodine/xenon,
      decay heat, fuel/cladding/coolant thermal nodes, reactor period,
      and load-follow mode
    - A fault-injection panel for classroom diagnosis exercises
    - A revised display: 2x2 meters above a wider strip chart
    - Scrollable operator and plant-display panes for smaller screens
    - CSV export for student post-run analysis.

Run from the repository root with:
    python simulators/ReactorPhysicsSimulator/main.py

Dependencies:
    pip install numpy matplotlib

Tkinter is included with the standard Windows Python installer when its Tcl/Tk
optional feature is selected.

Important:
    This is a classroom toy model. Constants and time scales are deliberately
    adjusted for visualization. Do not use it for design, licensing, safety
    analysis, or real reactor operation.
"""

import csv
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import numpy as np

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import FancyBboxPatch, Rectangle


# ============================================================
# Branding and startup splash
# ============================================================

PROJECT_NAME = "Open Nuclear Engineering Teaching Suite"

ABOUT_MESSAGE = """Let Us Know Where This Software Is Used

We would be delighted to hear from educators, students, researchers, and other users of this software.

Please consider sending us a postcard or a short thank-you email describing:

• where you are using the software;
• how it is being used, such as for teaching, laboratory exercises, demonstrations, or self-study; and
• any comments or experiences you would like to share.

Postcards may be sent to:

Dean
Faculty of Chemical and Energy Engineering
Universiti Teknologi Malaysia
81310 UTM Skudai
Johor
Malaysia

Email: fcee@utm.my

Please mention that the software was developed by the Advanced Nuclear Engineering Research Group (ANERGy), Universiti Teknologi Malaysia.

Your message will help us understand the educational reach of the software and encourage its continued development. Thank you for using our software!"""


def show_suite_about(parent):
    """Show the suite-wide user outreach message in a dedicated window."""
    window = tk.Toplevel(parent)
    window.title("About — Open Nuclear Engineering Teaching Suite")
    window.geometry("720x650")
    window.minsize(560, 480)
    window.transient(parent)
    text = tk.Text(window, wrap=tk.WORD, padx=24, pady=20, font=("Segoe UI", 10), relief=tk.FLAT)
    text.pack(fill=tk.BOTH, expand=True)
    text.insert("1.0", ABOUT_MESSAGE)
    text.configure(state=tk.DISABLED)
    actions = ttk.Frame(window, padding=(16, 10))
    actions.pack(fill=tk.X)
    ttk.Button(actions, text="EMAIL FCEE", command=lambda: webbrowser.open("mailto:fcee@utm.my")).pack(side=tk.LEFT)
    ttk.Button(actions, text="CLOSE", command=window.destroy).pack(side=tk.RIGHT)
    window.focus_set()
SPLASH_LOGO_FILENAME = "UTM.logo.png"
BANNER_LOGO_FILENAME = "utm.fkt.logo.png"


KINETICS_PRESETS = {
    "Classroom": 0.080,
    "Intermediate": 0.020,
    "Advanced": 0.005,
    # Representative teaching value for a large thermal-power LWR.  This
    # profile uses adaptive internal RK4 substeps rather than the legacy Euler
    # update used by the three classroom-scaled presets.
    "Representative LWR": 2.0e-5,
}

REFERENCE_LWR_POWER_MWTH = 3000.0

# Effective whole-core teaching parameters for the Representative LWR profile.
# They are selected to reproduce the declared 565/425/345/285 C full-power
# equilibrium while preserving a transparent three-node energy balance.  They
# are not parameters from a specific commercial reactor.
REFERENCE_LWR_THERMAL = {
    "fuel_capacity_mj_per_k": 160.0,
    "clad_capacity_mj_per_k": 180.0,
    "coolant_capacity_mj_per_k": 900.0,
    "fuel_deposition_fraction": 0.97,
    "clad_deposition_fraction": 0.02,
    "coolant_deposition_fraction": 0.01,
    "fuel_clad_conductance_mw_per_k": 0.97 * REFERENCE_LWR_POWER_MWTH / 140.0,
    "clad_coolant_conductance_mw_per_k": 0.99 * REFERENCE_LWR_POWER_MWTH / 80.0,
    "heat_removal_conductance_mw_per_k": REFERENCE_LWR_POWER_MWTH / 60.0,
}

XENON_PRESETS = {
    # Multipliers are relative to the existing 60 s iodine / 90 s xenon demo.
    "Laboratory demo": 1.0,
    "Extended exercise": 5.0,
    "Reference trend": 360.0,
}

PHYSICS_PROFILES = (
    "Classroom model",
    "Advanced core physics",
)

INITIAL_CONDITIONS = (
    "Full-power equilibrium",
    "Subcritical startup",
)

CYCLE_PRESETS = {
    "Steady classroom": (0.0, 0.0, 0.0),
    "Beginning of cycle": (0.0, 420.0, 1000.0),
    "Middle of cycle": (210.0, 420.0, 500.0),
    "End of cycle": (420.0, 420.0, 0.0),
}


def kinetics_preset_label(name):
    value = KINETICS_PRESETS[name]
    if name == "Representative LWR":
        return f"{name} (Lambda = {value:.1e} s, {REFERENCE_LWR_POWER_MWTH:.0f} MWth)"
    return f"{name} (Lambda = {value:.3f} s)"


def xenon_preset_label(name):
    multiplier = XENON_PRESETS[name]
    iodine_half_time = 60.0 * multiplier
    xenon_half_time = 90.0 * multiplier
    return f"{name} (I-135 = {iodine_half_time:g} s, Xe-135 = {xenon_half_time:g} s)"


@dataclass(frozen=True)
class PedagogicalSettings:
    kinetics_preset: str = "Classroom"
    xenon_preset: str = "Laboratory demo"
    load_follow_period_s: float = 220.0
    physics_profile: str = "Classroom model"
    initial_condition: str = "Full-power equilibrium"
    cycle_preset: str = "Steady classroom"

    def __post_init__(self):
        if self.kinetics_preset not in KINETICS_PRESETS:
            raise ValueError(f"Unknown kinetics preset: {self.kinetics_preset}")
        if self.xenon_preset not in XENON_PRESETS:
            raise ValueError(f"Unknown xenon preset: {self.xenon_preset}")
        if not 60.0 <= self.load_follow_period_s <= 600.0:
            raise ValueError("Load-follow period must be between 60 and 600 s")
        if self.physics_profile not in PHYSICS_PROFILES:
            raise ValueError(f"Unknown physics profile: {self.physics_profile}")
        if self.initial_condition not in INITIAL_CONDITIONS:
            raise ValueError(f"Unknown initial condition: {self.initial_condition}")
        if self.cycle_preset not in CYCLE_PRESETS:
            raise ValueError(f"Unknown cycle preset: {self.cycle_preset}")
        if self.physics_profile == "Classroom model" and (
            self.initial_condition != "Full-power equilibrium" or self.cycle_preset != "Steady classroom"
        ):
            raise ValueError("Startup and cycle presets require the Advanced core physics profile")

    @property
    def prompt_generation_time_s(self):
        return KINETICS_PRESETS[self.kinetics_preset]

    @property
    def xenon_time_multiplier(self):
        return XENON_PRESETS[self.xenon_preset]

    @property
    def advanced_physics(self):
        return self.physics_profile == "Advanced core physics"

    @property
    def dimensioned_lwr(self):
        return self.kinetics_preset == "Representative LWR"

    @property
    def subcritical_startup(self):
        return self.initial_condition == "Subcritical startup"

    @property
    def is_baseline(self):
        return self == PedagogicalSettings()


def find_logo_path(filename):
    """Return the first available branding image with the requested filename.

    Repository-root, local, and current-working-directory locations are
    supported so the simulator can be launched from outside the repository.
    """
    candidates = [
        Path(__file__).resolve().parent / filename,
        Path(__file__).resolve().parent.parent / filename,
        Path(__file__).resolve().parent.parent / "assets" / filename,
        Path(__file__).resolve().parents[2] / filename,
        Path(__file__).resolve().parents[2] / "assets" / filename,
        Path.cwd() / filename,
        Path.cwd() / "assets" / filename,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_logo_image(master, max_width, max_height=None, filename=BANNER_LOGO_FILENAME):
    """Load a branding image and fit it proportionally inside a box.

    Pillow is used when available for smooth, exact resizing. If Pillow is not
    installed, Tkinter's built-in PNG loader is used with integer subsampling.
    Neither path crops the image.
    """
    logo_path = find_logo_path(filename)
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

def show_startup_splash(root, module_name, duration_ms=3000):
    """Show a centred, borderless project splash, then reveal the dashboard."""
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg="#0f1115")
    try:
        splash.attributes("-topmost", True)
    except tk.TclError:
        pass

    border = tk.Frame(splash, bg="#7d1238", padx=3, pady=3)
    border.pack(fill="both", expand=True)
    panel = tk.Frame(border, bg="#12161c", padx=34, pady=24)
    panel.pack(fill="both", expand=True)

    splash.logo_image = load_logo_image(
        splash,
        max_width=720,
        max_height=245,
        filename=SPLASH_LOGO_FILENAME,
    )
    if splash.logo_image is not None:
        tk.Label(panel, image=splash.logo_image, bg="#12161c", bd=0).pack(pady=(0, 18))
    else:
        tk.Label(
            panel, text="UTM", bg="#7d1238", fg="white",
            font=("Segoe UI", 34, "bold"), padx=34, pady=8,
        ).pack(pady=(0, 18))

    tk.Label(
        panel, text=PROJECT_NAME, bg="#12161c", fg="#f3f5f7",
        font=("Segoe UI", 21, "bold"),
    ).pack()
    tk.Label(
        panel, text=module_name, bg="#12161c", fg="#c7d1db",
        font=("Segoe UI", 11),
    ).pack(pady=(8, 0))

    splash.update_idletasks()
    width = splash.winfo_reqwidth()
    height = splash.winfo_reqheight()
    x = max(0, (splash.winfo_screenwidth() - width) // 2)
    y = max(0, (splash.winfo_screenheight() - height) // 2)
    splash.geometry(f"{width}x{height}+{x}+{y}")

    def close_splash():
        if splash.winfo_exists():
            splash.destroy()
        root.deiconify()
        root.lift()
        try:
            root.focus_force()
        except tk.TclError:
            pass

    root.after(duration_ms, close_splash)


# ============================================================
# Utilities
# ============================================================

def clamp(x, a, b):
    return min(max(x, a), b)


def fmt_period(period):
    if math.isinf(period) or math.isnan(period):
        return "stable"
    if period > 0:
        return f"rise {period:5.1f} s"
    return f"fall {abs(period):5.1f} s"


CRITICALITY_DEADBAND_PCM = 1.0


def classify_criticality(reactivity_pcm):
    """Classify core criticality from total reactivity.

    A small +/-1 pcm display deadband prevents the indicator from flickering
    around zero because of floating-point roundoff. This is an educational
    status indication, not a protection-system setpoint.
    """
    if reactivity_pcm < -CRITICALITY_DEADBAND_PCM:
        return "SUBCRITICAL"
    if reactivity_pcm > CRITICALITY_DEADBAND_PCM:
        return "SUPERCRITICAL"
    return "CRITICAL"


def rod_reactivity(position_pct, advanced=False):
    """Return rod reactivity for a withdrawn-position percentage."""
    position_pct = clamp(float(position_pct), 0.0, 100.0)
    if not advanced:
        return 1.0e-4 * (position_pct - 50.0)
    fraction = position_pct / 100.0
    integral_fraction = 3.0 * fraction**2 - 2.0 * fraction**3
    return 0.010 * (integral_fraction - 0.5)


def differential_rod_worth_pcm_per_pct(position_pct, advanced=False):
    """Return the local slope of the selected integral rod-worth curve."""
    if not advanced:
        return 10.0
    fraction = clamp(float(position_pct) / 100.0, 0.0, 1.0)
    return 1.0e5 * 0.010 * (6.0 * fraction - 6.0 * fraction**2) / 100.0


def rod_position_for_reactivity(target_rho, advanced=False):
    """Invert the monotonic rod-worth curve with a bounded bisection."""
    target_rho = clamp(float(target_rho), rod_reactivity(0.0, advanced), rod_reactivity(100.0, advanced))
    low, high = 0.0, 100.0
    for _ in range(50):
        middle = 0.5 * (low + high)
        if rod_reactivity(middle, advanced) < target_rho:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


FAULT_KEYS = [
    "fault_stuck_rod",
    "fault_partial_scram",
    "fault_pump_trip",
    "fault_heat_sink_loss",
    "fault_detector_bias",
    "fault_frozen_detector",
    "fault_boron_dilution",
    "fault_auto_failure",
    "fault_low_flow_trip_fail",
]


EXPORT_COLUMNS = [
    "time_s",
    "mode",
    "running",
    "scram_active",
    "kinetics_preset",
    "prompt_generation_time_s",
    "kinetics_integrator",
    "kinetics_substeps",
    "rated_power_mwth",
    "xenon_preset",
    "xenon_time_multiplier",
    "load_follow_period_s",
    "physics_profile",
    "initial_condition",
    "cycle_preset",
    "true_power_pct",
    "true_power_mwth",
    "measured_power_pct",
    "total_heat_pct",
    "total_heat_mwth",
    "decay_heat_pct",
    "decay_heat_mwth",
    "fuel_heat_capacity_mj_per_k",
    "clad_heat_capacity_mj_per_k",
    "coolant_heat_capacity_mj_per_k",
    "fuel_to_clad_heat_mw",
    "clad_to_coolant_heat_mw",
    "heat_removed_mw",
    "thermal_energy_residual_mw",
    "target_power_pct",
    "reactivity_pcm",
    "rho_rod_pcm",
    "rho_manual_pcm",
    "rho_temp_pcm",
    "rho_fuel_pcm",
    "rho_moderator_temp_pcm",
    "rho_density_pcm",
    "rho_void_pcm",
    "rho_boron_pcm",
    "rho_xenon_pcm",
    "rho_samarium_pcm",
    "rho_depletion_pcm",
    "period_s",
    "rod_position_pct",
    "boron_ppm",
    "iodine_index",
    "xenon_index",
    "promethium_index",
    "samarium_index",
    "moderator_density_relative",
    "void_fraction",
    "source_strength",
    "instrument_range",
    "log_neutron_level",
    "exposure_efpd",
    "fuel_temp_C",
    "clad_temp_C",
    "coolant_temp_C",
    "inlet_temp_C",
    "coolant_flow_pct",
    "heat_sink_pct",
    "fault_severity_pct",
    "active_faults",
    "precursor_C1",
    "precursor_C2",
    "precursor_C3",
    "precursor_C4",
    "precursor_C5",
    "precursor_C6",
] + FAULT_KEYS


# ============================================================
# Reactor model
# ============================================================

class ReactorState:
    def __init__(self, pedagogical_settings=None):
        self.pedagogical_settings = pedagogical_settings or PedagogicalSettings()
        # Simulation clock
        self.dt = 0.02
        self.time = 0.0
        self.running = False
        self.mode = "manual"       # manual, auto, load_follow
        self.scram = False

        # Six delayed neutron group point kinetics, typical thermal U-235 data.
        self.beta_i = np.array([0.000215, 0.001424, 0.001274, 0.002568, 0.000748, 0.000273], dtype=float)
        self.lambda_i = np.array([0.0124, 0.0305, 0.1110, 0.3010, 1.1400, 3.0100], dtype=float)
        self.beta = float(np.sum(self.beta_i))

        # Effective prompt generation time is slowed for classroom visualization.
        self.Lambda = self.pedagogical_settings.prompt_generation_time_s
        self.rated_power_mwth = (
            REFERENCE_LWR_POWER_MWTH if self.pedagogical_settings.dimensioned_lwr else None
        )
        self.kinetics_integrator = (
            "RK4 with automatic substeps" if self.pedagogical_settings.dimensioned_lwr
            else "Legacy explicit Euler"
        )
        self.kinetics_substeps = 1
        self.source = 1.0e-5 if self.pedagogical_settings.subcritical_startup else 1.0e-6
        self.source_strength = self.source

        # Nominal operating point.
        self.P = 1.0e-6 if self.pedagogical_settings.subcritical_startup else 1.00
        self.measuredPower = self.P
        self.measuredPct = 100.0 * self.P
        self.powerPct = 100.0 * self.P
        self.setpoint = 1.00
        self.period = math.inf

        # Decay heat groups. Fractions and time constants are classroom-scaled.
        self.decay_frac = np.array([0.040, 0.018, 0.007], dtype=float)
        self.decay_tau = np.array([12.0, 120.0, 1200.0], dtype=float)
        self.prompt_frac = 1.0 - float(np.sum(self.decay_frac))
        self.Dh = self.decay_frac * self.P
        self.Qdecay = float(np.sum(self.Dh))
        self.Qheat = self.prompt_frac * self.P + self.Qdecay

        # Iodine/xenon model. Time constants are intentionally accelerated.
        xenon_multiplier = self.pedagogical_settings.xenon_time_multiplier
        self.lambdaI = math.log(2) / (60.0 * xenon_multiplier)
        self.lambdaXe = math.log(2) / (90.0 * xenon_multiplier)
        self.xeBurn = 0.020
        self.iodineYield = self.lambdaI
        self.xeDirectYield = 0.00035
        self.xeWorth = 0.0040
        self.I = self.P
        self.Xe = (self.xeDirectYield * self.P + self.lambdaI * self.I) / (self.lambdaXe + self.xeBurn * self.P)

        # Optional advanced Pm-149/Sm-149 poisoning, normalized for teaching.
        self.lambdaPm = math.log(2) / (150.0 * xenon_multiplier)
        self.pmYield = 0.0040
        self.smBurn = 0.0080
        self.smWorth = 0.0020
        self.Pm = self.pmYield * self.P / self.lambdaPm
        self.Sm = self.pmYield / self.smBurn if self.P > 1.0e-4 else 0.0
        if self.pedagogical_settings.subcritical_startup:
            self.I = self.Xe = self.Pm = self.Sm = 0.0

        # Simplified teaching-cycle state. One simulated second represents one
        # EFPD only in the explicitly selected advanced cycle demonstrations.
        exposure, cycle_length, initial_boron = CYCLE_PRESETS[self.pedagogical_settings.cycle_preset]
        self.exposure_efpd = exposure
        self.cycle_length_efpd = cycle_length
        self.exposure_rate_efpd_per_s = 1.0 if cycle_length > 0.0 else 0.0
        self.rho_depletion = 0.0030 * max(0.0, 1.0 - exposure / cycle_length) if cycle_length else 0.0

        # Operator controls and reactivity worths.
        advanced = self.pedagogical_settings.advanced_physics
        initial_poison_rho = -self.xeWorth * self.Xe - (self.smWorth * self.Sm if advanced else 0.0)
        initial_boron_rho = -3.0e-6 * initial_boron
        target_rod_rho = -(initial_poison_rho + initial_boron_rho + (self.rho_depletion if advanced else 0.0))
        self.rod_pos = 25.0 if self.pedagogical_settings.subcritical_startup else rod_position_for_reactivity(target_rod_rho, advanced)
        self.rho_manual = 0.0
        self.boron_ppm = initial_boron if advanced else 0.0
        self.boron_coeff = 3.0e-6
        self.autoRodGain = 8.0                 # % rod per second per unit power error
        self.scram_rod_speed_pct_s = 100.0     # representative bank insertion, % travel/s
        self.loadFollowPeriod = self.pedagogical_settings.load_follow_period_s

        # Reactivity terms.
        self.rho_rods = 0.0
        self.rho_temp = 0.0
        self.rho_fuel = 0.0
        self.rho_moderator_temp = 0.0
        self.rho_density = 0.0
        self.rho_void = 0.0
        self.rho_boron = 0.0
        self.rho_xe = 0.0
        self.rho_sm = 0.0
        self.rho_total = 0.0
        self.reactivity_pcm = 0.0

        # Three-node thermal model: fuel / cladding / coolant.
        self.coolantFlow = 100.0
        self.heatSink = 100.0
        self.inletT = 285.0
        self.fuelT = 345.0 if self.pedagogical_settings.subcritical_startup else 565.0
        self.cladT = 345.0 if self.pedagogical_settings.subcritical_startup else 425.0
        self.coolT = 345.0
        self.Tf_ref = self.fuelT
        self.Tc_ref = self.coolT
        self.alpha_f = -3.0e-6
        self.alpha_c = -1.5e-6
        self.alpha_density = -8.0e-4
        self.alpha_void = -0.012
        self.moderator_density = 1.0
        self.void_fraction = 0.0
        self.tauF = 8.0
        self.tauCl = 5.0
        self.tauC = 18.0
        if self.pedagogical_settings.dimensioned_lwr:
            thermal = REFERENCE_LWR_THERMAL
            self.fuel_heat_capacity_mj_per_k = thermal["fuel_capacity_mj_per_k"]
            self.clad_heat_capacity_mj_per_k = thermal["clad_capacity_mj_per_k"]
            self.coolant_heat_capacity_mj_per_k = thermal["coolant_capacity_mj_per_k"]
        else:
            self.fuel_heat_capacity_mj_per_k = None
            self.clad_heat_capacity_mj_per_k = None
            self.coolant_heat_capacity_mj_per_k = None
        self.fuel_to_clad_heat_mw = 0.0
        self.clad_to_coolant_heat_mw = 0.0
        self.heat_removed_mw = 0.0
        self.thermal_energy_residual_mw = 0.0
        if self.pedagogical_settings.dimensioned_lwr:
            self.fuel_to_clad_heat_mw = (
                REFERENCE_LWR_THERMAL["fuel_clad_conductance_mw_per_k"]
                * (self.fuelT - self.cladT)
            )
            self.clad_to_coolant_heat_mw = (
                REFERENCE_LWR_THERMAL["clad_coolant_conductance_mw_per_k"]
                * (self.cladT - self.coolT)
            )
            self.heat_removed_mw = (
                REFERENCE_LWR_THERMAL["heat_removal_conductance_mw_per_k"]
                * (self.coolT - self.inletT)
            )

        # Delayed neutron precursors initialized at equilibrium.
        self.C = (self.beta_i / (self.Lambda * self.lambda_i)) * self.P

        # Instrument range is derived from true power; it never feeds kinetics.
        self.instrument_range = "POWER RANGE"
        self.log_neutron_level = math.log10(max(self.P, 1.0e-12))
        self.subcritical_multiplication = 1.0

        # Instrumentation noise.
        self.noiseAmp = 1.0                    # percent-like slider scale
        self.noiseState = 0.0
        self.noiseTau = 1.5

        # Trip settings.
        self.tripHighPower = 1.25
        self.tripHighHeat = 1.35
        self.tripHighFuelTemp = 900.0
        self.tripHighCladTemp = 650.0
        self.tripHighCoolTemp = 430.0
        self.tripLowFlow = 35.0
        self.tripInhibit = 1.0

        # Fault-injection controls. These are deliberately simple,
        # classroom-scaled faults for diagnosis exercises, not safety analysis.
        self.fault_severity = 60.0  # 0 to 100 percent
        self.fault_stuck_rod = False
        self.fault_partial_scram = False
        self.fault_pump_trip = False
        self.fault_heat_sink_loss = False
        self.fault_detector_bias = False
        self.fault_frozen_detector = False
        self.fault_boron_dilution = False
        self.fault_auto_failure = False
        self.fault_low_flow_trip_fail = False

        # Latched values used by some faults.
        self.stuck_rod_pos = None
        self.pump_trip_start_time = None
        self.pump_trip_initial_flow = self.coolantFlow
        self.heat_sink_loss_start_time = None
        self.heat_sink_initial = self.heatSink
        self.frozen_measured_power = None
        self.low_flow_trip_fail_announced = False

        # Histories for strip chart.
        self.histLen = 2200
        self.tHist = np.full(self.histLen, np.nan)
        self.pHist = np.full(self.histLen, np.nan)
        self.truePHist = np.full(self.histLen, np.nan)
        self.heatHist = np.full(self.histLen, np.nan)
        self.decayHist = np.full(self.histLen, np.nan)
        self.targetHist = np.full(self.histLen, np.nan)
        self.rHist = np.full(self.histLen, np.nan)
        self.tfHist = np.full(self.histLen, np.nan)

        self.logText = [
            "System ready. Press START to begin.",
            "Merged model: V3C panel + V2-style boron, Xe/I, decay heat, and 3-node thermal response.",
        ]

        # Full-resolution run data for CSV export. This is separate from the
        # rolling strip-chart arrays, so students can export the whole run.
        self.export_rows = []

        self.clockString = "0000.0 s"
        self.update_reactivity_terms()
        self.update_derived()
        self.push_history()

    def update_reactivity_terms(self):
        advanced = self.pedagogical_settings.advanced_physics
        self.rho_rods = rod_reactivity(self.rod_pos, advanced)
        self.rho_fuel = self.alpha_f * (self.fuelT - self.Tf_ref)
        self.rho_moderator_temp = self.alpha_c * (self.coolT - self.Tc_ref)
        if advanced:
            self.moderator_density = clamp(1.0 - 0.0015 * (self.coolT - self.Tc_ref), 0.70, 1.05)
            self.void_fraction = clamp((self.coolT - 390.0) / 80.0, 0.0, 0.25)
            self.rho_density = self.alpha_density * (1.0 - self.moderator_density)
            self.rho_void = self.alpha_void * self.void_fraction
        else:
            self.moderator_density = 1.0
            self.void_fraction = 0.0
            self.rho_density = 0.0
            self.rho_void = 0.0
        self.rho_temp = self.rho_fuel + self.rho_moderator_temp + self.rho_density + self.rho_void
        self.rho_boron = -self.boron_coeff * self.boron_ppm
        self.rho_xe = -self.xeWorth * self.Xe
        self.rho_sm = -self.smWorth * self.Sm if advanced else 0.0
        depletion = self.rho_depletion if advanced else 0.0
        self.rho_total = (
            self.rho_rods + self.rho_manual + self.rho_temp + self.rho_boron
            + self.rho_xe + self.rho_sm + depletion
        )
        self.rho_total = clamp(self.rho_total, -0.0250, 0.95 * self.beta)

    def update_derived(self):
        self.powerPct = 100.0 * self.P
        self.measuredPct = 100.0 * self.measuredPower
        self.heatPct = 100.0 * self.Qheat
        self.decayPct = 100.0 * self.Qdecay
        self.targetPct = 100.0 * self.setpoint
        self.reactivity_pcm = 1.0e5 * self.rho_total
        self.log_neutron_level = math.log10(max(self.P, 1.0e-12))
        if self.P < 1.0e-4:
            self.instrument_range = "SOURCE RANGE"
        elif self.P < 0.10:
            self.instrument_range = "INTERMEDIATE RANGE"
        else:
            self.instrument_range = "POWER RANGE"
        if self.rho_total < -1.0e-8:
            equilibrium_without_multiplication = max(self.source_strength, 1.0e-12)
            self.subcritical_multiplication = max(1.0, self.P / equilibrium_without_multiplication)
        else:
            self.subcritical_multiplication = math.inf
        self.clockString = f"{self.time:06.1f} s"

    def push_history(self):
        self.tHist = np.roll(self.tHist, -1)
        self.pHist = np.roll(self.pHist, -1)
        self.truePHist = np.roll(self.truePHist, -1)
        self.heatHist = np.roll(self.heatHist, -1)
        self.decayHist = np.roll(self.decayHist, -1)
        self.targetHist = np.roll(self.targetHist, -1)
        self.rHist = np.roll(self.rHist, -1)
        self.tfHist = np.roll(self.tfHist, -1)

        self.tHist[-1] = self.time
        self.pHist[-1] = self.measuredPct
        self.truePHist[-1] = self.powerPct
        self.heatHist[-1] = self.heatPct
        self.decayHist[-1] = self.decayPct
        self.targetHist[-1] = self.targetPct
        self.rHist[-1] = self.reactivity_pcm
        self.tfHist[-1] = self.fuelT / 10.0

        self.export_rows.append(self.make_export_row())

    def make_export_row(self):
        active_faults = "; ".join(self.active_fault_labels())
        row = {
            "time_s": self.time,
            "mode": self.mode,
            "running": int(self.running),
            "scram_active": int(self.scram),
            "kinetics_preset": self.pedagogical_settings.kinetics_preset,
            "prompt_generation_time_s": self.Lambda,
            "kinetics_integrator": self.kinetics_integrator,
            "kinetics_substeps": self.kinetics_substeps,
            "rated_power_mwth": "" if self.rated_power_mwth is None else self.rated_power_mwth,
            "xenon_preset": self.pedagogical_settings.xenon_preset,
            "xenon_time_multiplier": self.pedagogical_settings.xenon_time_multiplier,
            "load_follow_period_s": self.loadFollowPeriod,
            "physics_profile": self.pedagogical_settings.physics_profile,
            "initial_condition": self.pedagogical_settings.initial_condition,
            "cycle_preset": self.pedagogical_settings.cycle_preset,
            "true_power_pct": self.powerPct,
            "true_power_mwth": "" if self.rated_power_mwth is None else self.rated_power_mwth * self.P,
            "measured_power_pct": self.measuredPct,
            "total_heat_pct": self.heatPct,
            "total_heat_mwth": "" if self.rated_power_mwth is None else self.rated_power_mwth * self.Qheat,
            "decay_heat_pct": self.decayPct,
            "decay_heat_mwth": "" if self.rated_power_mwth is None else self.rated_power_mwth * self.Qdecay,
            "fuel_heat_capacity_mj_per_k": "" if self.fuel_heat_capacity_mj_per_k is None else self.fuel_heat_capacity_mj_per_k,
            "clad_heat_capacity_mj_per_k": "" if self.clad_heat_capacity_mj_per_k is None else self.clad_heat_capacity_mj_per_k,
            "coolant_heat_capacity_mj_per_k": "" if self.coolant_heat_capacity_mj_per_k is None else self.coolant_heat_capacity_mj_per_k,
            "fuel_to_clad_heat_mw": "" if self.rated_power_mwth is None else self.fuel_to_clad_heat_mw,
            "clad_to_coolant_heat_mw": "" if self.rated_power_mwth is None else self.clad_to_coolant_heat_mw,
            "heat_removed_mw": "" if self.rated_power_mwth is None else self.heat_removed_mw,
            "thermal_energy_residual_mw": "" if self.rated_power_mwth is None else self.thermal_energy_residual_mw,
            "target_power_pct": self.targetPct,
            "reactivity_pcm": self.reactivity_pcm,
            "rho_rod_pcm": 1.0e5 * self.rho_rods,
            "rho_manual_pcm": 1.0e5 * self.rho_manual,
            "rho_temp_pcm": 1.0e5 * self.rho_temp,
            "rho_fuel_pcm": 1.0e5 * self.rho_fuel,
            "rho_moderator_temp_pcm": 1.0e5 * self.rho_moderator_temp,
            "rho_density_pcm": 1.0e5 * self.rho_density,
            "rho_void_pcm": 1.0e5 * self.rho_void,
            "rho_boron_pcm": 1.0e5 * self.rho_boron,
            "rho_xenon_pcm": 1.0e5 * self.rho_xe,
            "rho_samarium_pcm": 1.0e5 * self.rho_sm,
            "rho_depletion_pcm": 1.0e5 * (self.rho_depletion if self.pedagogical_settings.advanced_physics else 0.0),
            "period_s": "stable" if (math.isinf(self.period) or math.isnan(self.period)) else self.period,
            "rod_position_pct": self.rod_pos,
            "boron_ppm": self.boron_ppm,
            "iodine_index": self.I,
            "xenon_index": self.Xe,
            "promethium_index": self.Pm,
            "samarium_index": self.Sm,
            "moderator_density_relative": self.moderator_density,
            "void_fraction": self.void_fraction,
            "source_strength": self.source_strength,
            "instrument_range": self.instrument_range,
            "log_neutron_level": self.log_neutron_level,
            "exposure_efpd": self.exposure_efpd,
            "fuel_temp_C": self.fuelT,
            "clad_temp_C": self.cladT,
            "coolant_temp_C": self.coolT,
            "inlet_temp_C": self.inletT,
            "coolant_flow_pct": self.coolantFlow,
            "heat_sink_pct": self.heatSink,
            "fault_severity_pct": self.fault_severity,
            "active_faults": active_faults,
        }

        # Include delayed neutron precursor values and individual fault flags so
        # students can filter and compare transients in a spreadsheet.
        for i, value in enumerate(self.C, start=1):
            row[f"precursor_C{i}"] = value
        for key in FAULT_KEYS:
            row[key] = int(bool(getattr(self, key)))
        return row

    def fault_fraction(self):
        return clamp(self.fault_severity / 100.0, 0.0, 1.0)

    def active_fault_labels(self):
        names = []
        if self.fault_stuck_rod:
            names.append("stuck rod")
        if self.fault_partial_scram:
            names.append("partial SCRAM")
        if self.fault_pump_trip:
            names.append("pump trip")
        if self.fault_heat_sink_loss:
            names.append("heat-sink loss")
        if self.fault_detector_bias:
            names.append("detector bias")
        if self.fault_frozen_detector:
            names.append("frozen detector")
        if self.fault_boron_dilution:
            names.append("boron dilution")
        if self.fault_auto_failure:
            names.append("auto failure")
        if self.fault_low_flow_trip_fail:
            names.append("low-flow trip fail")
        return names

    def add_log(self, msg):
        stamp = f"[t={self.time:6.1f} s] {msg}"
        self.logText.append(stamp)
        if len(self.logText) > 20:
            self.logText = self.logText[-20:]


class ReactorModel:
    def __init__(self):
        self.s = ReactorState()

    def reset(self, pedagogical_settings=None):
        settings = pedagogical_settings or self.s.pedagogical_settings
        self.s = ReactorState(settings)

    def export_csv(self, filepath):
        # Make sure the most recent displayed state is represented, even if the
        # simulator is paused immediately before export.
        if not self.s.export_rows or self.s.export_rows[-1].get("time_s") != self.s.time:
            self.s.update_reactivity_terms()
            self.s.update_derived()
            self.s.export_rows.append(self.s.make_export_row())

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.s.export_rows)
        return len(self.s.export_rows)

    @staticmethod
    def _kinetics_derivative(state, power, precursors):
        delayed_source = float(np.sum(state.lambda_i * precursors))
        power_rate = (
            ((state.rho_total - state.beta) / state.Lambda) * power
            + delayed_source
            + state.source_strength
        )
        precursor_rate = (state.beta_i / state.Lambda) * power - state.lambda_i * precursors
        return power_rate, precursor_rate

    def _advance_point_kinetics(self):
        """Advance neutron power and precursors over one global model step.

        Existing classroom presets retain the historical Euler calculation.
        The dimensioned LWR preset uses RK4 substeps sized from the fast prompt
        mode, avoiding a globally tiny timestep for thermal and poison states.
        Reactivity and source are held constant during this 20 ms outer step.
        """
        state = self.s
        if not state.pedagogical_settings.dimensioned_lwr:
            old_precursors = state.C.copy()
            power_rate, precursor_rate = self._kinetics_derivative(
                state, state.P, old_precursors
            )
            state.P = clamp(state.P + power_rate * state.dt, 1.0e-8, 3.0)
            state.C = np.maximum(old_precursors + precursor_rate * state.dt, 0.0)
            state.kinetics_substeps = 1
            return

        # Resolve the near-critical prompt-mode time constant Lambda / beta
        # with at least five RK4 steps.  This is an accuracy policy rather than
        # a wall-clock speed setting.
        maximum_step = max(1.0e-6, 0.20 * state.Lambda / state.beta)
        substeps = max(1, int(math.ceil(state.dt / maximum_step)))
        step = state.dt / substeps
        power = state.P
        precursors = state.C.copy()

        for _ in range(substeps):
            k1p, k1c = self._kinetics_derivative(state, power, precursors)
            k2p, k2c = self._kinetics_derivative(
                state, power + 0.5 * step * k1p, precursors + 0.5 * step * k1c
            )
            k3p, k3c = self._kinetics_derivative(
                state, power + 0.5 * step * k2p, precursors + 0.5 * step * k2c
            )
            k4p, k4c = self._kinetics_derivative(
                state, power + step * k3p, precursors + step * k3c
            )
            power += (step / 6.0) * (k1p + 2.0 * k2p + 2.0 * k3p + k4p)
            precursors += (step / 6.0) * (k1c + 2.0 * k2c + 2.0 * k3c + k4c)

        state.P = clamp(float(power), 1.0e-8, 3.0)
        state.C = np.maximum(precursors, 0.0)
        state.kinetics_substeps = substeps

    def _advance_thermal_nodes(self):
        """Advance either the legacy response model or the LWR energy balance."""
        state = self.s
        flow = max(state.coolantFlow / 100.0, 0.20)
        sink = max(state.heatSink / 100.0, 0.30)
        state.inletT = 285.0 + 5.0 * (1.0 - flow) - 8.0 * (sink - 1.0)

        if not state.pedagogical_settings.dimensioned_lwr:
            cool_eq = state.inletT + 60.0 * state.Qheat / (flow * sink)
            clad_eq = cool_eq + 80.0 * state.Qheat / flow
            fuel_eq = clad_eq + 140.0 * state.Qheat / flow
            state.fuelT += ((fuel_eq - state.fuelT) / state.tauF) * state.dt
            state.cladT += ((clad_eq - state.cladT) / state.tauCl) * state.dt
            state.coolT += ((cool_eq - state.coolT) / state.tauC) * state.dt
            return

        thermal = REFERENCE_LWR_THERMAL
        generated_heat_mw = state.rated_power_mwth * state.Qheat
        fuel_deposition_mw = thermal["fuel_deposition_fraction"] * generated_heat_mw
        clad_deposition_mw = thermal["clad_deposition_fraction"] * generated_heat_mw
        coolant_deposition_mw = thermal["coolant_deposition_fraction"] * generated_heat_mw

        fuel_clad_conductance = thermal["fuel_clad_conductance_mw_per_k"] * flow
        clad_coolant_conductance = thermal["clad_coolant_conductance_mw_per_k"] * flow
        removal_conductance = thermal["heat_removal_conductance_mw_per_k"] * flow * sink

        state.fuel_to_clad_heat_mw = fuel_clad_conductance * (state.fuelT - state.cladT)
        state.clad_to_coolant_heat_mw = clad_coolant_conductance * (state.cladT - state.coolT)
        state.heat_removed_mw = removal_conductance * (state.coolT - state.inletT)

        fuel_storage_mw = fuel_deposition_mw - state.fuel_to_clad_heat_mw
        clad_storage_mw = (
            clad_deposition_mw + state.fuel_to_clad_heat_mw - state.clad_to_coolant_heat_mw
        )
        coolant_storage_mw = (
            coolant_deposition_mw + state.clad_to_coolant_heat_mw - state.heat_removed_mw
        )
        state.thermal_energy_residual_mw = (
            fuel_storage_mw + clad_storage_mw + coolant_storage_mw
            - (generated_heat_mw - state.heat_removed_mw)
        )

        # MW is MJ/s, so division by the effective MJ/K inventories gives K/s.
        state.fuelT += fuel_storage_mw / state.fuel_heat_capacity_mj_per_k * state.dt
        state.cladT += clad_storage_mw / state.clad_heat_capacity_mj_per_k * state.dt
        state.coolT += coolant_storage_mw / state.coolant_heat_capacity_mj_per_k * state.dt

    def advance(self, seconds_to_advance):
        s = self.s
        nsteps = max(1, int(round(seconds_to_advance / s.dt)))

        for _ in range(nsteps):
            p_old = s.P

            sev = s.fault_fraction()

            if s.pedagogical_settings.advanced_physics and s.cycle_length_efpd > 0.0:
                s.exposure_efpd = min(
                    s.cycle_length_efpd,
                    s.exposure_efpd + s.P * s.exposure_rate_efpd_per_s * s.dt,
                )
                s.rho_depletion = 0.0030 * max(
                    0.0, 1.0 - s.exposure_efpd / s.cycle_length_efpd,
                )

            # Load-follow demonstration changes demanded power slowly.
            if s.mode == "load_follow" and not s.scram:
                s.setpoint = 0.85 + 0.20 * math.sin(2.0 * math.pi * s.time / s.loadFollowPeriod)
                s.setpoint = clamp(s.setpoint, 0.30, 1.10)

            # Boron dilution: a slow positive-reactivity insertion as boron is removed.
            if s.fault_boron_dilution and s.boron_ppm > 0.0:
                dilution_rate_ppm_s = 0.20 + 1.80 * sev
                s.boron_ppm = max(0.0, s.boron_ppm - dilution_rate_ppm_s * s.dt)

            # Auto modes move the control rods physically. Faults can disable the
            # controller or freeze the actuator to create diagnosis exercises.
            if s.mode in ("auto", "load_follow") and not s.scram:
                if not s.fault_auto_failure and not s.fault_stuck_rod:
                    err = s.setpoint - s.P
                    rod_rate = clamp(s.autoRodGain * err, -1.2, 1.2)  # % withdrawn per second
                    s.rod_pos = clamp(s.rod_pos + rod_rate * s.dt, 0.0, 100.0)

            # SCRAM insertion. With partial-SCRAM fault, rods stop above the
            # fully inserted position; with stuck-rod fault, the rod bank freezes.
            if s.scram and not s.fault_stuck_rod:
                if s.fault_partial_scram:
                    failed_scram_rod_pos = 5.0 + 35.0 * sev
                    if s.pedagogical_settings.dimensioned_lwr:
                        s.rod_pos = max(
                            failed_scram_rod_pos,
                            s.rod_pos - s.scram_rod_speed_pct_s * s.dt,
                        )
                    else:
                        s.rod_pos = clamp(failed_scram_rod_pos, 0.0, 45.0)
                else:
                    if s.pedagogical_settings.dimensioned_lwr:
                        s.rod_pos = max(0.0, s.rod_pos - s.scram_rod_speed_pct_s * s.dt)
                    else:
                        s.rod_pos = 0.0

            if s.fault_stuck_rod and s.stuck_rod_pos is not None:
                s.rod_pos = clamp(s.stuck_rod_pos, 0.0, 100.0)

            # Pump trip and heat-sink loss override the operator sliders while active.
            if s.fault_pump_trip:
                if s.pump_trip_start_time is None:
                    s.pump_trip_start_time = s.time
                    s.pump_trip_initial_flow = s.coolantFlow
                t_fault = max(0.0, s.time - s.pump_trip_start_time)
                target_flow = 45.0 - 30.0 * sev      # 45% mild, 15% severe
                tau_pump = 6.0 + 18.0 * (1.0 - sev) # faster coastdown when severe
                s.coolantFlow = target_flow + (s.pump_trip_initial_flow - target_flow) * math.exp(-t_fault / tau_pump)
                s.coolantFlow = clamp(s.coolantFlow, 5.0, 120.0)

            if s.fault_heat_sink_loss:
                if s.heat_sink_loss_start_time is None:
                    s.heat_sink_loss_start_time = s.time
                    s.heat_sink_initial = s.heatSink
                t_fault = max(0.0, s.time - s.heat_sink_loss_start_time)
                target_sink = 70.0 - 40.0 * sev      # 70% mild, 30% severe
                tau_sink = 8.0
                s.heatSink = target_sink + (s.heat_sink_initial - target_sink) * math.exp(-t_fault / tau_sink)
                s.heatSink = clamp(s.heatSink, 10.0, 120.0)

            # Explicit integration substeps.
            s.update_reactivity_terms()

            self._advance_point_kinetics()

            # Decay heat groups build during operation and remain after SCRAM.
            dDh = (s.decay_frac * s.P - s.Dh) / s.decay_tau
            s.Dh = np.maximum(s.Dh + dDh * s.dt, 0.0)
            s.Qdecay = float(np.sum(s.Dh))
            s.Qheat = s.prompt_frac * s.P + s.Qdecay

            # Iodine/xenon poisoning.
            dI = s.iodineYield * s.P - s.lambdaI * s.I
            dXe = (
                s.xeDirectYield * s.P
                + s.lambdaI * s.I
                - s.lambdaXe * s.Xe
                - s.xeBurn * s.P * s.Xe
            )
            s.I = max(s.I + dI * s.dt, 0.0)
            s.Xe = max(s.Xe + dXe * s.dt, 0.0)
            if s.pedagogical_settings.advanced_physics:
                dPm = s.pmYield * s.P - s.lambdaPm * s.Pm
                dSm = s.lambdaPm * s.Pm - s.smBurn * s.P * s.Sm
                s.Pm = max(s.Pm + dPm * s.dt, 0.0)
                s.Sm = max(s.Sm + dSm * s.dt, 0.0)

            # Three-node thermal response.  The Representative LWR profile uses
            # a dimensional MW/MJ energy balance; legacy profiles retain their
            # historical equilibrium-response equations.
            self._advance_thermal_nodes()

            # Noisy indicated neutron power, with mild temporal correlation.
            phi = math.exp(-s.dt / max(0.2, s.noiseTau))
            sigma = 0.01 * s.noiseAmp
            s.noiseState = phi * s.noiseState + math.sqrt(max(0.0, 1.0 - phi**2)) * sigma * np.random.randn()
            if s.pedagogical_settings.advanced_physics:
                detector_noise = max(s.P * 0.002, 1.0e-10) * np.random.randn()
            else:
                detector_noise = 0.0005 * np.random.randn()
            indicated_power = max(0.0, s.P * (1.0 + s.noiseState) + detector_noise)

            # Instrumentation faults: detector bias reads high; frozen signal
            # holds the value latched when the fault was switched on.
            if s.fault_detector_bias:
                indicated_power *= (1.0 + 0.30 * sev)
            if s.fault_frozen_detector:
                if s.frozen_measured_power is None:
                    s.frozen_measured_power = indicated_power
                indicated_power = s.frozen_measured_power
            s.measuredPower = max(0.0, indicated_power)

            # Reactor period estimate from true neutron power trend.
            true_dPdt = (s.P - p_old) / s.dt
            if abs(true_dPdt) < 1.0e-9 or s.P < 1.0e-7:
                s.period = math.inf
            else:
                s.period = s.P / true_dPdt

            # Automatic protection trips. A low-flow trip-channel failure
            # suppresses only the low-flow trip; high power/temperature trips remain.
            low_flow_trip = s.coolantFlow < s.tripLowFlow
            if low_flow_trip and s.fault_low_flow_trip_fail and not s.low_flow_trip_fail_announced:
                s.add_log("FAULT: low-flow trip channel failed; no SCRAM from low-flow signal.")
                s.low_flow_trip_fail_announced = True
            effective_low_flow_trip = low_flow_trip and not s.fault_low_flow_trip_fail

            if (s.time > s.tripInhibit) and (not s.scram) and (
                s.P > s.tripHighPower
                or s.Qheat > s.tripHighHeat
                or s.fuelT > s.tripHighFuelTemp
                or s.cladT > s.tripHighCladTemp
                or s.coolT > s.tripHighCoolTemp
                or effective_low_flow_trip
            ):
                s.scram = True
                s.add_log("*** AUTOMATIC SCRAM ACTUATED ***")

            s.time += s.dt
            s.update_reactivity_terms()
            s.update_derived()
            s.push_history()

    def compose_readout(self):
        s = self.s
        cstr = "[{:5.2f} {:5.2f} {:5.2f} {:5.2f} {:5.2f} {:5.2f}]".format(*s.C)
        active_faults = s.active_fault_labels()
        fault_line = "None" if not active_faults else ", ".join(active_faults)
        out = [
            f"Physics: {s.pedagogical_settings.physics_profile}  |  Initial: {s.pedagogical_settings.initial_condition}",
            f"Mode: {s.mode.upper().replace('_', '-')}       Period: {fmt_period(s.period)}",
            f"Criticality: {classify_criticality(s.reactivity_pcm):<13}  |  Reactivity: {s.reactivity_pcm:+7.1f} pcm",
            f"Active faults: {fault_line}  |  Fault severity: {s.fault_severity:4.0f}%",
            f"Clock: {s.time:8.2f} s",
            f"Measured / true neutron power: {s.measuredPct:7.2f} / {s.powerPct:7.2f} %",
            f"Total heat / decay heat:       {s.heatPct:7.2f} / {s.decayPct:7.2f} %",
            f"Target power:                  {s.targetPct:7.2f} %",
            f"Total reactivity:              {s.reactivity_pcm:7.1f} pcm",
            f"rho_rod / manual / temp:        {1e5*s.rho_rods:7.1f} / {1e5*s.rho_manual:7.1f} / {1e5*s.rho_temp:7.1f} pcm",
            f"rho_boron / rho_xe:             {1e5*s.rho_boron:7.1f} / {1e5*s.rho_xe:7.1f} pcm",
            f"Rod position:                  {s.rod_pos:7.1f} % withdrawn",
            f"Boron concentration:            {s.boron_ppm:7.0f} ppm equivalent",
            f"Fuel / clad / coolant temp:     {s.fuelT:7.1f} / {s.cladT:7.1f} / {s.coolT:7.1f} C",
            f"Coolant flow / heat sink:       {s.coolantFlow:7.1f} / {s.heatSink:7.1f} %",
            f"Iodine / Xenon index:           {s.I:7.3f} / {s.Xe:7.3f}",
            f"Promethium / Samarium index:    {s.Pm:7.3f} / {s.Sm:7.3f}",
            f"C1..C6: {cstr}",
            "---- Event Log ----",
        ]
        if s.rated_power_mwth is not None:
            out.insert(
                6,
                f"Reference thermal power:       {s.rated_power_mwth * s.P:7.1f} / {s.rated_power_mwth:7.1f} MWth",
            )
            out.insert(
                7,
                f"Kinetics: {s.kinetics_integrator} ({s.kinetics_substeps} substeps per {s.dt:g} s)",
            )
            out.insert(
                8,
                f"Core heat / removed:           {s.rated_power_mwth * s.Qheat:7.1f} / {s.heat_removed_mw:7.1f} MW",
            )
        out.extend(s.logText)
        return out


# ============================================================
# Embedded matplotlib display panel
# ============================================================

class PlantDisplay:
    def __init__(self, parent):
        # Revised V6 layout:
        #   - mimic diagram in the upper-left
        #   - four meters in a 2 x 2 block in the upper-right
        #   - a wider/taller strip chart spanning the lower area
        self.figure = Figure(figsize=(10.8, 7.4), dpi=100, facecolor=(0.08, 0.09, 0.11))
        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.widget = self.canvas.get_tk_widget()

        self.axMimic = self.figure.add_axes([0.04, 0.56, 0.44, 0.38], facecolor=(0.05, 0.06, 0.07))
        self.axMeter1 = self.figure.add_axes([0.53, 0.76, 0.19, 0.17], facecolor=(0.08, 0.09, 0.11))
        self.axMeter2 = self.figure.add_axes([0.76, 0.76, 0.19, 0.17], facecolor=(0.08, 0.09, 0.11))
        self.axMeter3 = self.figure.add_axes([0.53, 0.56, 0.19, 0.17], facecolor=(0.08, 0.09, 0.11))
        self.axMeter4 = self.figure.add_axes([0.76, 0.56, 0.19, 0.17], facecolor=(0.08, 0.09, 0.11))
        self.axChart = self.figure.add_axes([0.06, 0.08, 0.90, 0.38], facecolor=(0.02, 0.03, 0.04))

    def refresh(self, s):
        self.draw_mimic(self.axMimic, s)
        self.draw_strip_chart(self.axChart, s)
        self.draw_meter(self.axMeter1, s.measuredPct, 0, 200, "MEAS. POWER %", [0.35, 0.95, 0.35])
        self.draw_meter(self.axMeter2, s.reactivity_pcm, -2500, 700, "REACTIVITY pcm", [0.98, 0.78, 0.20])
        self.draw_meter(self.axMeter3, s.fuelT, 250, 900, "FUEL TEMP C", [1.00, 0.42, 0.22])
        self.draw_meter(self.axMeter4, s.coolantFlow, 0, 120, "FLOW %", [0.35, 0.75, 1.00])
        self.canvas.draw_idle()

    @staticmethod
    def draw_strip_chart(ax, s):
        ax.clear()
        valid = ~np.isnan(s.tHist)
        t = s.tHist[valid]
        ax.set_facecolor((0.02, 0.03, 0.04))

        # Keep all chart text readable against the dark recorder background.
        ax.set_xlabel("Simulation time (s)", color="white")
        ax.set_ylabel("Power / heat (% full power)", color="white")
        ax.set_title(
            "Wide Strip Chart: neutron power, total heat, decay heat, and target",
            color="white",
            fontweight="bold",
        )
        ax.tick_params(axis="both", colors="white")
        for spine in ax.spines.values():
            spine.set_color("white")
        ax.grid(True, color=(0.20, 0.35, 0.20), alpha=0.45)

        # The recorder shows absolute simulation time. The first frame covers
        # 0-40 s; after 40 s the window advances continuously with the trace.
        visible_window_s = 40.0
        if len(t) == 0:
            ax.set_xlim(0.0, visible_window_s)
            ax.set_ylim(0.0, 120.0)
            return

        ax.plot(t, s.pHist[valid], color=(0.35, 1.0, 0.35), linewidth=1.7)
        ax.plot(t, s.truePHist[valid], color=(0.55, 0.75, 1.0), linestyle=":", linewidth=1.2)
        ax.plot(t, s.heatHist[valid], color=(1.0, 0.78, 0.18), linestyle="-.", linewidth=1.1)
        ax.plot(t, s.decayHist[valid], color=(1.0, 0.55, 0.22), linestyle="--", linewidth=1.0)
        ax.plot(t, s.targetHist[valid], color=(1.0, 0.48, 0.48), linestyle=":", linewidth=1.0)

        t_now = float(t[-1])
        if t_now <= visible_window_s:
            xmin, xmax = 0.0, visible_window_s
        else:
            xmin, xmax = t_now - visible_window_s, t_now
        ax.set_xlim(xmin, xmax)

        ymax = max(
            120.0,
            np.nanmax(s.pHist[valid]) * 1.1,
            np.nanmax(s.heatHist[valid]) * 1.1,
            s.targetPct * 1.1,
        )
        ax.set_ylim(0.0, min(ymax, 330.0))

        legend = ax.legend(
            ["Measured P", "True P", "Total heat", "Decay heat", "Target"],
            loc="upper left",
            fontsize=8,
            ncol=5,
        )
        legend.get_frame().set_facecolor((0.08, 0.09, 0.11))
        legend.get_frame().set_edgecolor((0.65, 0.68, 0.72))
        legend.get_frame().set_alpha(0.90)
        for text_item in legend.get_texts():
            text_item.set_color("white")

    @staticmethod
    def draw_mimic(ax, s):
        ax.clear()
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis("off")

        # Permanent two-zone layout:
        #   left  = plant schematic
        #   right = protection status and numerical readouts
        outer_x, outer_y, outer_w, outer_h = 0.30, 0.45, 9.40, 8.95
        divider_x = 6.35

        ax.add_patch(FancyBboxPatch(
            (outer_x, outer_y), outer_w, outer_h,
            boxstyle="round,pad=0.02,rounding_size=0.15",
            facecolor=(0.08, 0.10, 0.11),
            edgecolor=(0.35, 0.38, 0.42),
            linewidth=2,
        ))

        # Divide the mimic into a dedicated schematic area and a permanent
        # readout console so text can never overlap plant equipment.
        ax.plot(
            [divider_x, divider_x], [0.72, 9.10],
            color=(0.30, 0.34, 0.39), linewidth=1.5,
        )
        ax.text(
            3.30, 8.98, "PRIMARY SYSTEM MIMIC",
            color=(0.83, 0.88, 0.93), ha="center", va="center",
            fontsize=9.0, fontweight="bold",
        )
        ax.text(
            8.02, 8.98, "PLANT STATUS",
            color=(0.83, 0.88, 0.93), ha="center", va="center",
            fontsize=9.0, fontweight="bold",
        )

        # ---------------- Plant schematic: left zone ----------------
        vessel_x, vessel_y, vessel_w, vessel_h = 0.85, 3.05, 1.65, 3.65
        ax.add_patch(FancyBboxPatch(
            (vessel_x, vessel_y), vessel_w, vessel_h,
            boxstyle="round,pad=0.02,rounding_size=0.10",
            facecolor=(0.18, 0.20, 0.23),
            edgecolor=(0.72, 0.75, 0.79),
            linewidth=1.4,
        ))

        core_color = (0.14 + 0.20 * min(s.P, 1.5), 0.35, 0.76)
        core_x, core_y, core_w, core_h = 1.18, 3.48, 0.99, 2.72
        ax.add_patch(FancyBboxPatch(
            (core_x, core_y), core_w, core_h,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=core_color,
            edgecolor=(0.90, 0.95, 1.0),
            linewidth=1.1,
        ))
        ax.text(
            vessel_x + vessel_w / 2, 7.02, "REACTOR VESSEL",
            color=(0.92, 0.95, 0.98), ha="center",
            fontweight="bold", fontsize=8.8,
        )

        rod_top = 3.43 + 0.049 * s.rod_pos
        if s.scram:
            rod_top = 3.43
        for x in [1.32, 1.62, 1.92]:
            ax.add_patch(Rectangle(
                (x, rod_top), 0.10, 1.85,
                facecolor=(0.86, 0.86, 0.18),
                edgecolor=(0.98, 0.98, 0.55),
            ))
        ax.text(
            vessel_x + vessel_w / 2, 8.25, "Control Rods",
            color=(0.96, 0.96, 0.58), ha="center", fontsize=8.6,
        )

        # Steam generator.
        sg_x, sg_y, sg_w, sg_h = 3.05, 4.15, 1.30, 1.55
        ax.plot([2.17, sg_x], [4.95, 4.95], color=(0.3, 0.8, 1), linewidth=5)
        ax.add_patch(FancyBboxPatch(
            (sg_x, sg_y), sg_w, sg_h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=(0.20, 0.24, 0.27),
            edgecolor=(0.85, 0.88, 0.90),
            linewidth=1.2,
        ))
        ax.text(
            sg_x + sg_w / 2, sg_y + sg_h / 2, "STEAM\nGEN",
            color=(0.92, 0.95, 0.98), ha="center", va="center",
            fontweight="bold", fontsize=8.8,
        )

        # Turbine and secondary steam line.
        turb_x, turb_y, turb_w, turb_h = 4.78, 4.25, 1.08, 1.35
        ax.plot(
            [sg_x + sg_w, turb_x], [4.95, 4.95],
            color=(0.84, 0.84, 0.84), linewidth=5,
        )
        ax.add_patch(FancyBboxPatch(
            (turb_x, turb_y), turb_w, turb_h,
            boxstyle="round,pad=0.02,rounding_size=0.18",
            facecolor=(0.28, 0.28, 0.30),
            edgecolor=(0.91, 0.91, 0.93),
            linewidth=1.1,
        ))
        ax.text(
            turb_x + turb_w / 2, turb_y + turb_h / 2, "TURBINE",
            color=(0.96, 0.96, 0.96), ha="center", va="center",
            fontweight="bold", fontsize=8.2,
        )

        # Primary pump and cold-leg return.
        pump_x, pump_y, pump_w, pump_h = 3.05, 1.48, 1.32, 0.98
        ax.plot(
            [sg_x + sg_w / 2, sg_x + sg_w / 2],
            [sg_y, pump_y + pump_h],
            color=(0.3, 0.8, 1), linewidth=5,
        )
        ax.add_patch(FancyBboxPatch(
            (pump_x, pump_y), pump_w, pump_h,
            boxstyle="round,pad=0.02,rounding_size=0.18",
            facecolor=(0.14, 0.35, 0.15),
            edgecolor=(0.70, 1.0, 0.72),
            linewidth=1.1,
        ))
        ax.text(
            pump_x + pump_w / 2, pump_y + pump_h / 2, "PUMP",
            color=(0.86, 1.0, 0.86), ha="center", va="center",
            fontweight="bold", fontsize=8.8,
        )
        ax.plot(
            [pump_x, vessel_x + vessel_w / 2],
            [pump_y + pump_h / 2, pump_y + pump_h / 2],
            color=(0.3, 0.8, 1), linewidth=5,
        )
        ax.plot(
            [vessel_x + vessel_w / 2, vessel_x + vessel_w / 2],
            [pump_y + pump_h / 2, vessel_y],
            color=(0.3, 0.8, 1), linewidth=5,
        )

        # ---------------- Status console: right zone ----------------
        console_x, console_y, console_w, console_h = 6.58, 0.82, 2.86, 7.83
        ax.add_patch(FancyBboxPatch(
            (console_x, console_y), console_w, console_h,
            boxstyle="round,pad=0.02,rounding_size=0.10",
            facecolor=(0.075, 0.09, 0.105),
            edgecolor=(0.42, 0.47, 0.53),
            linewidth=1.2,
        ))

        # A fixed protection banner occupies its own row at the top of the
        # status console. It never shares space with the plant drawing.
        banner_x = console_x + 0.18
        banner_y = console_y + console_h - 0.78
        banner_w = console_w - 0.36
        banner_h = 0.48

        if s.scram:
            banner_text = "SCRAM ACTIVE"
            banner_face = (0.82, 0.10, 0.10)
            banner_edge = (1.0, 0.86, 0.86)
        elif s.time <= s.tripInhibit:
            banner_text = "STARTUP INHIBIT"
            banner_face = (0.80, 0.58, 0.08)
            banner_edge = (1.0, 0.95, 0.75)
        else:
            banner_text = "NORMAL OPERATION"
            banner_face = (0.10, 0.40, 0.18)
            banner_edge = (0.68, 1.0, 0.74)

        ax.add_patch(FancyBboxPatch(
            (banner_x, banner_y), banner_w, banner_h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=banner_face,
            edgecolor=banner_edge,
            linewidth=1.1,
        ))
        ax.text(
            banner_x + 0.5 * banner_w, banner_y + 0.5 * banner_h,
            banner_text, color=(1, 1, 1), ha="center", va="center",
            fontweight="bold", fontsize=8.6,
        )

        # Dedicated criticality-state indicator. It is placed directly below
        # the protection banner because it describes the instantaneous neutron
        # multiplication condition rather than an equipment alarm.
        criticality = classify_criticality(s.reactivity_pcm)
        if criticality == "SUBCRITICAL":
            crit_face = (0.10, 0.30, 0.55)
            crit_edge = (0.58, 0.78, 1.00)
        elif criticality == "SUPERCRITICAL":
            crit_face = (0.68, 0.32, 0.04)
            crit_edge = (1.00, 0.78, 0.38)
        else:
            crit_face = (0.08, 0.43, 0.20)
            crit_edge = (0.62, 1.00, 0.70)

        crit_x = banner_x
        crit_y = banner_y - 0.66
        crit_w = banner_w
        crit_h = 0.44
        ax.add_patch(FancyBboxPatch(
            (crit_x, crit_y), crit_w, crit_h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=crit_face,
            edgecolor=crit_edge,
            linewidth=1.1,
        ))
        ax.text(
            crit_x + 0.5 * crit_w, crit_y + 0.5 * crit_h,
            f"{criticality}   |   rho = {s.reactivity_pcm:+.1f} pcm",
            color=(1, 1, 1), ha="center", va="center",
            fontweight="bold", fontsize=7.8,
        )

        # Two-column readout: labels left, values right. Shorter rows keep all
        # values legible inside the dedicated console at smaller window sizes.
        rows = [
            ("Measured P", f"{s.measuredPct:6.1f} %"),
            ("True P", f"{s.powerPct:6.1f} %"),
            ("Total heat", f"{s.heatPct:6.1f} %"),
            ("Decay heat", f"{s.decayPct:6.1f} %"),
            ("Fuel / Clad", f"{s.fuelT:4.0f} / {s.cladT:4.0f} C"),
            ("Coolant", f"{s.coolT:6.1f} C"),
            ("Reactivity", f"{s.reactivity_pcm:6.1f} pcm"),
            ("Boron / Xe", f"{1e5*s.rho_boron:4.0f} / {1e5*s.rho_xe:4.0f}"),
            ("Period", fmt_period(s.period)),
        ]

        row_y = crit_y - 0.36
        row_step = 0.54
        for i, (label, value) in enumerate(rows):
            y = row_y - row_step * i
            if i % 2 == 0:
                ax.add_patch(Rectangle(
                    (console_x + 0.10, y - 0.22),
                    console_w - 0.20, 0.43,
                    facecolor=(0.10, 0.12, 0.14),
                    edgecolor="none",
                ))
            ax.text(
                console_x + 0.18, y, label,
                color=(0.72, 0.79, 0.85), ha="left", va="center",
                fontsize=7.5,
            )
            ax.text(
                console_x + console_w - 0.18, y, value,
                color=(0.92, 0.96, 0.99), ha="right", va="center",
                fontfamily="monospace", fontsize=7.5,
            )

        active_faults = s.active_fault_labels()
        if active_faults:
            fault_text = ", ".join(active_faults[:2])
            if len(active_faults) > 2:
                fault_text += " ..."
            fault_face = (0.55, 0.22, 0.05)
            fault_edge = (1.0, 0.82, 0.45)
            fault_label = "FAULTS: " + fault_text
        else:
            fault_face = (0.12, 0.20, 0.15)
            fault_edge = (0.45, 0.75, 0.52)
            fault_label = "NO ACTIVE FAULTS"

        ax.add_patch(FancyBboxPatch(
            (console_x + 0.18, console_y + 0.18),
            console_w - 0.36, 0.46,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=fault_face,
            edgecolor=fault_edge,
            linewidth=1.0,
        ))
        ax.text(
            console_x + 0.5 * console_w, console_y + 0.41,
            fault_label, color=(1, 1, 1), ha="center", va="center",
            fontweight="bold", fontsize=7.4,
        )

    @staticmethod
    def draw_meter(ax, val, vmin, vmax, label, col):
        ax.clear()
        ax.set_xlim(-1.1, 1.1)
        # Extra space below the dial keeps the value and label clear of the
        # needle pivot and of each other.
        ax.set_ylim(-0.40, 1.1)
        ax.axis("off")
        ax.set_facecolor((0.08, 0.09, 0.11))

        th = np.linspace(np.pi, 0, 120)
        ax.plot(np.cos(th), np.sin(th), color=(0.65, 0.68, 0.72), linewidth=3)

        for frac in np.linspace(0, 1, 11):
            ang = np.pi * (1 - frac)
            ax.plot([0.82 * np.cos(ang), np.cos(ang)],
                    [0.82 * np.sin(ang), np.sin(ang)],
                    color=(0.85, 0.88, 0.90), linewidth=1)

        frac = clamp((val - vmin) / (vmax - vmin), 0.0, 1.0)
        ang = np.pi * (1 - frac)
        ax.plot([0, 0.78 * np.cos(ang)],
                [0, 0.78 * np.sin(ang)],
                color=col, linewidth=4)
        ax.plot(0, 0, "o", markersize=8, markerfacecolor=(0.9, 0.9, 0.9), markeredgecolor=(0.2, 0.2, 0.2))

        ax.text(0, -0.13, f"{val:7.1f}", color=(0.96, 0.96, 0.82),
                ha="center", va="center", fontfamily="monospace",
                fontweight="bold", fontsize=12)
        ax.text(0, -0.32, label, color=(0.90, 0.92, 0.95),
                ha="center", va="center", fontweight="bold", fontsize=9)
        ax.text(-0.98, 0.05, f"{vmin:g}", color=(0.75, 0.78, 0.82), fontsize=8)
        ax.text(0.84, 0.05, f"{vmax:g}", color=(0.75, 0.78, 0.82), fontsize=8)



# ============================================================
# Scrollable pane helper
# ============================================================

class ScrollablePane:
    """A labelled scrollable canvas that holds a fixed-size content frame.

    The simulator still uses absolute placement inside each pane because that
    gives a stable control-panel layout, while the canvas provides horizontal
    and vertical scrolling when the user's screen is smaller than the design
    size.
    """

    def __init__(self, parent, title, content_width, content_height, bg, fg, font):
        self.content_width = content_width
        self.content_height = content_height

        self.outer = tk.LabelFrame(
            parent, text=title, bg=bg, fg=fg, font=font,
            bd=2, relief="groove",
        )
        self.outer.grid_rowconfigure(0, weight=1)
        self.outer.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self.outer, bg=bg, highlightthickness=0,
            xscrollincrement=20, yscrollincrement=20,
        )
        self.vbar = tk.Scrollbar(self.outer, orient="vertical", command=self.canvas.yview)
        self.hbar = tk.Scrollbar(self.outer, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")

        self.content = tk.Frame(self.canvas, bg=bg, width=content_width, height=content_height)
        self.content.pack_propagate(False)
        self.content.grid_propagate(False)
        self.window_id = self.canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.canvas.configure(scrollregion=(0, 0, content_width, content_height))

        self.content.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)

        # Linux scroll-wheel events.
        self.canvas.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda event: self.canvas.yview_scroll(3, "units"))

    def _update_scrollregion(self, _event=None):
        bbox = self.canvas.bbox("all")
        if bbox is not None:
            self.canvas.configure(scrollregion=bbox)

    def _bind_mousewheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

# ============================================================
# Main Tkinter application
# ============================================================

class ReactorTeachingSimulatorTk:
    def __init__(self, root):
        self.root = root
        self.root.title("Merged Reactor Teaching Simulator V6 - Scrollable Fault Injection Trainer")
        self.root.geometry("1320x820")
        self.root.minsize(900, 600)
        self.root.configure(bg="#0f1115")

        self.model = ReactorModel()
        self.syncing_controls = False
        self.active_scale = None
        self.display_dirty = False
        self.display_refresh_interval_s = 0.20
        self.last_display_refresh = time.perf_counter()
        self.diagnostics_window = None
        self.diagnostic_vars = {}
        self.syncing_diagnostics = False

        self.colors = {
            "bg": "#0f1115",
            "panel": "#1c2128",
            "panel2": "#16191f",
            "trim": "#2a313b",
            "text": "#e0ebf3",
            "green": "#2e8b57",
            "amber": "#b8860b",
            "red": "#b22222",
            "lcd": "#b6ffb6",
            "lcd_bg": "#081008",
            "readout_bg": "#061206",
            "readout_fg": "#9cff9c",
            "lamp_off": "#333333",
            "lamp_warn": "#d19a00",
            "lamp_trip": "#d62828",
        }

        self._build_styles()
        self._build_gui()
        self.refresh_all()
        self.schedule_loop()

    def _build_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Panel.TLabelframe", background=self.colors["panel"], foreground=self.colors["text"])
        style.configure("Panel.TLabelframe.Label", background=self.colors["panel"], foreground=self.colors["text"])
        style.configure("Dark.TLabel", background=self.colors["panel"], foreground=self.colors["text"])
        style.configure("LCD.TLabel", background=self.colors["lcd_bg"], foreground=self.colors["lcd"],
                        font=("Courier New", 11, "bold"))
        style.configure("Readout.TLabel", background=self.colors["panel2"], foreground=self.colors["text"])

    def _build_gui(self):
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)

        header = tk.Frame(self.root, bg=self.colors["bg"])
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=25, pady=(8, 6))
        header.grid_columnconfigure(0, weight=1)

        title_block = tk.Frame(header, bg=self.colors["bg"])
        title_block.grid(row=0, column=0, sticky="w")
        tk.Label(
            title_block,
            text="NUCLEAR REACTOR CONTROL PANEL - V7 ",
            bg=self.colors["bg"], fg="#eef5fb",
            font=("Segoe UI", 17, "bold"), anchor="w",
        ).pack(anchor="w")
        tk.Label(
            title_block, text=PROJECT_NAME, bg=self.colors["bg"], fg="#aebdca",
            font=("Segoe UI", 9), anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        # About 2 mm taller than the thermal banner's earlier 62 px rendering
        # at the standard 96-DPI desktop scale.
        self.utm_logo_image = load_logo_image(self.root, max_width=700, max_height=70)
        if self.utm_logo_image is not None:
            tk.Label(
                header, image=self.utm_logo_image, bg=self.colors["bg"], bd=0,
            ).grid(row=0, column=2, sticky="e", padx=(18, 0))
        else:
            tk.Label(
                header, text="UTM", bg="#7d1238", fg="white",
                font=("Segoe UI", 18, "bold"), padx=18, pady=6,
            ).grid(row=0, column=2, sticky="e", padx=(18, 0))

        ttk.Button(header, text="ABOUT", command=lambda: show_suite_about(self.root)).grid(
            row=0, column=1, sticky="e", padx=(18, 0),
        )

        pane_font = ("Segoe UI", 11, "bold")
        self.left_pane = ScrollablePane(
            self.root, " Operator Controls ", 400, 950,
            self.colors["panel"], self.colors["text"], pane_font,
        )
        self.right_pane = ScrollablePane(
            self.root, " Plant Display ", 1100, 980,
            self.colors["panel2"], self.colors["text"], pane_font,
        )

        self.left_pane.outer.grid(row=1, column=0, sticky="nsew", padx=(25, 10), pady=(0, 14))
        self.right_pane.outer.grid(row=1, column=1, sticky="nsew", padx=(10, 25), pady=(0, 14))

        # Existing panel builders use absolute placement; point them at the
        # scrollable content frames rather than the outer labelled frames.
        self.left = self.left_pane.content
        self.right = self.right_pane.content

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        s = self.model.s

        self.start_btn = tk.Button(self.left, text="START", bg="#2e6f3e", fg="white",
                                   font=("Segoe UI", 10, "bold"), command=self.start_cb)
        self.start_btn.place(x=20, y=20, width=95, height=36)

        self.pause_btn = tk.Button(self.left, text="PAUSE", bg="#8b6508", fg="white",
                                   font=("Segoe UI", 10, "bold"), command=self.pause_cb)
        self.pause_btn.place(x=140, y=20, width=95, height=36)

        self.scram_btn = tk.Button(self.left, text="SCRAM", bg="#b22222", fg="white",
                                   font=("Segoe UI", 10, "bold"), command=self.scram_cb)
        self.scram_btn.place(x=260, y=20, width=95, height=36)

        self.clock_var = tk.StringVar(value="TIME 0000.0 s")
        self.status_var = tk.StringVar(value="STATUS: READY")
        self.scaling_var = tk.StringVar(value="")

        tk.Label(self.left, textvariable=self.clock_var, bg=self.colors["lcd_bg"], fg=self.colors["lcd"],
                 font=("Courier New", 12, "bold")).place(x=20, y=70, width=160, height=30)
        tk.Label(self.left, textvariable=self.status_var, bg="#0c1018", fg="#f6f0cc",
                 font=("Courier New", 11, "bold")).place(x=200, y=70, width=160, height=30)

        tk.Label(
            self.left, textvariable=self.scaling_var, bg="#5b3900", fg="#fff0b3",
            font=("Segoe UI", 8, "bold"), anchor="center", wraplength=330,
        ).place(x=20, y=830, width=340, height=42)
        tk.Button(
            self.left, text="INSTRUCTOR: PEDAGOGICAL SETTINGS", bg="#604878", fg="white",
            font=("Segoe UI", 9, "bold"), command=self.open_pedagogical_settings,
        ).place(x=20, y=790, width=340, height=32)
        tk.Button(
            self.left, text="OPEN CORE PHYSICS DIAGNOSTICS", bg="#315b67", fg="white",
            font=("Segoe UI", 9, "bold"), command=self.open_physics_diagnostics,
        ).place(x=20, y=882, width=340, height=32)

        tk.Label(self.left, text="Control Mode", bg=self.colors["panel"], fg=self.colors["text"],
                 font=("Segoe UI", 10, "bold"), anchor="w").place(x=20, y=112, width=150, height=24)

        self.mode_var = tk.StringVar(value="manual")
        rb_frame = tk.Frame(self.left, bg="#151920", bd=1, relief="solid")
        rb_frame.place(x=20, y=140, width=340, height=85)

        tk.Radiobutton(rb_frame, text="Manual rod/reactivity", variable=self.mode_var, value="manual",
                       command=self.manual_mode_cb, bg="#151920", fg=self.colors["text"],
                       selectcolor="#151920", activebackground="#151920", activeforeground=self.colors["text"]
                       ).place(x=10, y=4)
        tk.Radiobutton(rb_frame, text="Auto power hold", variable=self.mode_var, value="auto",
                       command=self.auto_mode_cb, bg="#151920", fg=self.colors["text"],
                       selectcolor="#151920", activebackground="#151920", activeforeground=self.colors["text"]
                       ).place(x=10, y=30)
        tk.Radiobutton(rb_frame, text="Load-follow demo", variable=self.mode_var, value="load_follow",
                       command=self.load_follow_mode_cb, bg="#151920", fg=self.colors["text"],
                       selectcolor="#151920", activebackground="#151920", activeforeground=self.colors["text"]
                       ).place(x=10, y=56)

        y0 = 235
        step = 70
        self.rod_scale, self.rod_value = self._add_slider("Control Rod Position (%)", y0, 0, 100, s.rod_pos, self.rod_cb)
        self.flow_scale, self.flow_value = self._add_slider("Primary Coolant Flow (%)", y0 + step, 20, 120, s.coolantFlow, self.flow_cb)
        self.sink_scale, self.sink_value = self._add_slider("Heat Sink / Turbine Load (%)", y0 + 2 * step, 30, 120, s.heatSink, self.sink_cb)
        self.noise_scale, self.noise_value = self._add_slider("Instrumentation Noise (%)", y0 + 3 * step, 0, 8, s.noiseAmp, self.noise_cb)
        self.set_scale, self.set_value = self._add_slider("Auto Power Setpoint (%)", y0 + 4 * step, 30, 120, 100 * s.setpoint, self.setpoint_cb)
        self.boron_scale, self.boron_value = self._add_slider("Soluble Boron (ppm equiv.)", y0 + 5 * step, 0, 1000, s.boron_ppm, self.boron_cb)

        tk.Label(self.left, text="Manual Reactivity Trim", bg=self.colors["panel"], fg=self.colors["text"],
                 font=("Segoe UI", 10, "bold"), anchor="w").place(x=20, y=665, width=180, height=24)

        tk.Button(self.left, text="-5 pcm", bg="#404854", fg="white", command=self.minus_cb).place(x=20, y=695, width=90, height=34)
        tk.Button(self.left, text="+5 pcm", bg="#404854", fg="white", command=self.plus_cb).place(x=120, y=695, width=90, height=34)
        tk.Button(self.left, text="STEP 1 s", bg="#285b6b", fg="white", command=self.step_cb).place(x=220, y=695, width=70, height=34)
        tk.Button(self.left, text="RESET", bg="#285b6b", fg="white", command=self.reset_cb).place(x=300, y=695, width=60, height=34)

        self.lamp_power = self._make_lamp("HIGH PWR", 20, 738)
        self.lamp_temp = self._make_lamp("HI TEMP", 110, 738)
        self.lamp_flow = self._make_lamp("LOW FLOW", 200, 738)
        self.lamp_trip = self._make_lamp("TRIP", 290, 738)

    def _build_right_panel(self):
        self.display = PlantDisplay(self.right)
        self.display.widget.place(x=10, y=10, width=1070, height=710)

        self._build_fault_panel()

        self.readout = tk.Listbox(
            self.right,
            bg=self.colors["readout_bg"],
            fg=self.colors["readout_fg"],
            font=("Courier New", 9),
            selectbackground="#103010",
            selectforeground=self.colors["readout_fg"],
        )
        self.readout.place(x=20, y=865, width=1045, height=90)

    def _build_fault_panel(self):
        self.fault_frame = tk.LabelFrame(
            self.right, text=" Fault Injection Panel ",
            bg=self.colors["panel"], fg=self.colors["text"],
            font=("Segoe UI", 10, "bold"), bd=2, relief="groove",
        )
        self.fault_frame.place(x=20, y=735, width=1045, height=118)

        self.fault_vars = {}
        faults = [
            ("Stuck rod", "fault_stuck_rod"),
            ("Partial SCRAM", "fault_partial_scram"),
            ("Pump trip", "fault_pump_trip"),
            ("Heat-sink loss", "fault_heat_sink_loss"),
            ("Detector bias", "fault_detector_bias"),
            ("Frozen detector", "fault_frozen_detector"),
            ("Boron dilution", "fault_boron_dilution"),
            ("Auto failure", "fault_auto_failure"),
            ("Low-flow trip fail", "fault_low_flow_trip_fail"),
        ]
        for i, (label, key) in enumerate(faults):
            var = tk.IntVar(value=0)
            self.fault_vars[key] = var
            row = i % 3
            col = i // 3
            cb = tk.Checkbutton(
                self.fault_frame, text=label, variable=var,
                command=lambda k=key: self.fault_toggle_cb(k),
                bg=self.colors["panel"], fg=self.colors["text"],
                selectcolor="#151920", activebackground=self.colors["panel"],
                activeforeground=self.colors["text"], anchor="w",
                font=("Segoe UI", 9, "bold"),
            )
            cb.place(x=12 + 165 * col, y=8 + 29 * row, width=155, height=24)

        self.fault_severity_label = tk.Label(
            self.fault_frame, text="Fault severity: 60%",
            bg=self.colors["panel"], fg="#ffd98a",
            font=("Segoe UI", 9, "bold"), anchor="w",
        )
        self.fault_severity_label.place(x=540, y=8, width=170, height=22)
        self.fault_severity_scale = tk.Scale(
            self.fault_frame, from_=0, to=100, orient="horizontal", resolution=1,
            showvalue=0, bg=self.colors["panel"], fg=self.colors["text"],
            troughcolor="#39414a", highlightthickness=0,
            command=self.fault_severity_cb,
        )
        self.fault_severity_scale.set(self.model.s.fault_severity)
        self.fault_severity_scale.place(x=540, y=32, width=245, height=45)
        self.fault_severity_scale.bind(
            "<ButtonPress-1>",
            lambda _event: self._begin_scale_drag(self.fault_severity_scale),
        )
        self.fault_severity_scale.bind(
            "<ButtonRelease-1>",
            lambda _event: self._end_scale_drag(self.fault_severity_scale),
        )

        tk.Button(
            self.fault_frame, text="EXPORT CSV", bg="#285b6b", fg="white",
            activebackground="#285b6b", activeforeground="white",
            font=("Segoe UI", 10, "bold"), command=self.export_csv_cb,
        ).place(x=800, y=10, width=210, height=32)

        help_text = (
            "Export run history for Excel, Octave, Python, or lab reports. "
            "Use faults for diagnosis drills."
        )
        tk.Label(
            self.fault_frame, text=help_text, bg="#111315", fg="#d6d9d0",
            justify="left", wraplength=210, font=("Segoe UI", 8),
            padx=6, pady=4,
        ).place(x=800, y=48, width=210, height=48)

    def _add_slider(self, label, y, minv, maxv, initv, callback):
        tk.Label(self.left, text=label, bg=self.colors["panel"], fg=self.colors["text"],
                 font=("Segoe UI", 9, "bold"), anchor="w").place(x=20, y=y, width=235, height=18)

        val_label = tk.Label(self.left, text=f"{initv:5.1f}", bg="#0c1018", fg="#f5f5d0",
                             font=("Courier New", 9, "bold"))
        val_label.place(x=285, y=y + 20, width=75, height=24)

        resolution = 1 if maxv >= 1000 else 0.1
        scale = tk.Scale(
            self.left, from_=minv, to=maxv, orient="horizontal", resolution=resolution,
            showvalue=0, bg=self.colors["panel"], fg=self.colors["text"],
            highlightthickness=0, troughcolor="#39414a", command=lambda v: callback(v, val_label),
        )
        scale.set(initv)
        scale.place(x=20, y=y + 16, width=250, height=42)
        scale.bind("<ButtonPress-1>", lambda _event, widget=scale: self._begin_scale_drag(widget))
        scale.bind("<ButtonRelease-1>", lambda _event, widget=scale: self._end_scale_drag(widget))
        return scale, val_label

    def _begin_scale_drag(self, scale):
        self.active_scale = scale

    def _end_scale_drag(self, scale):
        if self.active_scale is scale:
            self.active_scale = None
        self.sync_controls_from_model()
        self.request_display_refresh()

    def request_display_refresh(self):
        """Queue an expensive plant-display redraw without blocking UI input."""
        self.display_dirty = True

    def _make_lamp(self, text, x, y):
        lbl = tk.Label(self.left, text=text, bg=self.colors["lamp_off"], fg="white",
                       font=("Segoe UI", 10, "bold"), relief="raised", bd=2)
        lbl.place(x=x, y=y, width=75, height=28)
        return lbl

    # ----------------------------
    # Callbacks
    # ----------------------------
    def start_cb(self):
        self.model.s.running = True
        self.model.s.add_log("Simulation started.")
        self.refresh_all()

    def pause_cb(self):
        self.model.s.running = False
        self.model.s.add_log("Simulation paused.")
        self.refresh_all()

    def scram_cb(self):
        self.model.s.scram = True
        self.model.s.running = True
        self.model.s.add_log("Manual SCRAM pushbutton pressed. Decay heat remains; maintain cooling.")
        self.sync_controls_from_model()
        self.refresh_all()

    def reset_cb(self):
        self.model.reset()
        self.sync_controls_from_model()
        self.refresh_all()

    def open_pedagogical_settings(self):
        if self.model.s.running:
            messagebox.showwarning(
                "Pause required",
                "Pause the simulator before changing pedagogical model settings.",
            )
            return

        current = self.model.s.pedagogical_settings
        dialog = tk.Toplevel(self.root)
        dialog.title("Instructor - Pedagogical Settings")
        dialog.geometry("680x500")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="These controls alter the model equations, not wall-clock simulation speed.",
            wraplength=620,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        kinetics_labels = {kinetics_preset_label(name): name for name in KINETICS_PRESETS}
        xenon_labels = {xenon_preset_label(name): name for name in XENON_PRESETS}
        kinetics_var = tk.StringVar(value=kinetics_preset_label(current.kinetics_preset))
        xenon_var = tk.StringVar(value=xenon_preset_label(current.xenon_preset))
        load_var = tk.DoubleVar(value=current.load_follow_period_s)
        profile_var = tk.StringVar(value=current.physics_profile)
        initial_var = tk.StringVar(value=current.initial_condition)
        cycle_var = tk.StringVar(value=current.cycle_preset)

        ttk.Label(frame, text="Kinetics preset").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Combobox(
            frame, textvariable=kinetics_var, values=list(kinetics_labels), state="readonly", width=55,
        ).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="Xenon timescale").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(
            frame, textvariable=xenon_var, values=list(xenon_labels), state="readonly", width=55,
        ).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="Load-follow period (s)").grid(row=3, column=0, sticky="w", pady=6)
        tk.Scale(
            frame, variable=load_var, from_=60, to=600, resolution=10, orient="horizontal", length=245,
        ).grid(row=3, column=1, sticky="ew", pady=6)

        ttk.Separator(frame, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(frame, text="Core-physics detail").grid(row=5, column=0, sticky="w", pady=6)
        profile_box = ttk.Combobox(
            frame, textvariable=profile_var, values=PHYSICS_PROFILES, state="readonly", width=55,
        )
        profile_box.grid(row=5, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="Initial condition").grid(row=6, column=0, sticky="w", pady=6)
        initial_box = ttk.Combobox(
            frame, textvariable=initial_var, values=INITIAL_CONDITIONS, state="readonly", width=55,
        )
        initial_box.grid(row=6, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="Exposure state").grid(row=7, column=0, sticky="w", pady=6)
        cycle_box = ttk.Combobox(
            frame, textvariable=cycle_var, values=list(CYCLE_PRESETS), state="readonly", width=55,
        )
        cycle_box.grid(row=7, column=1, sticky="ew", pady=6)

        def update_advanced_controls(_event=None):
            advanced = profile_var.get() == "Advanced core physics"
            if not advanced:
                initial_var.set("Full-power equilibrium")
                cycle_var.set("Steady classroom")
            initial_box.configure(state="readonly" if advanced else "disabled")
            cycle_box.configure(state="readonly" if advanced else "disabled")

        profile_box.bind("<<ComboboxSelected>>", update_advanced_controls)
        update_advanced_controls()

        note = ttk.Label(
            frame,
            text="Applying settings resets the run and initializes delayed-neutron and Xe/I state consistently.",
            wraplength=620,
        )
        note.grid(row=8, column=0, columnspan=2, sticky="w", pady=(12, 15))

        def apply_settings():
            settings = PedagogicalSettings(
                kinetics_preset=kinetics_labels[kinetics_var.get()],
                xenon_preset=xenon_labels[xenon_var.get()],
                load_follow_period_s=float(load_var.get()),
                physics_profile=profile_var.get(),
                initial_condition=initial_var.get(),
                cycle_preset=cycle_var.get(),
            )
            self.model.reset(settings)
            self.model.s.add_log("Pedagogical settings applied; simulation reset.")
            dialog.destroy()
            self.sync_controls_from_model()
            self.refresh_all()

        buttons = ttk.Frame(frame)
        buttons.grid(row=9, column=0, columnspan=2, sticky="e")
        ttk.Button(
            buttons, text="Restore validated defaults",
            command=lambda: (
                kinetics_var.set(kinetics_preset_label("Classroom")),
                xenon_var.set(xenon_preset_label("Laboratory demo")),
                load_var.set(220),
                profile_var.set("Classroom model"),
                initial_var.set("Full-power equilibrium"),
                cycle_var.set("Steady classroom"),
                update_advanced_controls(),
            ),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Apply and reset", command=apply_settings).pack(side="left")

    def open_physics_diagnostics(self):
        if self.diagnostics_window is not None and self.diagnostics_window.winfo_exists():
            self.diagnostics_window.lift()
            self.diagnostics_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title("Core Physics Diagnostics")
        window.geometry("780x620")
        window.minsize(700, 560)
        window.transient(self.root)
        self.diagnostics_window = window
        self.diagnostic_vars = {
            key: tk.StringVar(value="")
            for key in ("profile", "reactivity", "poisons", "startup", "cycle", "source")
        }

        def close_window():
            self.diagnostics_window = None
            self.diagnostic_vars = {}
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_window)
        ttk.Label(
            window, textvariable=self.diagnostic_vars["profile"],
            font=("Segoe UI", 11, "bold"), padding=(12, 10),
        ).pack(fill="x")
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for title, key in (
            ("Reactivity balance", "reactivity"),
            ("Poisons and exposure", "poisons"),
            ("Startup instrumentation", "startup"),
        ):
            tab = ttk.Frame(notebook, padding=18)
            notebook.add(tab, text=title)
            ttk.Label(
                tab, textvariable=self.diagnostic_vars[key],
                font=("Courier New", 10), justify="left",
            ).pack(anchor="nw", fill="x")
            if key == "reactivity":
                self.rod_worth_figure = Figure(figsize=(6.8, 2.0), dpi=90, facecolor="#f3f3f3")
                self.rod_worth_axis = self.rod_worth_figure.add_subplot(111)
                self.rod_diff_axis = self.rod_worth_axis.twinx()
                self.rod_worth_canvas = FigureCanvasTkAgg(self.rod_worth_figure, master=tab)
                self.rod_worth_canvas.get_tk_widget().pack(fill="both", expand=True, pady=(10, 0))
            if key == "poisons":
                ttk.Separator(tab).pack(fill="x", pady=14)
                ttk.Label(
                    tab, textvariable=self.diagnostic_vars["cycle"],
                    font=("Courier New", 10), justify="left",
                ).pack(anchor="nw", fill="x")
            if key == "startup":
                ttk.Separator(tab).pack(fill="x", pady=14)
                ttk.Label(tab, text="External source strength (log10 model units)").pack(anchor="w")
                source_scale = tk.Scale(
                    tab, from_=-8, to=-3, resolution=0.1, orient="horizontal", length=500,
                )
                source_scale.set(math.log10(max(self.model.s.source_strength, 1.0e-8)))
                source_scale.configure(command=self.source_strength_cb)
                source_scale.pack(anchor="w")
                self.source_strength_scale = source_scale
                ttk.Label(tab, textvariable=self.diagnostic_vars["source"]).pack(anchor="w")

        self.refresh_diagnostics()

    def source_strength_cb(self, value):
        if self.syncing_diagnostics or not self.model.s.pedagogical_settings.advanced_physics:
            return
        self.model.s.source_strength = 10.0 ** float(value)
        self.model.s.add_log(f"External source set to {self.model.s.source_strength:.2e} model units.")
        self.refresh_all()

    def refresh_diagnostics(self):
        if self.diagnostics_window is None or not self.diagnostics_window.winfo_exists():
            return
        s = self.model.s
        advanced = s.pedagogical_settings.advanced_physics
        self.diagnostic_vars["profile"].set(
            f"Active profile: {s.pedagogical_settings.physics_profile} | "
            f"Initial condition: {s.pedagogical_settings.initial_condition}"
        )
        components = [
            ("Rod bank", s.rho_rods), ("Manual trim", s.rho_manual),
            ("Fuel Doppler", s.rho_fuel), ("Moderator temperature", s.rho_moderator_temp),
            ("Moderator density", s.rho_density), ("Void", s.rho_void),
            ("Boron", s.rho_boron), ("Xe-135", s.rho_xe),
            ("Sm-149", s.rho_sm), ("Cycle depletion", s.rho_depletion if advanced else 0.0),
        ]
        balance = "\n".join(f"{name:<24} {1.0e5 * value:+9.1f} pcm" for name, value in components)
        balance += (
            f"\n{'-' * 38}\n{'TOTAL':<24} {s.reactivity_pcm:+9.1f} pcm"
            f"\n\nRod position             {s.rod_pos:9.2f} % withdrawn"
            f"\nDifferential rod worth   {differential_rod_worth_pcm_per_pct(s.rod_pos, advanced):9.2f} pcm/%"
        )
        self.diagnostic_vars["reactivity"].set(balance)
        self.diagnostic_vars["poisons"].set(
            f"I-135 index              {s.I:12.5f}\n"
            f"Xe-135 index             {s.Xe:12.5f}   ({1.0e5*s.rho_xe:+.1f} pcm)\n"
            f"Pm-149 index             {s.Pm:12.5f}\n"
            f"Sm-149 index             {s.Sm:12.5f}   ({1.0e5*s.rho_sm:+.1f} pcm)\n\n"
            f"Moderator density        {s.moderator_density:12.5f} relative\n"
            f"Void fraction            {100.0*s.void_fraction:12.3f} %"
        )
        recommended_boron = 1000.0 * max(
            0.0, 1.0 - s.exposure_efpd / s.cycle_length_efpd,
        ) if s.cycle_length_efpd else 0.0
        self.diagnostic_vars["cycle"].set(
            f"Exposure preset           {s.pedagogical_settings.cycle_preset}\n"
            f"Teaching exposure         {s.exposure_efpd:9.2f} / {s.cycle_length_efpd:.0f} EFPD\n"
            f"Cycle excess reactivity   {1.0e5*s.rho_depletion:+9.1f} pcm\n"
            f"Illustrative boron target {recommended_boron:9.0f} ppm\n"
            f"Actual boron              {s.boron_ppm:9.0f} ppm"
        )
        multiplication = "infinite/critical" if math.isinf(s.subcritical_multiplication) else f"{s.subcritical_multiplication:.2f}"
        self.diagnostic_vars["startup"].set(
            f"Active detector range     {s.instrument_range}\n"
            f"True neutron power        {s.P:12.5e} fraction\n"
            f"Log neutron level         {s.log_neutron_level:12.3f} decades\n"
            f"External source           {s.source_strength:12.5e} model units\n"
            f"Subcritical multiplication {multiplication}\n\n"
            "Range transitions: source < 1e-4, intermediate < 10%, power >= 10%."
        )
        self.diagnostic_vars["source"].set(
            "Available only in Advanced core physics. "
            f"Current source = {s.source_strength:.2e}."
        )
        if hasattr(self, "source_strength_scale"):
            self.syncing_diagnostics = True
            try:
                self.source_strength_scale.configure(state="normal" if advanced else "disabled")
                self.source_strength_scale.set(math.log10(max(s.source_strength, 1.0e-8)))
            finally:
                self.syncing_diagnostics = False
        if hasattr(self, "rod_worth_axis"):
            positions = np.linspace(0.0, 100.0, 101)
            integral = np.array([1.0e5 * rod_reactivity(position, advanced) for position in positions])
            differential = np.array([
                differential_rod_worth_pcm_per_pct(position, advanced) for position in positions
            ])
            axis = self.rod_worth_axis
            diff_axis = self.rod_diff_axis
            axis.clear()
            diff_axis.clear()
            integral_line, = axis.plot(positions, integral, color="#315b67", label="Integral worth")
            differential_line, = diff_axis.plot(
                positions, differential, color="#a65f00", linestyle="--", label="Differential worth",
            )
            axis.axvline(s.rod_pos, color="#8b1e1e", linewidth=1.2, label="Current position")
            axis.axhline(0.0, color="#777777", linewidth=0.7)
            axis.set_xlim(0.0, 100.0)
            axis.set_xlabel("Rod bank withdrawn (%)", fontsize=8)
            axis.set_ylabel("Integral worth (pcm)", fontsize=8, color="#315b67")
            diff_axis.set_ylabel("Differential worth (pcm/%)", fontsize=8, color="#a65f00")
            axis.tick_params(labelsize=7)
            diff_axis.tick_params(labelsize=7)
            axis.grid(True, alpha=0.25)
            axis.legend(
                [integral_line, differential_line],
                [integral_line.get_label(), differential_line.get_label()],
                loc="upper left", fontsize=7, ncol=2,
            )
            self.rod_worth_figure.tight_layout(pad=0.8)
            self.rod_worth_canvas.draw_idle()

    def manual_mode_cb(self):
        self.model.s.mode = "manual"
        self.model.s.add_log("Mode changed to MANUAL.")
        self.refresh_all()

    def auto_mode_cb(self):
        self.model.s.mode = "auto"
        self.model.s.add_log("Mode changed to AUTO power hold. Rods move gradually.")
        self.refresh_all()

    def load_follow_mode_cb(self):
        self.model.s.mode = "load_follow"
        self.model.s.add_log("Mode changed to LOAD-FOLLOW demo. Target power varies with time.")
        self.refresh_all()

    def rod_cb(self, val, label):
        if self.syncing_controls:
            label.config(text=f"{float(val):5.1f} %")
            return
        s = self.model.s
        if s.fault_stuck_rod and s.stuck_rod_pos is not None:
            label.config(text=f"{s.stuck_rod_pos:5.1f} %")
            self.rod_scale.set(s.stuck_rod_pos)
            return
        s.rod_pos = float(val)
        label.config(text=f"{s.rod_pos:5.1f} %")
        if s.scram and s.rod_pos > 5.0:
            s.scram = False
            s.add_log("SCRAM cleared by rod withdrawal. Use RESET for a clean restart if desired.")
        self.request_display_refresh()

    def flow_cb(self, val, label):
        if self.syncing_controls:
            label.config(text=f"{float(val):5.1f} %")
            return
        if self.model.s.fault_pump_trip:
            label.config(text=f"{self.model.s.coolantFlow:5.1f} %")
            return
        self.model.s.coolantFlow = float(val)
        label.config(text=f"{self.model.s.coolantFlow:5.1f} %")
        self.request_display_refresh()

    def sink_cb(self, val, label):
        if self.syncing_controls:
            label.config(text=f"{float(val):5.1f} %")
            return
        if self.model.s.fault_heat_sink_loss:
            label.config(text=f"{self.model.s.heatSink:5.1f} %")
            return
        self.model.s.heatSink = float(val)
        label.config(text=f"{self.model.s.heatSink:5.1f} %")
        self.request_display_refresh()

    def noise_cb(self, val, label):
        if self.syncing_controls:
            label.config(text=f"{float(val):4.1f} %")
            return
        self.model.s.noiseAmp = float(val)
        label.config(text=f"{self.model.s.noiseAmp:4.1f} %")
        self.request_display_refresh()

    def setpoint_cb(self, val, label):
        if self.syncing_controls:
            label.config(text=f"{float(val):5.1f} %")
            return
        self.model.s.setpoint = float(val) / 100.0
        label.config(text=f"{100*self.model.s.setpoint:5.1f} %")
        self.request_display_refresh()

    def boron_cb(self, val, label):
        if self.syncing_controls:
            label.config(text=f"{float(val):5.0f}")
            return
        self.model.s.boron_ppm = float(val)
        label.config(text=f"{self.model.s.boron_ppm:5.0f}")
        self.request_display_refresh()

    def minus_cb(self):
        self.model.s.rho_manual = clamp(self.model.s.rho_manual - 5e-5, -0.010, 0.010)
        self.model.s.add_log("Manual reactivity decreased by 5 pcm.")
        self.refresh_all()

    def plus_cb(self):
        self.model.s.rho_manual = clamp(self.model.s.rho_manual + 5e-5, -0.010, 0.010)
        self.model.s.add_log("Manual reactivity increased by 5 pcm.")
        self.refresh_all()

    def step_cb(self):
        self.model.advance(1.0)
        self.model.s.add_log("Single 1 s step executed.")
        self.sync_controls_from_model()
        self.refresh_all()

    def export_csv_cb(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"reactor_sim_run_{timestamp}.csv"
        filepath = filedialog.asksaveasfilename(
            title="Export simulation history to CSV",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not filepath:
            return

        try:
            nrows = self.model.export_csv(filepath)
        except Exception as exc:
            messagebox.showerror("CSV export failed", f"Could not export CSV file:\n{exc}")
            return

        self.model.s.add_log(f"CSV export saved: {nrows} rows.")
        messagebox.showinfo("CSV export complete", f"Saved {nrows} rows to:\n{filepath}")
        self.refresh_all()

    def fault_toggle_cb(self, key):
        if self.syncing_controls:
            return
        s = self.model.s
        active = bool(self.fault_vars[key].get())
        setattr(s, key, active)

        if key == "fault_stuck_rod":
            if active:
                s.stuck_rod_pos = s.rod_pos
                s.add_log(f"FAULT ON: stuck control rod at {s.stuck_rod_pos:.1f}% withdrawn.")
            else:
                s.stuck_rod_pos = None
                s.add_log("FAULT OFF: stuck control rod cleared.")
        elif key == "fault_partial_scram":
            s.add_log("FAULT ON: partial SCRAM insertion enabled." if active else "FAULT OFF: partial SCRAM cleared.")
        elif key == "fault_pump_trip":
            if active:
                s.pump_trip_start_time = s.time
                s.pump_trip_initial_flow = s.coolantFlow
                s.add_log("FAULT ON: primary pump trip/coastdown started.")
            else:
                s.pump_trip_start_time = None
                s.add_log("FAULT OFF: pump trip cleared; flow slider available.")
        elif key == "fault_heat_sink_loss":
            if active:
                s.heat_sink_loss_start_time = s.time
                s.heat_sink_initial = s.heatSink
                s.add_log("FAULT ON: heat-sink loss started.")
            else:
                s.heat_sink_loss_start_time = None
                s.add_log("FAULT OFF: heat-sink loss cleared; load slider available.")
        elif key == "fault_detector_bias":
            s.add_log("FAULT ON: power detector reads high." if active else "FAULT OFF: detector bias cleared.")
        elif key == "fault_frozen_detector":
            if active:
                s.frozen_measured_power = s.measuredPower
                s.add_log(f"FAULT ON: power detector frozen at {100*s.frozen_measured_power:.1f}%.")
            else:
                s.frozen_measured_power = None
                s.add_log("FAULT OFF: frozen detector cleared.")
        elif key == "fault_boron_dilution":
            s.add_log("FAULT ON: boron dilution started." if active else "FAULT OFF: boron dilution stopped.")
        elif key == "fault_auto_failure":
            s.add_log("FAULT ON: auto controller output failed." if active else "FAULT OFF: auto controller restored.")
        elif key == "fault_low_flow_trip_fail":
            s.low_flow_trip_fail_announced = False
            s.add_log("FAULT ON: low-flow trip channel disabled." if active else "FAULT OFF: low-flow trip channel restored.")

        self.sync_controls_from_model()
        self.refresh_all()

    def fault_severity_cb(self, val):
        if self.syncing_controls:
            return
        self.model.s.fault_severity = float(val)
        self.fault_severity_label.config(text=f"Fault severity: {float(val):.0f}%")
        self.request_display_refresh()

    def sync_controls_from_model(self):
        s = self.model.s
        self.syncing_controls = True
        try:
            if self.active_scale is not self.rod_scale:
                self.rod_scale.set(s.rod_pos)
            if self.active_scale is not self.flow_scale:
                self.flow_scale.set(s.coolantFlow)
            if self.active_scale is not self.sink_scale:
                self.sink_scale.set(s.heatSink)
            if self.active_scale is not self.noise_scale:
                self.noise_scale.set(s.noiseAmp)
            if self.active_scale is not self.set_scale:
                self.set_scale.set(100 * s.setpoint)
            if self.active_scale is not self.boron_scale:
                self.boron_scale.set(s.boron_ppm)
            self.mode_var.set(s.mode)
            if hasattr(self, "fault_vars"):
                for key, var in self.fault_vars.items():
                    var.set(1 if getattr(s, key) else 0)
                if self.active_scale is not self.fault_severity_scale:
                    self.fault_severity_scale.set(s.fault_severity)
                self.fault_severity_label.config(text=f"Fault severity: {s.fault_severity:.0f}%")
        finally:
            self.syncing_controls = False

    # ----------------------------
    # Refresh and loop
    # ----------------------------
    def refresh_all(self):
        s = self.model.s
        s.update_reactivity_terms()
        s.update_derived()

        self.clock_var.set("TIME " + s.clockString)
        settings = s.pedagogical_settings
        if settings.is_baseline:
            self.scaling_var.set("PEDAGOGICAL SCALING: VALIDATED CLASSROOM DEFAULTS")
        else:
            self.scaling_var.set(
                f"MODEL SETTINGS ACTIVE - {settings.physics_profile}; Lambda={s.Lambda:.3f} s; "
                f"Xe={settings.xenon_preset}; {settings.cycle_preset}"
            )
        if s.scram:
            self.status_var.set("STATUS: SCRAM")
        elif s.running:
            if s.active_fault_labels():
                self.status_var.set(f"FAULTS: {len(s.active_fault_labels())}")
            else:
                self.status_var.set("STATUS: RUNNING")
        else:
            if s.active_fault_labels():
                self.status_var.set(f"FAULTS: {len(s.active_fault_labels())}")
            else:
                self.status_var.set("STATUS: PAUSED")

        self.lamp_power.config(bg=self.colors["lamp_warn"] if s.P > 0.95 * s.tripHighPower else self.colors["lamp_off"])
        self.lamp_temp.config(bg=self.colors["lamp_warn"] if s.fuelT > 0.95 * s.tripHighFuelTemp or s.cladT > 0.95 * s.tripHighCladTemp else self.colors["lamp_off"])
        self.lamp_flow.config(bg=self.colors["lamp_warn"] if s.coolantFlow < 1.05 * s.tripLowFlow else self.colors["lamp_off"])
        self.lamp_trip.config(bg=self.colors["lamp_trip"] if s.scram else self.colors["lamp_off"])

        self.display.refresh(s)

        self.readout.delete(0, tk.END)
        for line in self.model.compose_readout():
            self.readout.insert(tk.END, line)
        if self.readout.size() > 0:
            self.readout.see(tk.END)
        self.refresh_diagnostics()
        self.display_dirty = False
        self.last_display_refresh = time.perf_counter()

    def schedule_loop(self):
        # Keep the transient and throttled display moving throughout an
        # operator drag.  Model-to-widget synchronization is held until the
        # mouse releases the active scale so it cannot fight the operator.
        if self.model.s.running:
            self.model.advance(0.20)
            self.display_dirty = True

        now = time.perf_counter()
        if (
            self.display_dirty
            and now - self.last_display_refresh >= self.display_refresh_interval_s
        ):
            if self.active_scale is None:
                self.sync_controls_from_model()
            self.refresh_all()
        self.root.after(40, self.schedule_loop)


# ============================================================
# Entry point
# ============================================================

def main():
    root = tk.Tk()
    root.withdraw()
    ReactorTeachingSimulatorTk(root)
    show_startup_splash(
        root,
        module_name="Reactor Physics and Kinetics Simulator",
        duration_ms=3000,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
