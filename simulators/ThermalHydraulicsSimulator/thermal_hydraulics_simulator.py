#!/usr/bin/env python3
"""
LWR Thermal-Hydraulics / LOCA Teaching Simulator - Python version
-----------------------------------------------------------------
Author: maxisnote20
Contact: maxisnote20@gmail.com
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
    python simulators/ThermalHydraulicsSimulator/main.py
"""

from __future__ import annotations

import csv
import math
import time
import tkinter as tk
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Deque, Dict, List, Optional, TextIO, Tuple

import numpy as np

from steam_properties import SteamTables
from thermal_hydraulics_engine import PWRControlInputs, ThermalHydraulicsEngine
from hot_channel import HotChannelModel, HotChannelResult
from bwr_hot_channel import BWRHotChannelModel
from bwr_plant_model import BWRControlInputs
from plant_models import create_plant_model

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

ABOUT_MESSAGE = """Open Nuclear Engineering Teaching Suite

Interactive desktop simulators for teaching reactor physics, kinetics,
thermal-hydraulics, LOCA behavior, and core loading concepts.

Author and maintainer: maxisnote20
Email: maxisnote20@gmail.com
Repository: https://github.com/open-nuclear-suite/OpenNuclearSuite

This software is intended for education and demonstration. It must not be
used for reactor design, licensing, safety analysis, or plant operation."""


def show_suite_about(parent: tk.Misc) -> None:
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
    ttk.Button(actions, text="EMAIL AUTHOR", command=lambda: webbrowser.open("mailto:maxisnote20@gmail.com")).pack(side=tk.LEFT)
    ttk.Button(actions, text="CLOSE", command=window.destroy).pack(side=tk.RIGHT)
    window.focus_set()


def find_logo_path(filename: str) -> Optional[Path]:
    """Return the first available branding image with the requested filename."""
    module_dir = Path(__file__).resolve().parent
    project_root = module_dir.parents[1]
    candidates = [
        module_dir / filename,
        module_dir.parent / filename,
        project_root / filename,
        project_root / "assets" / filename,
        Path.cwd() / filename,
        Path.cwd() / "assets" / filename,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_logo_image(
    master: tk.Misc,
    max_width: int,
    max_height: Optional[int] = None,
    filename: str = "",
) -> Optional[tk.PhotoImage]:
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

def show_startup_splash(
    root: tk.Tk, module_name: str, duration_ms: int = 3000
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
class PWRConstants:
    """Declared constants for the representative reduced-order PWR."""
    # Nominal LWR / PWR-like teaching reference values.
    Pnom_MW: float = 3415.0
    Tsink: float = 273.0
    TrefFuel: float = 850.0
    TrefClad: float = 335.0
    TrefCool: float = 300.75
    Pref: float = 15.5
    Mref: float = 1.0
    plant_type: str = "PWR"
    plant_label: str = "Representative PWR"
    pressure_reference_temperature_C: float = 344.7915516

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
    coolant_energy_reference_C: float = 20.0
    # Effective h_fg/cp expressed as an equivalent liquid-temperature rise.
    # This keeps the classroom model conservative without pretending to be a
    # steam-property package (roughly 2.2 MJ/kg / 4.2 kJ/kg-K).
    latent_heat_equiv_C: float = 525.0
    eccs_temp_C: float = 35.0
    pressurizer_tau: float = 18.0

    # Reactivity coefficients. Units are delta-k/k per degC.
    alpha_f: float = -3.5e-5
    alpha_m: float = -2.0e-5
    boron_worth: float = -0.8e-5
    boron_ref: float = 1000.0
    rod_worth_pcm: float = 3000.0

    # Simplified inventory and pressure model coefficients.
    break_coeff: float = 0.014
    porv_coeff: float = 0.007
    eccs_coeff: float = 0.010
    # Generic safety-injection curves. Flow units are nominal-primary-inventory
    # fractions per second; values are teaching surrogates, not plant data.
    pwr_hpsi_runout_fraction_s: float = 0.0040
    pwr_hpsi_shutoff_pressure_mpa: float = 16.0
    pwr_lpsi_runout_fraction_s: float = 0.0070
    pwr_lpsi_shutoff_pressure_mpa: float = 3.0
    pwr_accumulator_set_pressure_mpa: float = 4.5
    pwr_accumulator_flow_coefficient_fraction_s_mpa_sqrt: float = 0.0025
    pwr_accumulator_inventory_fraction_of_primary: float = 0.04
    pwr_recirculation_runout_fraction_s: float = 0.0040
    pwr_recirculation_shutoff_pressure_mpa: float = 2.0
    pwr_hpsi_start_delay_s: float = 1.0
    pwr_lpsi_start_delay_s: float = 1.0
    pwr_recirculation_start_delay_s: float = 8.0
    pwr_safety_reset_inventory_fraction: float = 0.98
    pwr_safety_reset_delay_s: float = 10.0
    # Reduced-order primary-loop and steam-generator component model.
    pwr_core_inventory_share: float = 0.30
    pwr_hot_leg_inventory_share: float = 0.20
    pwr_cold_leg_inventory_share: float = 0.42
    pwr_pressurizer_inventory_share: float = 0.08
    pwr_component_inventory_tau_s: float = 4.0
    pwr_loop_flow_tau_s: float = 4.0
    pwr_rcp_shutoff_head_m: float = 111.25
    pwr_loop_loss_head_m: float = 111.25
    pwr_nominal_core_delta_C: float = 41.0
    pwr_natural_circulation_head_per_C_m: float = 0.20
    pwr_secondary_inventory_kg: float = 76965.77
    pwr_secondary_reference_pressure_mpa: float = 5.76
    pwr_secondary_vapor_mass_fraction: float = 0.05
    pwr_secondary_pressure_energy_capacity_MJ_MPa: float = 3500.0
    pwr_afw_capacity_kg_s: float = 900.0
    pwr_axial_node_count: int = 4
    pwr_axial_power_shape_tau_s: float = 1.0
    pwr_axial_void_transport_tau_s: float = 2.0
    pwr_axial_void_shape_feedback: float = 0.9
    pwr_axial_void_reactivity_pcm_per_fraction: float = -1500.0
    pwr_normal_rod_maneuver_tau_s: float = 30.0
    pwr_normal_power_target_slope: float = 1.45
    pwr_normal_power_damping_gain_pcm: float = 500.0

    # Classroom warning limits only.
    cladWarn: float = 650.0
    cladTrip: float = 1200.0
    pressHigh: float = 16.7
    invLow: float = 0.65
    # Generic teaching protection settings, not plant setpoints.
    pwr_rps_high_flux_fraction: float = 1.18
    pwr_rps_high_flux_delay_s: float = 0.10
    pwr_rps_high_pressure_mpa: float = 16.70
    pwr_rps_high_pressure_delay_s: float = 0.50
    pwr_rps_low_inventory_fraction: float = 0.82
    pwr_rps_low_inventory_delay_s: float = 0.50
    pwr_rps_low_flow_fraction: float = 0.75
    pwr_rps_low_flow_power_permissive: float = 0.25
    pwr_rps_low_flow_delay_s: float = 1.00
    pwr_rps_high_clad_C: float = 650.0
    pwr_rps_low_dnbr: float = 1.0
    pwr_rps_thermal_delay_s: float = 0.50

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
class BWRConstants(PWRConstants):
    """Declared phase-1 reference values for a representative BWR equilibrium."""

    plant_type: str = "BWR"
    plant_label: str = "Representative BWR"
    # OECD/NEA Peach Bottom-2 BWR/4 benchmark rated reference quantities.
    # This remains a representative teaching model, not a Peach Bottom model.
    Pnom_MW: float = 3293.0
    Tsink: float = 275.0
    TrefFuel: float = 800.0
    TrefClad: float = 300.0
    TrefCool: float = 285.830022805751
    # BWR fuel heat storage is kept distinct from the deliberately slow PWR
    # classroom surrogate. This gives an approximately 53 s fuel-to-clad time
    # constant at rated conditions and prevents minute-scale feedback lag from
    # manufacturing undamped rod-step power oscillations.
    Cfuel: float = 350.0
    Pref: float = 7.0
    pressure_reference_temperature_C: float = 285.830022805751
    alpha_m: float = -1.0e-5
    cladWarn: float = 650.0
    pressHigh: float = 7.8
    alpha_void: float = -0.035
    bwr_liquid_inventory_kg: float = 300000.0
    bwr_core_inventory_fraction: float = 0.36
    bwr_downcomer_inventory_fraction: float = 0.50
    bwr_upper_plenum_inventory_fraction: float = 0.09
    bwr_separator_inventory_fraction: float = 0.05
    bwr_steam_dome_volume_m3: float = 105.0
    bwr_upper_plenum_residence_s: float = 0.8
    bwr_separator_residence_s: float = 1.2
    bwr_core_vapor_residence_s: float = 1.8
    bwr_level_span_m: float = 5.0
    bwr_reference_core_flow_kg_s: float = 12915.0
    # 191.17 C benchmark feedwater at 7 MPa mapped through the bundled IF97
    # table: hf,sat - h(P,T) = 452.09 kJ/kg.
    bwr_feedwater_subcooling_kJ_kg: float = 452.09
    bwr_natural_circulation_fraction: float = 0.22
    bwr_recirc_tau_s: float = 4.0
    # The benchmark measured 151.685 kPa rated core pressure drop. Converted
    # with the model's 7 MPa saturated-liquid density this is 20.90 m. The
    # actual 216.4 m external recirculation-pump head drives jet pumps and is
    # therefore not inserted directly into this reduced effective-core loop.
    bwr_loop_loss_head_m: float = 20.90
    # Curve shape/shutoff ratio remains generic pending a public pump curve.
    bwr_pump_shutoff_head_m: float = 23.65
    bwr_pump_reference_head_m: float = 17.996
    bwr_reference_buoyancy_head_m: float = 2.904
    # Of the measured core drop, 124.105 kPa (17.10 m) is the support plate;
    # the 3.80 m remainder is represented as bundle/two-phase core friction.
    bwr_core_friction_head_ref_m: float = 3.80
    bwr_single_phase_loss_head_ref_m: float = 17.10
    bwr_acceleration_head_ref_m: float = 0.0
    bwr_reference_leg_tau_s: float = 25.0
    bwr_reference_leg_sensitivity: float = 0.35
    bwr_void_tau_s: float = 1.5
    # Proportional pressure and level regulators represent the fast inner
    # control loops that keep a rod-induced load change from becoming an
    # artificial pressure/inventory transient. Operator sliders remain demand
    # limits rather than raw, fixed valve/flow positions.
    bwr_pressure_regulator_gain: float = 10.0
    bwr_feedwater_regulator_gain: float = 10.0
    bwr_srv_open_mpa: float = 7.55
    bwr_srv_capacity_kg_s: float = 3200.0
    # Quadratic-curve runout equivalents. They reproduce approximately 600 gpm
    # RCIC and 5000 gpm HPCI at 7 MPa with the retained generic 10 MPa shutoff.
    bwr_rcic_capacity_kg_s: float = 68.0
    bwr_hpci_capacity_kg_s: float = 566.0
    bwr_lpci_capacity_kg_s: float = 4200.0
    bwr_core_spray_capacity_kg_s: float = 2300.0
    # Generic screening curves, not plant-specific certified pump data.  The
    # capacity is the zero-differential-pressure runout flow; injection stops
    # when vessel-to-pool differential pressure reaches shutoff pressure.
    bwr_rcic_shutoff_head_mpa: float = 10.0
    bwr_hpci_shutoff_head_mpa: float = 10.0
    bwr_lpci_shutoff_head_mpa: float = 2.0
    bwr_core_spray_shutoff_head_mpa: float = 2.5
    bwr_rcic_driver_min_mpa: float = 0.52
    bwr_hpci_driver_min_mpa: float = 0.52
    bwr_driver_full_mpa: float = 1.5
    bwr_suppression_pool_pressure_mpa: float = 0.10
    bwr_suction_inventory_fraction_min: float = 0.20
    # Full break is an equivalent sharp-edged opening. Flow is calculated by
    # an isentropic homogeneous-equilibrium flashing nozzle, not this value.
    bwr_break_area_m2: float = 0.020
    bwr_break_discharge_coefficient: float = 0.80
    bwr_break_backpressure_mpa: float = 0.10
    bwr_bypass_capacity_kg_s: float = 1900.0
    bwr_pool_mass_kg: float = 2.5e6
    bwr_pool_cp_kJ_kgK: float = 4.18
    bwr_min_coolant_heat_transfer_factor: float = 0.04
    # Generic teaching protection/actuation settings. These are deliberately
    # declared inputs, not technical-specification values for any plant.
    bwr_rps_high_flux_fraction: float = 1.18
    bwr_rps_high_flux_delay_s: float = 0.10
    bwr_rps_high_pressure_mpa: float = 7.80
    bwr_rps_high_pressure_delay_s: float = 0.50
    bwr_rps_low_level_percent: float = 82.0
    bwr_rps_low_level_delay_s: float = 0.50
    bwr_rps_high_clad_C: float = 650.0
    bwr_rps_thermal_delay_s: float = 0.50
    bwr_axial_node_count: int = 4
    bwr_axial_power_shape_tau_s: float = 0.8
    bwr_axial_void_transport_tau_s: float = 1.8
    bwr_axial_void_shape_feedback: float = 1.4
    bwr_rcic_start_level_percent: float = 90.0
    bwr_hpci_start_level_percent: float = 90.0
    bwr_low_pressure_eccs_start_level_percent: float = 85.0
    bwr_ads_start_level_percent: float = 70.0
    bwr_ads_pressure_permissive_mpa: float = 1.50
    bwr_low_pressure_eccs_pressure_permissive_mpa: float = 2.20
    bwr_rcic_start_delay_s: float = 2.0
    bwr_hpci_start_delay_s: float = 1.0
    bwr_ads_start_delay_s: float = 5.0
    bwr_lpci_start_delay_s: float = 1.0
    bwr_core_spray_start_delay_s: float = 1.0
    bwr_eccs_reset_level_percent: float = 95.0
    bwr_eccs_reset_delay_s: float = 10.0


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
    void: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    chf: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    hot_fuel: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    hot_clad: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    hot_outlet: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    hot_dnbr: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_mass_residual: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_energy_residual: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_projection_mass: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_projection_energy: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_primary_flow: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_core_temp: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_hot_leg_temp: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_cold_leg_temp: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_prz_liquid_inventory: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_prz_steam_inventory: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_secondary_mass: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_secondary_pressure: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_axial_power_1: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_axial_power_2: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_axial_power_3: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_axial_power_4: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_axial_void_1: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_axial_void_2: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_axial_void_3: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))
    pwr_axial_void_4: Deque[float] = field(default_factory=lambda: deque(maxlen=1600))

    def as_array(self, name: str) -> np.ndarray:
        return np.array(getattr(self, name), dtype=float)

    def clear(self) -> None:
        for name in (
            "t", "pow", "dec", "Tf", "Tcl", "Tc", "P", "M", "rho",
            "flow", "void", "chf", "hot_fuel", "hot_clad", "hot_outlet",
            "hot_dnbr", "pwr_mass_residual", "pwr_energy_residual",
            "pwr_projection_mass", "pwr_projection_energy",
            "pwr_primary_flow", "pwr_core_temp", "pwr_hot_leg_temp",
            "pwr_cold_leg_temp", "pwr_prz_liquid_inventory",
            "pwr_prz_steam_inventory", "pwr_secondary_mass",
            "pwr_secondary_pressure",
            "pwr_axial_power_1", "pwr_axial_power_2", "pwr_axial_power_3",
            "pwr_axial_power_4", "pwr_axial_void_1", "pwr_axial_void_2",
            "pwr_axial_void_3", "pwr_axial_void_4",
        ):
            getattr(self, name).clear()


@dataclass
class PWRState:
    """Public dynamic and diagnostic state for the PWR model."""

    c: PWRConstants
    t: float = 0.0
    n: float = 1.0
    Ci: np.ndarray = field(init=False)
    Di: np.ndarray = field(init=False)
    Tf: float = field(init=False)
    Tcl: float = field(init=False)
    Tc: float = field(init=False)
    Ucool: float = field(init=False)
    Tprz: float = field(init=False)
    void_fraction: float = 0.0
    boiling_regime: str = "single-phase"
    chf_ratio: float = 0.0
    hot_peak_fuel_C: float = float("nan")
    hot_peak_clad_C: float = float("nan")
    hot_outlet_C: float = float("nan")
    hot_min_dnbr: float = float("nan")
    hot_dnbr_valid_nodes: int = 0
    effective_eccs_fraction: float = 0.0
    auto_eccs_demand: float = 0.0
    break_out_fraction_s: float = 0.0
    porv_out_fraction_s: float = 0.0
    evaporation_out_fraction_s: float = 0.0
    pwr_stored_mass_rate_fraction_s: float = 0.0
    pwr_boundary_mass_rate_fraction_s: float = 0.0
    pwr_mass_balance_residual_fraction_s: float = 0.0
    pwr_stored_energy_rate_MW: float = 0.0
    pwr_boundary_energy_rate_MW: float = 0.0
    pwr_energy_balance_residual_MW: float = 0.0
    pwr_projection_mass_correction_fraction_s: float = 0.0
    pwr_projection_energy_correction_MW: float = 0.0
    pwr_rps_high_flux_timer_s: float = 0.0
    pwr_rps_high_pressure_timer_s: float = 0.0
    pwr_rps_low_inventory_timer_s: float = 0.0
    pwr_rps_low_flow_timer_s: float = 0.0
    pwr_rps_thermal_timer_s: float = 0.0
    pwr_protection_demand: bool = False
    pwr_active_protection_channels: str = "None"
    pwr_trip_cause: str = "None"
    pwr_hpsi_flow_fraction_s: float = 0.0
    pwr_lpsi_flow_fraction_s: float = 0.0
    pwr_accumulator_flow_fraction_s: float = 0.0
    pwr_recirculation_flow_fraction_s: float = 0.0
    pwr_total_injection_fraction_s: float = 0.0
    pwr_hpsi_head_margin_mpa: float = 0.0
    pwr_lpsi_head_margin_mpa: float = 0.0
    pwr_accumulator_inventory_fraction: float = 1.0
    pwr_hpsi_latched: bool = False
    pwr_lpsi_latched: bool = False
    pwr_recirculation_latched: bool = False
    pwr_hpsi_demand_timer_s: float = 0.0
    pwr_lpsi_demand_timer_s: float = 0.0
    pwr_recirculation_demand_timer_s: float = 0.0
    pwr_safety_reset_timer_s: float = 0.0
    pwr_core_inventory_fraction: float = 0.30
    pwr_hot_leg_inventory_fraction: float = 0.20
    pwr_cold_leg_inventory_fraction: float = 0.42
    pwr_pressurizer_liquid_inventory_fraction: float = 0.07
    pwr_pressurizer_steam_inventory_fraction: float = 0.01
    pwr_core_temperature_C: float = 309.0
    pwr_hot_leg_temperature_C: float = 311.0
    pwr_cold_leg_temperature_C: float = 299.0
    pwr_primary_flow_fraction: float = 1.0
    pwr_pump_head_m: float = 95.0
    pwr_buoyancy_head_m: float = 0.0
    pwr_loop_loss_head_m: float = 95.0
    pwr_surge_flow_fraction_s: float = 0.0
    pwr_core_energy_MJ: float = 0.0
    pwr_hot_leg_energy_MJ: float = 0.0
    pwr_cold_leg_energy_MJ: float = 0.0
    pwr_pressurizer_liquid_energy_MJ: float = 0.0
    pwr_pressurizer_steam_energy_MJ: float = 0.0
    pwr_components_initialized: bool = False
    pwr_secondary_mass_kg: float = 0.0
    pwr_secondary_energy_MJ: float = 0.0
    pwr_secondary_pressure_mpa: float = 6.5
    pwr_secondary_steam_flow_kg_s: float = 0.0
    pwr_secondary_feedwater_flow_kg_s: float = 0.0
    pwr_secondary_heat_transfer_MW: float = 0.0
    pwr_secondary_mass_residual_kg_s: float = 0.0
    pwr_secondary_energy_residual_MW: float = 0.0
    pwr_axial_power_fraction: np.ndarray = field(
        default_factory=lambda: np.full(4, 0.25, dtype=float)
    )
    pwr_axial_vapor_fraction: np.ndarray = field(
        default_factory=lambda: np.full(4, 0.25, dtype=float)
    )
    pwr_axial_void_fraction: np.ndarray = field(
        default_factory=lambda: np.zeros(4, dtype=float)
    )
    pwr_axial_peak_node: int = 1
    pwr_axial_spatial_void_signal: float = 0.0
    pwr_effective_rod_pct: float = 0.0
    pwr_normal_power_target: float = 1.0
    pwr_normal_power_damping_pcm: float = 0.0
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
        self.Ucool = self.c.Ccool * self.c.Mref * (
            self.Tc - self.c.coolant_energy_reference_C
        )
        self.Tprz = self.c.pressure_reference_temperature_C
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
        self.Ucool = c.Ccool * c.Mref * (self.Tc - c.coolant_energy_reference_C)
        self.Tprz = c.pressure_reference_temperature_C
        self.void_fraction = 0.0
        self.boiling_regime = "single-phase"
        self.chf_ratio = 0.0
        self.hot_peak_fuel_C = float("nan")
        self.hot_peak_clad_C = float("nan")
        self.hot_outlet_C = float("nan")
        self.hot_min_dnbr = float("nan")
        self.hot_dnbr_valid_nodes = 0
        self.effective_eccs_fraction = 0.0
        self.auto_eccs_demand = 0.0
        self.break_out_fraction_s = 0.0
        self.porv_out_fraction_s = 0.0
        self.evaporation_out_fraction_s = 0.0
        self.pwr_stored_mass_rate_fraction_s = 0.0
        self.pwr_boundary_mass_rate_fraction_s = 0.0
        self.pwr_mass_balance_residual_fraction_s = 0.0
        self.pwr_stored_energy_rate_MW = 0.0
        self.pwr_boundary_energy_rate_MW = 0.0
        self.pwr_energy_balance_residual_MW = 0.0
        self.pwr_projection_mass_correction_fraction_s = 0.0
        self.pwr_projection_energy_correction_MW = 0.0
        self.pwr_rps_high_flux_timer_s = 0.0
        self.pwr_rps_high_pressure_timer_s = 0.0
        self.pwr_rps_low_inventory_timer_s = 0.0
        self.pwr_rps_low_flow_timer_s = 0.0
        self.pwr_rps_thermal_timer_s = 0.0
        self.pwr_protection_demand = False
        self.pwr_active_protection_channels = "None"
        self.pwr_trip_cause = "None"
        self.pwr_hpsi_flow_fraction_s = 0.0
        self.pwr_lpsi_flow_fraction_s = 0.0
        self.pwr_accumulator_flow_fraction_s = 0.0
        self.pwr_recirculation_flow_fraction_s = 0.0
        self.pwr_total_injection_fraction_s = 0.0
        self.pwr_hpsi_head_margin_mpa = 0.0
        self.pwr_lpsi_head_margin_mpa = 0.0
        self.pwr_accumulator_inventory_fraction = 1.0
        self.pwr_hpsi_latched = False
        self.pwr_lpsi_latched = False
        self.pwr_recirculation_latched = False
        self.pwr_hpsi_demand_timer_s = 0.0
        self.pwr_lpsi_demand_timer_s = 0.0
        self.pwr_recirculation_demand_timer_s = 0.0
        self.pwr_safety_reset_timer_s = 0.0
        self.pwr_core_inventory_fraction = c.pwr_core_inventory_share
        self.pwr_hot_leg_inventory_fraction = c.pwr_hot_leg_inventory_share
        self.pwr_cold_leg_inventory_fraction = c.pwr_cold_leg_inventory_share
        self.pwr_pressurizer_liquid_inventory_fraction = 0.875 * c.pwr_pressurizer_inventory_share
        self.pwr_pressurizer_steam_inventory_fraction = 0.125 * c.pwr_pressurizer_inventory_share
        self.pwr_core_temperature_C = c.TrefCool
        self.pwr_hot_leg_temperature_C = c.TrefCool + 0.5 * c.pwr_nominal_core_delta_C
        self.pwr_cold_leg_temperature_C = c.TrefCool - 0.5 * c.pwr_nominal_core_delta_C
        self.pwr_primary_flow_fraction = 1.0
        self.pwr_pump_head_m = c.pwr_rcp_shutoff_head_m
        self.pwr_buoyancy_head_m = 0.0
        self.pwr_loop_loss_head_m = c.pwr_loop_loss_head_m
        self.pwr_surge_flow_fraction_s = 0.0
        self.pwr_core_energy_MJ = 0.0
        self.pwr_hot_leg_energy_MJ = 0.0
        self.pwr_cold_leg_energy_MJ = 0.0
        self.pwr_pressurizer_liquid_energy_MJ = 0.0
        self.pwr_pressurizer_steam_energy_MJ = 0.0
        self.pwr_components_initialized = False
        self.pwr_secondary_mass_kg = c.pwr_secondary_inventory_kg
        self.pwr_secondary_energy_MJ = 0.0
        self.pwr_secondary_pressure_mpa = c.pwr_secondary_reference_pressure_mpa
        self.pwr_secondary_steam_flow_kg_s = 0.0
        self.pwr_secondary_feedwater_flow_kg_s = 0.0
        self.pwr_secondary_heat_transfer_MW = 0.0
        self.pwr_secondary_mass_residual_kg_s = 0.0
        self.pwr_secondary_energy_residual_MW = 0.0
        z = (np.arange(c.pwr_axial_node_count, dtype=float) + 0.5) / c.pwr_axial_node_count
        base = np.sin(np.pi * z)
        self.pwr_axial_power_fraction = base / np.sum(base)
        vapor = np.cumsum(self.pwr_axial_power_fraction)
        self.pwr_axial_vapor_fraction = vapor / np.sum(vapor)
        self.pwr_axial_void_fraction = np.zeros(c.pwr_axial_node_count, dtype=float)
        self.pwr_axial_peak_node = int(np.argmax(self.pwr_axial_power_fraction)) + 1
        self.pwr_axial_spatial_void_signal = 0.0
        self.pwr_effective_rod_pct = 0.0
        self.pwr_normal_power_target = 1.0
        self.pwr_normal_power_damping_pcm = 0.0
        self.P = c.Pref
        self.M = c.Mref
        self.trip = False
        self.autoECCS = True
        self.scenario_name = "Normal operation"
        self.hist.clear()


@dataclass
class BWRState(PWRState):
    """BWR-only vessel, safety-system, level, and conservation state."""

    bwr_core_mass_kg: float = 0.0
    bwr_core_energy_MJ: float = 0.0
    bwr_downcomer_mass_kg: float = 0.0
    bwr_downcomer_energy_MJ: float = 0.0
    bwr_upper_plenum_mass_kg: float = 0.0
    bwr_upper_plenum_energy_MJ: float = 0.0
    bwr_separator_mass_kg: float = 0.0
    bwr_separator_energy_MJ: float = 0.0
    bwr_steam_mass_kg: float = 0.0
    bwr_steam_energy_MJ: float = 0.0
    bwr_core_vapor_mass_kg: float = 0.0
    bwr_core_vapor_energy_MJ: float = 0.0
    bwr_core_flow_fraction: float = 1.0
    bwr_pump_head_m: float = 0.0
    bwr_buoyancy_head_m: float = 0.0
    bwr_friction_head_m: float = 0.0
    bwr_core_friction_head_m: float = 0.0
    bwr_single_phase_loss_head_m: float = 0.0
    bwr_acceleration_head_m: float = 0.0
    bwr_two_phase_friction_multiplier: float = 1.0
    bwr_steam_flow_kg_s: float = 0.0
    bwr_feedwater_flow_kg_s: float = 0.0
    bwr_srv_flow_kg_s: float = 0.0
    bwr_downcomer_temperature_C: float = 0.0
    bwr_liquid_energy_residual_MW: float = 0.0
    bwr_collapsed_level_percent: float = 100.0
    bwr_indicated_level_percent: float = 100.0
    bwr_indicated_level_m: float = 0.0
    bwr_reference_leg_temperature_C: float = 0.0
    bwr_collapsed_level_m: float = 0.0
    bwr_steam_dome_volume_m3: float = 0.0
    bwr_steam_volume_residual_m3: float = 0.0
    bwr_steam_energy_residual_MJ: float = 0.0
    bwr_rcic_flow_kg_s: float = 0.0
    bwr_hpci_flow_kg_s: float = 0.0
    bwr_lpci_flow_kg_s: float = 0.0
    bwr_core_spray_flow_kg_s: float = 0.0
    bwr_break_flow_kg_s: float = 0.0
    bwr_break_critical_pressure_mpa: float = 0.0
    bwr_break_mass_flux_kg_m2_s: float = 0.0
    bwr_break_choked: bool = False
    bwr_rcic_head_margin_mpa: float = 0.0
    bwr_hpci_head_margin_mpa: float = 0.0
    bwr_lpci_head_margin_mpa: float = 0.0
    bwr_core_spray_head_margin_mpa: float = 0.0
    bwr_coolant_heat_transfer_factor: float = 1.0
    bwr_heat_transfer_regime: str = "single-phase convection"
    bwr_critical_power_coupled: bool = False
    bwr_bypass_flow_kg_s: float = 0.0
    bwr_shutdown_cooling_MW: float = 0.0
    bwr_suppression_pool_temperature_C: float = 35.0
    bwr_suppression_pool_mass_kg: float = 0.0
    bwr_suppression_pool_energy_MJ: float = 0.0
    bwr_mass_balance_residual_kg_s: float = 0.0
    bwr_energy_balance_residual_MW: float = 0.0
    bwr_vessel_pool_mass_residual_kg_s: float = 0.0
    bwr_vessel_pool_energy_residual_MW: float = 0.0
    bwr_rcic_latched: bool = False
    bwr_hpci_latched: bool = False
    bwr_ads_latched: bool = False
    bwr_lpci_latched: bool = False
    bwr_core_spray_latched: bool = False
    bwr_rcic_demand_timer_s: float = 0.0
    bwr_hpci_demand_timer_s: float = 0.0
    bwr_ads_demand_timer_s: float = 0.0
    bwr_lpci_demand_timer_s: float = 0.0
    bwr_core_spray_demand_timer_s: float = 0.0
    bwr_safety_reset_timer_s: float = 0.0
    bwr_trip_demand_timer_s: float = 0.0
    bwr_rps_high_flux_timer_s: float = 0.0
    bwr_rps_high_pressure_timer_s: float = 0.0
    bwr_rps_low_level_timer_s: float = 0.0
    bwr_rps_thermal_timer_s: float = 0.0
    bwr_protection_demand: bool = False
    bwr_trip_cause: str = "None"
    bwr_axial_power_fraction: np.ndarray = field(
        default_factory=lambda: np.full(4, 0.25, dtype=float)
    )
    bwr_axial_vapor_fraction: np.ndarray = field(
        default_factory=lambda: np.full(4, 0.25, dtype=float)
    )
    bwr_axial_void_fraction: np.ndarray = field(
        default_factory=lambda: np.zeros(4, dtype=float)
    )
    bwr_axial_peak_node: int = 1


# Backward-compatible names used by existing notebooks and front ends.
Constants = PWRConstants
State = PWRState


@dataclass(frozen=True)
class TimelineEvent:
    time_s: float
    category: str
    message: str


# ---------------------------------------------------------------------------
# GUI application
# ---------------------------------------------------------------------------


class LWRTeachingSimulator:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.c = PWRConstants()
        self.state = PWRState(self.c)
        self.steam_tables = SteamTables()
        self.physics = create_plant_model(self.c.plant_type, self.c, self.steam_tables)
        self.physics.initialize_state(self.state)
        self.hot_channel = HotChannelModel(self.steam_tables)
        self.bwr_hot_channel = BWRHotChannelModel(self.steam_tables)
        self.hot_channel_window: Optional[tk.Toplevel] = None
        self.hot_channel_result: Optional[HotChannelResult] = None
        self.hot_channel_result_time = float("nan")
        self.hot_channel_error: Optional[str] = None
        self.hot_channel_rendered_time = float("nan")
        self.hot_channel_update_interval_s = 0.25
        self.hot_channel_display_interval_s = 0.25
        self.last_hot_channel_render_wall = 0.0
        self.hot_flux_reference_max_MW_m2 = 6.0
        self.hot_dnbr_reference_max = 6.0

        self.running = False
        self.freeze_chart = False
        self.last_wall_time = time.perf_counter()
        self.last_display_refresh_wall = 0.0
        self.display_refresh_interval_s = 0.10
        self.after_id: str | None = None

        self.root.title("LWR Thermal-Hydraulics / LOCA Teaching Simulator - Python")
        self.root.geometry("1420x820")
        self.root.minsize(1150, 680)
        self.root.configure(bg="#202226")

        self.control_vars: Dict[str, tk.DoubleVar] = {}
        self.value_labels: Dict[str, ttk.Label] = {}
        self.readout_vars: Dict[str, tk.StringVar] = {}
        self.lamps: Dict[str, tk.Label] = {}
        self.events: Deque[TimelineEvent] = deque(maxlen=250)
        self.event_snapshot: Dict[str, object] = {}
        self.last_event_time: Dict[str, float] = {}

        self.auto_eccs_var = tk.BooleanVar(value=True)
        self.auto_trip_var = tk.BooleanVar(value=True)
        self.bwr_system_availability = {
            name: True for name in ("rcic", "hpci", "ads", "lpci", "core_spray")
        }
        self.pwr_system_availability = {
            name: True for name in ("hpsi", "lpsi", "accumulator", "recirculation")
        }
        self.hot_channel_coupling_var = tk.BooleanVar(value=True)

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
        self.reset_event_timeline()
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
            text="LIGHT WATER REACTOR THERMAL-HYDRAULICS TRAINING PANEL",
        ).pack(anchor="w")
        tk.Label(
            title_block, text=PROJECT_NAME, bg="#0e1013", fg="#b8c2cc",
            font=("Segoe UI", 9), anchor="w",
        ).pack(anchor="w", pady=(3, 0))


        ttk.Button(header, text="ABOUT", command=lambda: show_suite_about(self.root)).pack(
            side=tk.RIGHT, padx=(4, 0), pady=18,
        )

        main = ttk.Frame(self.root, style="TFrame")
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))

        plot_frame = ttk.Frame(main, style="TFrame")
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        panel_host = ttk.Frame(main, style="Panel.TFrame", width=620)
        panel_host.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        panel_host.pack_propagate(False)

        self.control_canvas = tk.Canvas(
            panel_host,
            width=600,
            bg="#2a2d33",
            highlightthickness=0,
            borderwidth=0,
        )
        control_scroll = ttk.Scrollbar(
            panel_host, orient=tk.VERTICAL, command=self.control_canvas.yview
        )
        self.control_canvas.configure(yscrollcommand=control_scroll.set)
        control_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.control_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        panel = ttk.Frame(self.control_canvas, style="Panel.TFrame", padding=12)
        self.control_panel_window = self.control_canvas.create_window(
            (0, 0), window=panel, anchor="nw"
        )
        panel.bind("<Configure>", self._on_control_panel_configure)
        self.control_canvas.bind("<Configure>", self._on_control_canvas_configure)
        self.control_canvas.bind("<MouseWheel>", self._scroll_control_panel)

        ttk.Label(panel, style="PanelTitle.TLabel", text="CONTROL PANEL").pack(anchor="w", pady=(0, 8))

        self._build_plots(plot_frame)
        self._build_controls(panel)
        self._bind_control_mousewheel(panel)

    def _on_control_panel_configure(self, _event: tk.Event) -> None:
        self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all"))

    def _on_control_canvas_configure(self, event: tk.Event) -> None:
        self.control_canvas.itemconfigure(self.control_panel_window, width=event.width)

    def _bind_control_mousewheel(self, widget: tk.Misc) -> None:
        if isinstance(widget, ttk.Treeview):
            return
        widget.bind("<MouseWheel>", self._scroll_control_panel, add="+")
        for child in widget.winfo_children():
            self._bind_control_mousewheel(child)

    def _scroll_control_panel(self, event: tk.Event) -> None:
        direction = -1 if event.delta > 0 else 1
        self.control_canvas.yview_scroll(direction, "units")

    def _build_plots(self, parent: ttk.Frame) -> None:
        self.fig = Figure(figsize=(7.2, 7.5), dpi=100, facecolor="#202226")
        self.ax_power = self.fig.add_subplot(311)
        self.ax_temp = self.fig.add_subplot(312)
        self.ax_press = self.fig.add_subplot(313)
        self.fig.subplots_adjust(left=0.10, right=0.89, top=0.96, bottom=0.07, hspace=0.42)

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

        self.ax_decay = self.ax_power.twinx()
        self.ax_decay.tick_params(axis="y", colors="white")
        self.ax_decay.yaxis.label.set_color("white")
        self.ax_decay.spines["right"].set_color("white")
        (self.line_pow,) = self.ax_power.plot(
            [], [], linewidth=1.4, color="#1f77b4", label="Indicated power"
        )
        (self.line_dec,) = self.ax_decay.plot(
            [], [], linewidth=1.3, color="#d62728", label="Decay heat"
        )
        self.ax_power.set_xlabel("time (s)", color="white")
        self.ax_power.set_ylabel("Power (%)", color="white")
        self.ax_decay.set_ylabel("Decay heat (% nominal)", color="white")
        self.ax_power.set_title("Strip chart: indicated power and decay heat", color="white")
        self._style_legend(
            self.ax_power.legend(
                [self.line_pow, self.line_dec],
                [self.line_pow.get_label(), self.line_dec.get_label()],
                loc="upper right",
            )
        )

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
        ttk.Button(
            demo_frame, text="HOT CHANNEL", command=self.open_hot_channel
        ).grid(row=1, column=1, columnspan=2, sticky="ew", pady=(5, 0), padx=(0, 6))
        ttk.Button(
            demo_frame, text="SCENARIO SUMMARY", command=self.open_scenario_summary
        ).grid(row=1, column=3, sticky="ew", pady=(5, 0))
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
        ttk.Checkbutton(
            checks, text="Couple axial hot channel", variable=self.hot_channel_coupling_var
        ).grid(row=0, column=2, sticky="w", padx=(35, 0))

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

        timeline_title = ttk.Frame(parent, style="Panel.TFrame")
        timeline_title.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(
            timeline_title, style="Text.TLabel", font=("Segoe UI", 9, "bold"),
            text="EVENT TIMELINE",
        ).pack(side=tk.LEFT)
        ttk.Button(
            timeline_title, text="CLEAR", command=self.clear_event_timeline,
        ).pack(side=tk.RIGHT)

        timeline_frame = ttk.Frame(parent, style="Panel.TFrame")
        timeline_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self.event_tree = ttk.Treeview(
            timeline_frame,
            columns=("time", "category", "event"),
            show="headings",
            height=5,
            selectmode="browse",
        )
        self.event_tree.heading("time", text="Time")
        self.event_tree.heading("category", text="Type")
        self.event_tree.heading("event", text="Event")
        self.event_tree.column("time", width=64, minwidth=58, anchor="e", stretch=False)
        self.event_tree.column("category", width=84, minwidth=72, anchor="w", stretch=False)
        self.event_tree.column("event", width=390, minwidth=220, anchor="w")
        event_scroll = ttk.Scrollbar(
            timeline_frame, orient=tk.VERTICAL, command=self.event_tree.yview
        )
        self.event_tree.configure(yscrollcommand=event_scroll.set)
        self.event_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        event_scroll.pack(side=tk.RIGHT, fill=tk.Y)

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

    # -------------------------- Hot-channel view --------------------------

    def update_auto_eccs_demand(self) -> float:
        """Update the latched automatic-ECCS demand with recovery hysteresis."""
        s = self.state
        if self.c.plant_type == "BWR":
            enabled = bool(self.auto_eccs_var.get())
            s.auto_eccs_demand = 1.0 if enabled and s.M < 0.90 else 0.0
            return s.auto_eccs_demand
        if not bool(self.auto_eccs_var.get()):
            s.auto_eccs_demand = 0.0
            return 0.0

        demand = self.clamp(s.auto_eccs_demand, 0.0, 1.0)
        coupled = bool(self.hot_channel_coupling_var.get())
        hot_clad = (
            s.hot_peak_clad_C
            if coupled and np.isfinite(s.hot_peak_clad_C) else s.Tcl
        )
        hot_dnbr_limit = (
            coupled and np.isfinite(s.hot_min_dnbr) and s.hot_min_dnbr <= 1.0
        )
        if (s.P < 12.0 and s.M < 0.92) or max(s.Tcl, hot_clad) > 450.0:
            demand = max(demand, 0.35)
        if hot_dnbr_limit or (s.P < 4.5 and s.M < 1.05):
            demand = max(demand, 0.85)
        if s.P < 2.0 and s.M < 1.10:
            demand = 1.0

        # Safety injection stays latched throughout an active break or a
        # depressurized recovery. It clears only after generous recovery
        # margins, preventing threshold chatter around 105% inventory.
        recovered = (
            self.control_vars["break"].get() < 1.0
            and s.P > 13.0
            and s.M > 0.98
            and max(s.Tcl, hot_clad) < 400.0
            and (not np.isfinite(s.hot_min_dnbr) or s.hot_min_dnbr > 1.30)
        )
        if recovered:
            demand = 0.0
        s.auto_eccs_demand = demand
        return demand

    def effective_eccs_fraction(self) -> float:
        """Return the pressure-adjusted manual/automatic ECCS fraction."""
        s = self.state
        automatic = s.auto_eccs_demand if bool(self.auto_eccs_var.get()) else 0.0
        requested = max(self.control_vars["eccs"].get() / 100.0, automatic)
        return self.clamp(requested * self.physics.pressure_eccs_factor(s.P), 0.0, 1.0)

    def calculate_hot_channel(self) -> HotChannelResult:
        s, c = self.state, self.c
        heat_fraction = c.prompt_frac * s.n + float(np.sum(c.decay_lambda * s.Di))
        if c.plant_type == "BWR":
            saturation_temperature = self.steam_tables.saturation_temperature(
                self.clamp(s.P, 0.10, 17.50)
            )
            inlet_temperature = self.clamp(
                s.bwr_downcomer_temperature_C, 25.0, saturation_temperature-0.1
            )
            return self.bwr_hot_channel.solve(
                heat_fraction, self.clamp(s.P, 0.10, 17.50), inlet_temperature,
                s.bwr_core_flow_fraction, s.bwr_axial_power_fraction,
            )
        pump = max(0.0, self.control_vars["pump"].get() / 100.0)
        natural = 0.035 + 0.08 * self.clamp(s.M, 0.0, 1.0)
        break_bypass = 1.0 - 0.35 * self.clamp(
            self.control_vars["break"].get() / 100.0, 0.0, 1.0
        )
        flow_fraction = max(
            natural, pump * math.sqrt(max(s.M, 0.02)) * break_bypass
        )
        eccs_effective = self.effective_eccs_fraction()
        saturation_temperature = self.steam_tables.saturation_temperature(
            self.clamp(s.P, 0.10, 17.50)
        )
        inlet_temperature = self.clamp(
            s.Tc - 15.0 - 35.0 * eccs_effective,
            25.0, saturation_temperature - 1.0,
        )
        return self.hot_channel.solve(
            heat_fraction, self.clamp(s.P, 0.10, 17.50),
            inlet_temperature, flow_fraction, s.pwr_axial_power_fraction,
        )

    def update_hot_channel_state(self, result: Optional[HotChannelResult]) -> None:
        s = self.state
        if result is None:
            s.hot_peak_fuel_C = float("nan")
            s.hot_peak_clad_C = float("nan")
            s.hot_outlet_C = float("nan")
            s.hot_min_dnbr = float("nan")
            s.hot_dnbr_valid_nodes = 0
            return
        s.hot_peak_fuel_C = float(np.nanmax(result.fuel_centerline_temperature_C))
        s.hot_peak_clad_C = float(np.nanmax(result.clad_surface_temperature_C))
        s.hot_outlet_C = result.outlet_temperature_C
        s.hot_min_dnbr = result.minimum_dnbr
        s.hot_dnbr_valid_nodes = int(np.count_nonzero(result.chf_correlation_valid))
        if not s.trip:
            flux_values = np.concatenate((
                result.surface_heat_flux_W_m2 / 1.0e6,
                result.critical_heat_flux_W_m2 / 1.0e6,
            ))
            finite_flux = flux_values[np.isfinite(flux_values)]
            if finite_flux.size:
                self.hot_flux_reference_max_MW_m2 = max(
                    1.0, 1.10 * float(np.max(finite_flux))
                )
            finite_dnbr = result.dnbr[np.isfinite(result.dnbr)]
            if finite_dnbr.size:
                self.hot_dnbr_reference_max = min(
                    10.0, max(3.0, 1.50 * float(np.min(finite_dnbr)))
                )

    def scenario_summary_text(self) -> str:
        s, hist = self.state, self.state.hist

        def extrema(name: str, function, fallback: float) -> float:
            values = hist.as_array(name)
            finite = values[np.isfinite(values)]
            return fallback if finite.size == 0 else float(function(finite))

        min_dnbr = extrema("hot_dnbr", np.min, s.hot_min_dnbr)
        dnbr_text = "unavailable" if not np.isfinite(min_dnbr) else f"{min_dnbr:.2f}"
        coupling = "enabled" if bool(self.hot_channel_coupling_var.get()) else "disabled"
        if self.c.plant_type == "PWR":
            max_mass_residual = extrema(
                "pwr_mass_residual", lambda values: np.max(np.abs(values)),
                abs(s.pwr_mass_balance_residual_fraction_s),
            )
            max_energy_residual = extrema(
                "pwr_energy_residual", lambda values: np.max(np.abs(values)),
                abs(s.pwr_energy_balance_residual_MW),
            )
            max_projection_mass = extrema(
                "pwr_projection_mass", lambda values: np.max(np.abs(values)),
                abs(s.pwr_projection_mass_correction_fraction_s),
            )
            max_projection_energy = extrema(
                "pwr_projection_energy", lambda values: np.max(np.abs(values)),
                abs(s.pwr_projection_energy_correction_MW),
            )
            ledger_text = (
                f"\nPWR protection demand: {'yes' if s.pwr_protection_demand else 'no'}"
                f"\nPWR active protection channels: {s.pwr_active_protection_channels}"
                f"\nPWR retained trip cause: {s.pwr_trip_cause}"
                f"\nPWR HPSI / LPSI flow: {s.pwr_hpsi_flow_fraction_s:.3e} / "
                f"{s.pwr_lpsi_flow_fraction_s:.3e} fraction/s"
                f"\nPWR accumulator / recirculation flow: "
                f"{s.pwr_accumulator_flow_fraction_s:.3e} / "
                f"{s.pwr_recirculation_flow_fraction_s:.3e} fraction/s"
                f"\nPWR accumulator inventory remaining: "
                f"{100.0*s.pwr_accumulator_inventory_fraction:.1f}%"
                f"\nMaximum PWR mass-balance residual: {max_mass_residual:.3e} fraction/s"
                f"\nMaximum PWR energy-balance residual: {max_energy_residual:.3e} MW"
                f"\nMaximum PWR projection mass correction: {max_projection_mass:.3e} fraction/s"
                f"\nMaximum PWR projection energy correction: {max_projection_energy:.3e} MW"
            )
        else:
            ledger_text = ""
        return (
            f"Scenario: {s.scenario_name}\n"
            f"Elapsed simulation time: {s.t:.1f} s\n"
            f"Axial-to-lumped coupling: {coupling}\n"
            f"Peak lumped fuel temperature: {extrema('Tf', np.max, s.Tf):.1f} C\n"
            f"Peak lumped clad temperature: {extrema('Tcl', np.max, s.Tcl):.1f} C\n"
            f"Peak axial fuel-centre temperature: "
            f"{extrema('hot_fuel', np.max, s.hot_peak_fuel_C):.1f} C\n"
            f"Peak axial clad-surface temperature: "
            f"{extrema('hot_clad', np.max, s.hot_peak_clad_C):.1f} C\n"
            f"Minimum primary inventory: {extrema('M', np.min, 100.0 * s.M):.1f}%\n"
            f"Minimum pressure: {extrema('P', np.min, s.P):.2f} MPa\n"
            f"Minimum in-range W-3 DNBR: {dnbr_text}\n"
            f"Reactor trip: {'yes' if s.trip else 'no'}"
            f"{ledger_text}\n"
            f"Recorded timeline events: {len(self.events)}"
        )

    def open_scenario_summary(self) -> None:
        messagebox.showinfo("Scenario summary", self.scenario_summary_text())

    def open_hot_channel(self) -> None:
        if self.hot_channel_window is not None and self.hot_channel_window.winfo_exists():
            self.hot_channel_window.lift()
            self.hot_channel_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        self.hot_channel_window = window
        window.title("Representative 1-D Hot Channel")
        window.geometry("1180x900")
        window.minsize(900, 680)
        window.configure(bg="#202226")
        window.protocol("WM_DELETE_WINDOW", self.close_hot_channel)

        scroll_shell = tk.Frame(window, bg="#202226")
        scroll_shell.pack(fill=tk.BOTH, expand=True)
        self.hot_scroll_canvas = tk.Canvas(
            scroll_shell, bg="#202226", highlightthickness=0
        )
        outer_scroll = ttk.Scrollbar(
            scroll_shell, orient=tk.VERTICAL, command=self.hot_scroll_canvas.yview
        )
        self.hot_scroll_canvas.configure(yscrollcommand=outer_scroll.set)
        outer_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.hot_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        content = tk.Frame(self.hot_scroll_canvas, bg="#202226")
        content_window = self.hot_scroll_canvas.create_window(
            (0, 0), window=content, anchor="nw"
        )

        def update_scroll_region(_event=None) -> None:
            self.hot_scroll_canvas.configure(
                scrollregion=self.hot_scroll_canvas.bbox("all")
            )

        def match_content_width(event) -> None:
            self.hot_scroll_canvas.itemconfigure(content_window, width=event.width)

        def scroll_hot_window(event) -> str:
            units = -1 if event.delta > 0 else 1
            self.hot_scroll_canvas.yview_scroll(units * 3, "units")
            return "break"

        content.bind("<Configure>", update_scroll_region)
        self.hot_scroll_canvas.bind("<Configure>", match_content_width)
        window.bind("<MouseWheel>", scroll_hot_window)
        window.bind(
            "<Prior>", lambda _event: self.hot_scroll_canvas.yview_scroll(-1, "pages")
        )
        window.bind(
            "<Next>", lambda _event: self.hot_scroll_canvas.yview_scroll(1, "pages")
        )
        window.bind("<Home>", lambda _event: self.hot_scroll_canvas.yview_moveto(0.0))
        window.bind("<End>", lambda _event: self.hot_scroll_canvas.yview_moveto(1.0))

        self.hot_channel_summary_var = tk.StringVar(value="Calculating hot channel...")
        tk.Label(
            content, textvariable=self.hot_channel_summary_var, bg="#101114",
            fg="#f4f4f4", justify=tk.LEFT, anchor="w", wraplength=1040,
            padx=10, pady=8, font=("Segoe UI", 10),
        ).pack(fill=tk.X, padx=10, pady=(10, 6))

        figure = Figure(figsize=(10.2, 7.5), dpi=100, facecolor="#202226")
        self.hot_channel_ax = figure.add_subplot(311)
        self.hot_coolant_ax = self.hot_channel_ax.twinx()
        self.hot_channel_ax.set_facecolor("#f6f6f6")
        self.hot_channel_ax.grid(True, alpha=0.35)
        self.hot_channel_ax.set_ylabel("Fuel centre (degC)", color="white")
        self.hot_coolant_ax.set_ylabel(
            "Clad / coolant / saturation (degC)", color="white"
        )
        self.hot_channel_ax.set_title("Axial hot-channel temperatures", color="white")
        self.hot_channel_ax.tick_params(axis="both", colors="white")
        self.hot_coolant_ax.tick_params(axis="y", colors="white")
        for spine in self.hot_channel_ax.spines.values():
            spine.set_color("white")
        self.hot_coolant_ax.spines["right"].set_color("white")
        (self.hot_line_fuel,) = self.hot_channel_ax.plot(
            [], [], color="#9467bd", linewidth=1.6, label="Fuel centre"
        )
        (self.hot_line_clad,) = self.hot_coolant_ax.plot(
            [], [], color="#d62728", linewidth=1.5, label="Clad surface"
        )
        (self.hot_line_bulk,) = self.hot_coolant_ax.plot(
            [], [], color="#1f77b4", linewidth=1.5, label="Bulk coolant"
        )
        (self.hot_line_sat,) = self.hot_coolant_ax.plot(
            [], [], color="#2ca02c", linestyle="--", label="Saturation temperature"
        )
        self._style_legend(
            self.hot_channel_ax.legend(
                [self.hot_line_fuel, self.hot_line_clad, self.hot_line_bulk, self.hot_line_sat],
                ["Fuel centre", "Clad surface", "Bulk coolant", "Saturation temperature"],
                loc="best",
            )
        )

        self.hot_flux_ax = figure.add_subplot(312, sharex=self.hot_channel_ax)
        self.hot_dnbr_ax = self.hot_flux_ax.twinx()
        self.hot_flux_ax.set_facecolor("#f6f6f6")
        self.hot_flux_ax.grid(True, alpha=0.35)
        self.hot_flux_ax.set_xlabel("Distance from channel inlet (m)", color="white")
        self.hot_flux_ax.set_ylabel("Heat flux (MW/m2)", color="white")
        self.hot_dnbr_ax.set_ylabel("DNBR (-)", color="white")
        self.hot_flux_ax.set_title("Local heat flux, W-3 CHF, and DNBR", color="white")
        self.hot_flux_ax.tick_params(axis="both", colors="white")
        self.hot_dnbr_ax.tick_params(axis="y", colors="white")
        for spine in self.hot_flux_ax.spines.values():
            spine.set_color("white")
        self.hot_dnbr_ax.spines["right"].set_color("white")
        (self.hot_line_heat_flux,) = self.hot_flux_ax.plot(
            [], [], color="#ff7f0e", linewidth=1.5,
            label="Actual heat flux (fission + decay)"
        )
        (self.hot_line_chf,) = self.hot_flux_ax.plot(
            [], [], color="#17becf", linewidth=1.5, label="W-3 CHF"
        )
        (self.hot_line_dnbr,) = self.hot_dnbr_ax.plot(
            [], [], color="#111111", linewidth=1.4, label="DNBR"
        )
        self.hot_dnbr_ax.axhline(
            1.0, color="#d62728", linestyle=":", linewidth=1.0, label="DNBR = 1"
        )
        self._style_legend(
            self.hot_flux_ax.legend(
                [self.hot_line_heat_flux, self.hot_line_chf, self.hot_line_dnbr],
                ["Actual heat flux (fission + decay)", "W-3 CHF", "DNBR"], loc="best",
            )
        )

        self.hot_trend_ax = figure.add_subplot(313)
        self.hot_trend_coolant_ax = self.hot_trend_ax.twinx()
        self.hot_trend_ax.set_facecolor("#f6f6f6")
        self.hot_trend_ax.grid(True, alpha=0.35)
        self.hot_trend_ax.set_xlabel("Simulation time (s)", color="white")
        self.hot_trend_ax.set_ylabel("Peak fuel centre (degC)", color="white")
        self.hot_trend_coolant_ax.set_ylabel("Peak clad / outlet (degC)", color="white")
        self.hot_trend_ax.set_title(
            "Transient hot-channel response: decay heat versus available cooling",
            color="white",
        )
        self.hot_trend_ax.tick_params(axis="both", colors="white")
        self.hot_trend_coolant_ax.tick_params(axis="y", colors="white")
        for spine in self.hot_trend_ax.spines.values():
            spine.set_color("white")
        self.hot_trend_coolant_ax.spines["right"].set_color("white")
        (self.hot_trend_fuel,) = self.hot_trend_ax.plot(
            [], [], color="#9467bd", linewidth=1.4, label="Peak fuel centre"
        )
        (self.hot_trend_clad,) = self.hot_trend_coolant_ax.plot(
            [], [], color="#d62728", linewidth=1.4, label="Peak clad surface"
        )
        (self.hot_trend_outlet,) = self.hot_trend_coolant_ax.plot(
            [], [], color="#1f77b4", linewidth=1.4, label="Coolant outlet"
        )
        self._style_legend(
            self.hot_trend_ax.legend(
                [self.hot_trend_fuel, self.hot_trend_clad, self.hot_trend_outlet],
                ["Peak fuel centre", "Peak clad surface", "Coolant outlet"],
                loc="best",
            )
        )
        figure.subplots_adjust(left=0.09, right=0.88, top=0.95, bottom=0.07, hspace=0.58)
        self.hot_channel_canvas = FigureCanvasTkAgg(figure, master=content)
        self.hot_channel_canvas.get_tk_widget().pack(
            fill=tk.X, expand=False, padx=10, pady=4
        )

        table_frame = ttk.Frame(content)
        table_frame.pack(fill=tk.X, expand=False, padx=10, pady=(4, 10))
        columns = (
            "node", "z", "pressure", "enthalpy", "bulk", "clad", "fuel",
            "quality", "xe", "heat_flux", "chf", "dnbr",
        )
        self.hot_channel_tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=7
        )
        headings = {
            "node": "Node", "z": "z (m)", "pressure": "P (MPa)",
            "enthalpy": "h (kJ/kg)", "bulk": "Coolant (C)",
            "clad": "Clad (C)", "fuel": "Fuel centre (C)", "quality": "Quality",
            "xe": "Eq. quality", "heat_flux": "q actual (MW/m2)",
            "chf": "W-3 CHF (MW/m2)", "dnbr": "DNBR",
        }
        widths = {"node": 55, "z": 75, "pressure": 85, "enthalpy": 100,
                  "bulk": 95, "clad": 85, "fuel": 110, "quality": 85,
                  "xe": 90, "heat_flux": 125, "chf": 125, "dnbr": 75}
        for column in columns:
            self.hot_channel_tree.heading(column, text=headings[column])
            self.hot_channel_tree.column(column, width=widths[column], anchor="e")
        y_scroll = ttk.Scrollbar(
            table_frame, orient=tk.VERTICAL, command=self.hot_channel_tree.yview
        )
        x_scroll = ttk.Scrollbar(
            table_frame, orient=tk.HORIZONTAL, command=self.hot_channel_tree.xview
        )
        self.hot_channel_tree.configure(
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set
        )
        self.hot_channel_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.hot_channel_rendered_time = float("nan")
        self.last_hot_channel_render_wall = 0.0
        self.update_hot_channel()

    def close_hot_channel(self) -> None:
        if self.hot_channel_window is not None:
            self.hot_channel_window.destroy()
        self.hot_channel_window = None
        self.hot_channel_rendered_time = float("nan")
        self.last_hot_channel_render_wall = 0.0

    def update_hot_channel(self) -> None:
        if self.hot_channel_window is None or not self.hot_channel_window.winfo_exists():
            return
        render_now = time.perf_counter()
        if (
            self.hot_channel_rendered_time == self.hot_channel_result_time
            or render_now - self.last_hot_channel_render_wall
            < self.hot_channel_display_interval_s
        ):
            return
        self.last_hot_channel_render_wall = render_now
        if not np.isfinite(self.hot_channel_result_time):
            try:
                result = self.calculate_hot_channel()
                self.hot_channel_result = result
                self.hot_channel_error = None
            except (ValueError, ArithmeticError) as error:
                self.hot_channel_result = None
                self.hot_channel_error = str(error)
            self.hot_channel_result_time = self.state.t
            self.update_hot_channel_state(self.hot_channel_result)

        self.hot_channel_rendered_time = self.hot_channel_result_time
        result = self.hot_channel_result
        if result is None:
            detail = self.hot_channel_error or "state is outside the axial model domain"
            self.hot_channel_summary_var.set(
                f"Hot-channel calculation unavailable: {detail}. "
                "The lumped transient continues and the axial solver will retry periodically."
            )
            return
        fuel_index = result.peak_fuel_index
        clad_index = result.peak_clad_index
        warning = f" Warning: {result.phase_warning}" if result.phase_warning else ""
        dnbr_index = result.minimum_dnbr_index
        if dnbr_index is None:
            dnbr_text = "W-3 DNBR unavailable at the present conditions"
        else:
            dnbr_text = (
                f"minimum in-range W-3 DNBR {result.minimum_dnbr:.2f} at "
                f"z={result.z_m[dnbr_index]:.2f} m"
            )
        clad_history = self.state.hist.as_array("hot_clad")
        finite_clad = clad_history[np.isfinite(clad_history)]
        if finite_clad.size >= 2:
            change = float(finite_clad[-1] - finite_clad[-2])
            if change > 0.05:
                trend_text = "axial peak clad is rising"
            elif change < -0.05:
                trend_text = "axial peak clad is falling"
            else:
                trend_text = "axial peak clad is approximately steady"
        else:
            trend_text = "axial temperature trend is not yet established"
        self.hot_channel_summary_var.set(
            f"{result.z_m.size}-node representative channel. Peak fuel centre "
            f"{result.fuel_centerline_temperature_C[fuel_index]:.1f} C at "
            f"z={result.z_m[fuel_index]:.2f} m; peak clad surface "
            f"{result.clad_surface_temperature_C[clad_index]:.1f} C at "
            f"z={result.z_m[clad_index]:.2f} m; outlet coolant "
            f"{result.outlet_temperature_C:.1f} C; deposited channel power "
            f"{result.deposited_power_W / 1000.0:.1f} kW; {dnbr_text}; "
            f"{trend_text}.{warning}"
        )
        self.hot_line_fuel.set_data(result.z_m, result.fuel_centerline_temperature_C)
        self.hot_line_clad.set_data(result.z_m, result.clad_surface_temperature_C)
        self.hot_line_bulk.set_data(result.z_m, result.bulk_temperature_C)
        self.hot_line_sat.set_data(result.z_m, result.saturation_temperature_C)
        self.hot_channel_ax.relim()
        self.hot_channel_ax.autoscale_view()
        self.hot_coolant_ax.relim()
        self.hot_coolant_ax.autoscale_view()
        self.hot_line_heat_flux.set_data(result.z_m, result.surface_heat_flux_W_m2 / 1.0e6)
        self.hot_line_chf.set_data(result.z_m, result.critical_heat_flux_W_m2 / 1.0e6)
        self.hot_line_dnbr.set_data(result.z_m, result.dnbr)
        if self.state.trip:
            self.hot_flux_ax.set_ylim(0.0, self.hot_flux_reference_max_MW_m2)
            self.hot_dnbr_ax.set_ylim(0.0, self.hot_dnbr_reference_max)
        else:
            self.hot_flux_ax.relim()
            self.hot_flux_ax.autoscale_view()
            self.hot_dnbr_ax.relim()
            self.hot_dnbr_ax.autoscale_view()

        history = self.state.hist
        times = history.as_array("t")
        self.hot_trend_fuel.set_data(times, history.as_array("hot_fuel"))
        self.hot_trend_clad.set_data(times, history.as_array("hot_clad"))
        self.hot_trend_outlet.set_data(times, history.as_array("hot_outlet"))
        if times.size:
            xmax = max(40.0, float(times[-1]))
            xmin = max(0.0, xmax - 40.0)
            self.hot_trend_ax.set_xlim(xmin, xmax)
        self.hot_trend_ax.relim()
        self.hot_trend_ax.autoscale_view(scalex=False)
        self.hot_trend_coolant_ax.relim()
        self.hot_trend_coolant_ax.autoscale_view(scalex=False)
        self.hot_channel_canvas.draw_idle()

        for item in self.hot_channel_tree.get_children():
            self.hot_channel_tree.delete(item)
        for index, z in enumerate(result.z_m):
            quality = "--" if np.isnan(result.quality[index]) else f"{result.quality[index]:.4f}"
            chf = result.critical_heat_flux_W_m2[index] / 1.0e6
            chf_text = "--" if np.isnan(chf) else f"{chf:.3f}"
            dnbr = result.dnbr[index]
            dnbr_value = "--" if np.isnan(dnbr) else f"{dnbr:.3f}"
            self.hot_channel_tree.insert("", tk.END, values=(
                index + 1, f"{z:.3f}", f"{result.pressure_mpa[index]:.3f}",
                f"{result.enthalpy_kj_kg[index]:.2f}",
                f"{result.bulk_temperature_C[index]:.2f}",
                f"{result.clad_surface_temperature_C[index]:.2f}",
                f"{result.fuel_centerline_temperature_C[index]:.2f}", quality,
                f"{result.equilibrium_quality[index]:.4f}",
                f"{result.surface_heat_flux_W_m2[index] / 1.0e6:.3f}",
                chf_text, dnbr_value,
            ))

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
        self.hot_channel_result = None
        self.hot_channel_result_time = float("nan")
        self.hot_channel_error = None
        self.hot_channel_rendered_time = float("nan")
        self.last_hot_channel_render_wall = 0.0
        self.hot_flux_reference_max_MW_m2 = 6.0
        self.hot_dnbr_reference_max = 6.0
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
        self.hot_channel_coupling_var.set(True)
        self.state.autoECCS = True
        self.reset_event_timeline()
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
        if self.c.plant_type == "PWR" and self.state.pwr_trip_cause == "None":
            self.state.pwr_trip_cause = "Manual reactor trip"
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
        if not self.state.autoECCS:
            self.state.auto_eccs_demand = 0.0

    # --------------------------- Event timeline --------------------------

    def eccs_is_active(self) -> bool:
        s = self.state
        if self.c.plant_type == "BWR":
            commanded = any(
                self.control_vars[key].get() > 1.0
                for key in ("rcic", "hpci", "ads", "lpci", "core_spray")
            )
            flowing = (
                s.bwr_rcic_flow_kg_s+s.bwr_hpci_flow_kg_s
                +s.bwr_lpci_flow_kg_s+s.bwr_core_spray_flow_kg_s
            ) > 1.0
            return commanded or flowing or (
                bool(self.auto_eccs_var.get()) and s.M < 0.90
            )
        manual = any(
            self.control_vars[name].get() > 1.0
            for name in ("eccs", "pwr_hpsi", "pwr_lpsi", "pwr_recirculation")
            if name in self.control_vars
        )
        component_flow = s.pwr_total_injection_fraction_s > 1.0e-8
        hot_coupling = (
            self.c.plant_type != "BWR" and bool(self.hot_channel_coupling_var.get())
        )
        axial_dnbr_limit = (
            hot_coupling and np.isfinite(s.hot_min_dnbr) and s.hot_min_dnbr <= 1.0
        )
        axial_high_clad = (
            hot_coupling
            and np.isfinite(s.hot_peak_clad_C)
            and s.hot_peak_clad_C > 450.0
        )
        automatic = bool(self.auto_eccs_var.get()) and (
            s.auto_eccs_demand > 0.01
            or
            (s.P < 12.0 and s.M < 0.92)
            or s.Tcl > 450.0
            or axial_high_clad
            or axial_dnbr_limit
            or (s.P < 4.5 and s.M < 1.05)
            or (s.P < 2.0 and s.M < 1.10)
        )
        return manual or automatic or component_flow

    def current_event_state(self) -> Dict[str, object]:
        s = self.state
        hot_coupling = (
            self.c.plant_type != "BWR" and bool(self.hot_channel_coupling_var.get())
        )
        axial_high_clad = (
            hot_coupling
            and np.isfinite(s.hot_peak_clad_C)
            and s.hot_peak_clad_C > self.c.cladWarn
        )
        axial_dnbr_limit = (
            hot_coupling and np.isfinite(s.hot_min_dnbr) and s.hot_min_dnbr <= 1.0
        )
        return {
            "scenario": s.scenario_name,
            "trip": s.trip,
            "eccs": self.eccs_is_active(),
            "low_inventory": s.M < self.c.invLow,
            "high_clad": s.Tcl > self.c.cladWarn or axial_high_clad,
            "chf": s.chf_ratio >= 1.0 or axial_dnbr_limit,
            "regime": s.boiling_regime,
        }

    def record_event(
        self, category: str, message: str, *, key: Optional[str] = None,
        minimum_interval_s: float = 0.0,
    ) -> bool:
        event_key = key or f"{category}:{message}"
        previous_time = self.last_event_time.get(event_key, -1.0e30)
        if self.state.t - previous_time < minimum_interval_s:
            return False
        event = TimelineEvent(self.state.t, category, message)
        self.events.append(event)
        self.last_event_time[event_key] = self.state.t
        if hasattr(self, "event_tree"):
            self.event_tree.insert(
                "", tk.END,
                values=(f"{event.time_s:.1f} s", event.category, event.message),
            )
            children = self.event_tree.get_children()
            while len(children) > self.events.maxlen:
                self.event_tree.delete(children[0])
                children = self.event_tree.get_children()
            if children:
                self.event_tree.see(children[-1])
        return True

    def reset_event_timeline(self) -> None:
        self.events.clear()
        self.last_event_time.clear()
        if hasattr(self, "event_tree"):
            for item in self.event_tree.get_children():
                self.event_tree.delete(item)
        self.event_snapshot = self.current_event_state()
        self.record_event("SYSTEM", f"{self.state.scenario_name} initialized")

    def clear_event_timeline(self) -> None:
        self.events.clear()
        self.last_event_time.clear()
        if hasattr(self, "event_tree"):
            for item in self.event_tree.get_children():
                self.event_tree.delete(item)
        self.event_snapshot = self.current_event_state()

    def set_scenario(self, name: str) -> None:
        if name == self.state.scenario_name:
            return
        self.state.scenario_name = name
        self.record_event("SCENARIO", f"Selected {name}")
        self.event_snapshot["scenario"] = name

    def detect_timeline_events(self) -> None:
        current = self.current_event_state()
        previous = self.event_snapshot or current

        transitions = (
            ("trip", "PROTECTION", "Reactor trip actuated", "Reactor trip reset"),
            ("eccs", "SAFETY", "ECCS injection started", "ECCS injection stopped"),
            ("low_inventory", "INVENTORY", "Low primary inventory", "Primary inventory recovered"),
            ("high_clad", "THERMAL", "High cladding temperature", "Cladding temperature recovered"),
            ("chf", "BOILING", "Critical heat flux exceeded", "Heat flux returned below CHF"),
        )
        for state_key, category, active_message, clear_message in transitions:
            if current[state_key] != previous.get(state_key):
                self.record_event(
                    category,
                    active_message if current[state_key] else clear_message,
                    key=state_key,
                    minimum_interval_s=0.25,
                )

        if current["regime"] != previous.get("regime"):
            self.record_event(
                "BOILING", f"Heat-transfer regime: {current['regime']}",
                key="boiling_regime", minimum_interval_s=1.0,
            )
        self.event_snapshot = current

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
            "inventory_percent", "void_percent", "chf_ratio", "boiling_regime",
            "rho_pcm", "flow_percent", "trip", "auto_eccs", "auto_trip",
            "rod_percent", "trim_pcm", "boron_ppm", "pump_percent", "sg_percent",
            "break_percent", "eccs_percent", "afw_percent", "porv_percent", "spray_percent",
            "heater_percent", "rhr_percent",
            "hot_channel_coupled", "hot_peak_fuel_C", "hot_peak_clad_C",
            "hot_outlet_C", "hot_min_dnbr", "hot_dnbr_valid_nodes",
            "effective_eccs_percent", "break_out_inventory_fraction_s",
            "porv_out_inventory_fraction_s", "evaporation_out_inventory_fraction_s",
            "pwr_stored_mass_rate_fraction_s", "pwr_boundary_mass_rate_fraction_s",
            "pwr_mass_balance_residual_fraction_s", "pwr_stored_energy_rate_MW",
            "pwr_boundary_energy_rate_MW", "pwr_energy_balance_residual_MW",
            "pwr_projection_mass_correction_fraction_s",
            "pwr_projection_energy_correction_MW",
            "pwr_protection_demand", "pwr_active_protection_channels",
            "pwr_trip_cause", "pwr_rps_high_flux_timer_s",
            "pwr_rps_high_pressure_timer_s", "pwr_rps_low_inventory_timer_s",
            "pwr_rps_low_flow_timer_s", "pwr_rps_thermal_timer_s",
            "pwr_hpsi_flow_fraction_s", "pwr_lpsi_flow_fraction_s",
            "pwr_accumulator_flow_fraction_s", "pwr_recirculation_flow_fraction_s",
            "pwr_total_injection_fraction_s", "pwr_accumulator_inventory_percent",
            "pwr_hpsi_latched", "pwr_lpsi_latched", "pwr_recirculation_latched",
            "pwr_hpsi_head_margin_mpa", "pwr_lpsi_head_margin_mpa",
            "pwr_primary_flow_percent", "pwr_pump_head_m",
            "pwr_buoyancy_head_m", "pwr_loop_loss_head_m",
            "pwr_core_temperature_C", "pwr_hot_leg_temperature_C",
            "pwr_cold_leg_temperature_C", "pwr_pressurizer_liquid_inventory_percent",
            "pwr_pressurizer_steam_inventory_percent", "pwr_surge_flow_fraction_s",
            "pwr_secondary_mass_kg", "pwr_secondary_energy_MJ",
            "pwr_secondary_pressure_mpa", "pwr_secondary_steam_flow_kg_s",
            "pwr_secondary_feedwater_flow_kg_s", "pwr_secondary_heat_transfer_MW",
            "pwr_secondary_mass_residual_kg_s", "pwr_secondary_energy_residual_MW",
            "pwr_axial_power_zone_1", "pwr_axial_power_zone_2",
            "pwr_axial_power_zone_3", "pwr_axial_power_zone_4",
            "pwr_axial_void_zone_1", "pwr_axial_void_zone_2",
            "pwr_axial_void_zone_3", "pwr_axial_void_zone_4",
            "pwr_axial_peak_node", "pwr_axial_spatial_void_signal",
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
            f"{100.0 * s.M:.5g}", f"{100.0 * s.void_fraction:.5g}", f"{s.chf_ratio:.5g}",
            s.boiling_regime, f"{rho_total * 1.0e5:.5g}", f"{100.0 * flow_eff:.5g}",
            int(s.trip), int(self.auto_eccs_var.get()), int(self.auto_trip_var.get()),
            f"{self.control_vars['rod'].get():.5g}", f"{self.control_vars['trim'].get():.5g}",
            f"{self.control_vars['boron'].get():.5g}", f"{self.control_vars['pump'].get():.5g}",
            f"{self.control_vars['sg'].get():.5g}", f"{self.control_vars['break'].get():.5g}",
            f"{self.control_vars['eccs'].get():.5g}", f"{self.control_vars['afw'].get():.5g}",
            f"{self.control_vars['porv'].get():.5g}", f"{self.control_vars['spray'].get():.5g}",
            f"{self.control_vars['heater'].get():.5g}", f"{self.control_vars['rhr'].get():.5g}",
            int(self.hot_channel_coupling_var.get()),
            f"{s.hot_peak_fuel_C:.5g}", f"{s.hot_peak_clad_C:.5g}",
            f"{s.hot_outlet_C:.5g}", f"{s.hot_min_dnbr:.5g}",
            s.hot_dnbr_valid_nodes, f"{100.0 * s.effective_eccs_fraction:.5g}",
            f"{s.break_out_fraction_s:.5g}", f"{s.porv_out_fraction_s:.5g}",
            f"{s.evaporation_out_fraction_s:.5g}",
            f"{s.pwr_stored_mass_rate_fraction_s:.5g}",
            f"{s.pwr_boundary_mass_rate_fraction_s:.5g}",
            f"{s.pwr_mass_balance_residual_fraction_s:.5g}",
            f"{s.pwr_stored_energy_rate_MW:.5g}",
            f"{s.pwr_boundary_energy_rate_MW:.5g}",
            f"{s.pwr_energy_balance_residual_MW:.5g}",
            f"{s.pwr_projection_mass_correction_fraction_s:.5g}",
            f"{s.pwr_projection_energy_correction_MW:.5g}",
            int(s.pwr_protection_demand), s.pwr_active_protection_channels,
            s.pwr_trip_cause, f"{s.pwr_rps_high_flux_timer_s:.5g}",
            f"{s.pwr_rps_high_pressure_timer_s:.5g}",
            f"{s.pwr_rps_low_inventory_timer_s:.5g}",
            f"{s.pwr_rps_low_flow_timer_s:.5g}",
            f"{s.pwr_rps_thermal_timer_s:.5g}",
            f"{s.pwr_hpsi_flow_fraction_s:.5g}",
            f"{s.pwr_lpsi_flow_fraction_s:.5g}",
            f"{s.pwr_accumulator_flow_fraction_s:.5g}",
            f"{s.pwr_recirculation_flow_fraction_s:.5g}",
            f"{s.pwr_total_injection_fraction_s:.5g}",
            f"{100.0*s.pwr_accumulator_inventory_fraction:.5g}",
            int(s.pwr_hpsi_latched), int(s.pwr_lpsi_latched),
            int(s.pwr_recirculation_latched),
            f"{s.pwr_hpsi_head_margin_mpa:.5g}",
            f"{s.pwr_lpsi_head_margin_mpa:.5g}",
            f"{100.0*s.pwr_primary_flow_fraction:.5g}",
            f"{s.pwr_pump_head_m:.5g}", f"{s.pwr_buoyancy_head_m:.5g}",
            f"{s.pwr_loop_loss_head_m:.5g}", f"{s.pwr_core_temperature_C:.5g}",
            f"{s.pwr_hot_leg_temperature_C:.5g}", f"{s.pwr_cold_leg_temperature_C:.5g}",
            f"{100.0*s.pwr_pressurizer_liquid_inventory_fraction:.5g}",
            f"{100.0*s.pwr_pressurizer_steam_inventory_fraction:.5g}",
            f"{s.pwr_surge_flow_fraction_s:.5g}", f"{s.pwr_secondary_mass_kg:.5g}",
            f"{s.pwr_secondary_energy_MJ:.5g}", f"{s.pwr_secondary_pressure_mpa:.5g}",
            f"{s.pwr_secondary_steam_flow_kg_s:.5g}",
            f"{s.pwr_secondary_feedwater_flow_kg_s:.5g}",
            f"{s.pwr_secondary_heat_transfer_MW:.5g}",
            f"{s.pwr_secondary_mass_residual_kg_s:.5g}",
            f"{s.pwr_secondary_energy_residual_MW:.5g}",
            *(f"{value:.5g}" for value in s.pwr_axial_power_fraction),
            *(f"{value:.5g}" for value in s.pwr_axial_void_fraction),
            s.pwr_axial_peak_node, f"{s.pwr_axial_spatial_void_signal:.5g}",
        ]
        self.csv_writer.writerow(row)
        if int(s.t * 10) % 20 == 0:
            self.csv_file.flush()

    # ----------------------------- Scenarios ------------------------------

    def scenario_normal(self) -> None:
        self.set_scenario("Normal operation")
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
        self.state.auto_eccs_demand = 0.0
        self.refresh_all(force=False)

    def scenario_sbloc(self) -> None:
        self.set_scenario("Small-break LOCA")
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
        self.set_scenario("Large-break LOCA")
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
        self.set_scenario("Loss of flow accident")
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
        self.set_scenario("Loss of heat sink")
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
        self.set_scenario("Station blackout")
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
                refresh_now = time.perf_counter()
                if (
                    refresh_now - self.last_display_refresh_wall
                    >= self.display_refresh_interval_s
                ):
                    self.refresh_all(force=False)
                    self.last_display_refresh_wall = refresh_now
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

    def saturation_temperature(self, pressure_mpa: float) -> float:
        return self.steam_tables.saturation_temperature(pressure_mpa)

    def saturation_pressure(self, temperature_C: float) -> float:
        return self.steam_tables.saturation_pressure(temperature_C)

    def boiling_heat_transfer(
        self, flow_eff: float, coverage: float
    ) -> Tuple[float, float, str, float]:
        """Return clad-coolant conductance, boiling demand, regime and CHF ratio.

        The CHF criterion is a transparent teaching surrogate: available CHF
        rises with pressure, forced flow, and wetted-core fraction. Crossing it
        moves the surface to transition/film boiling instead of allowing the
        former unlimited two-phase heat-transfer enhancement.
        """
        c, s = self.c, self.state
        tsat = self.saturation_temperature(s.P)
        wall_superheat = max(0.0, s.Tcl - tsat)
        base = c.Kcc_nom * coverage * (0.20 + 0.80 * flow_eff)

        if wall_superheat <= 3.0:
            multiplier, regime = 1.0, "single-phase"
        elif wall_superheat <= 25.0:
            multiplier = 1.0 + 1.8 * (wall_superheat - 3.0) / 22.0
            regime = "nucleate boiling"
        else:
            multiplier, regime = 2.8, "nucleate boiling"

        q_candidate = max(0.0, base * multiplier * (s.Tcl - s.Tc))
        pressure_factor = self.clamp(0.55 + 0.035 * s.P, 0.55, 1.15)
        chf_limit = 4300.0 * coverage * pressure_factor * (0.30 + 0.70 * math.sqrt(max(flow_eff, 0.0)))
        chf_ratio = q_candidate / max(chf_limit, 1.0)

        if chf_ratio > 1.0:
            # Smooth degradation avoids a discontinuous ODE while preserving
            # the key physical lesson: post-CHF heat transfer is much poorer.
            film_fraction = self.clamp((chf_ratio - 1.0) / 0.6, 0.0, 1.0)
            multiplier *= 1.0 - 0.86 * film_fraction
            regime = "transition boiling" if film_fraction < 0.95 else "film boiling"

        conductance = max(1.5, base * multiplier)
        boiling_demand = max(0.0, conductance * (s.Tcl - s.Tc)) if s.Tc >= tsat - 8.0 else 0.0
        return conductance, boiling_demand, regime, chf_ratio

    def step_model(self, dt: float) -> None:
        """Advance the GUI-independent physics engine by one RK4 step."""
        s = self.state
        self.update_auto_eccs_demand()
        model_metadata = getattr(self.physics, "metadata", None)
        hot_channel_capable = (
            True if model_metadata is None else model_metadata.hot_channel_capable
        )
        if not hot_channel_capable:
            hot_result = None
            self.hot_channel_result = None
            self.hot_channel_error = "BWR axial-channel diagnostic is unavailable"
        else:
            cache_age = s.t - self.hot_channel_result_time
            if (
                not np.isfinite(cache_age)
                or cache_age >= getattr(self, "hot_channel_update_interval_s", 0.25) - 1.0e-12
            ):
                try:
                    hot_result = self.calculate_hot_channel()
                    self.hot_channel_error = None
                except (ValueError, ArithmeticError) as error:
                    hot_result = None
                    self.hot_channel_error = str(error)
                self.hot_channel_result = hot_result
                self.hot_channel_result_time = s.t
            else:
                hot_result = self.hot_channel_result
        self.update_hot_channel_state(hot_result)

        hot_coupling = (
            self.c.plant_type != "BWR" and bool(self.hot_channel_coupling_var.get())
        )
        if self.c.plant_type == "BWR":
            automatic_trip_demand, _ = self.physics.evaluate_protection(s,dt)
            if bool(self.auto_trip_var.get()) and automatic_trip_demand:
                s.trip = True
        else:
            automatic_trip_demand, _ = self.physics.evaluate_protection(
                s, dt, self.control_vars["pump"].get(),
                thermal_limit_enabled=hot_coupling,
            )
            if bool(self.auto_trip_var.get()) and automatic_trip_demand:
                s.trip = True

        rod_pct = self.control_vars["rod"].get()
        trim_pcm = self.control_vars["trim"].get()
        if s.trip:
            rod_pct = 100.0
            trim_pcm = min(trim_pcm, 0.0)
            if self.c.plant_type == "PWR":
                s.pwr_effective_rod_pct = rod_pct
                s.pwr_normal_power_target = s.n
                s.pwr_normal_power_damping_pcm = 0.0
        elif self.c.plant_type == "PWR" and (
            s.scenario_name == "Normal operation"
            and self.control_vars["break"].get() <= 0.0
            and (rod_pct > 1.0e-9 or s.pwr_effective_rod_pct > 1.0e-9)
        ):
            alpha = 1.0 - math.exp(-dt / self.c.pwr_normal_rod_maneuver_tau_s)
            s.pwr_effective_rod_pct += alpha * (rod_pct - s.pwr_effective_rod_pct)
            rod_pct = s.pwr_effective_rod_pct
            s.pwr_normal_power_target = self.clamp(
                1.0 - self.c.pwr_normal_power_target_slope * rod_pct / 100.0,
                0.05, 1.20,
            )
            s.pwr_normal_power_damping_pcm = self.clamp(
                self.c.pwr_normal_power_damping_gain_pcm
                * (s.pwr_normal_power_target - s.n),
                -500.0, 500.0,
            )
            trim_pcm += s.pwr_normal_power_damping_pcm
        elif self.c.plant_type == "PWR":
            s.pwr_effective_rod_pct = rod_pct
            s.pwr_normal_power_target = s.n
            s.pwr_normal_power_damping_pcm = 0.0

        if self.c.plant_type == "BWR":
            controls = BWRControlInputs(
                rod_pct=rod_pct, trim_pcm=trim_pcm,
                recirc_pct=self.control_vars["recirc"].get(),
                feedwater_pct=self.control_vars["feedwater"].get(),
                main_steam_pct=self.control_vars["main_steam"].get(),
                srv_pct=self.control_vars["srv"].get(),
                msiv_pct=self.control_vars["msiv"].get(),
                bypass_pct=self.control_vars["bypass"].get(),
                rcic_pct=self.control_vars["rcic"].get(),
                hpci_pct=self.control_vars["hpci"].get(),
                ads_pct=self.control_vars["ads"].get(),
                lpci_pct=self.control_vars["lpci"].get(),
                core_spray_pct=self.control_vars["core_spray"].get(),
                shutdown_cooling_pct=self.control_vars["shutdown_cooling"].get(),
                bwr_break_pct=self.control_vars["bwr_break"].get(),
                auto_bwr_safety=bool(self.auto_eccs_var.get()),
                rcic_available=self.bwr_system_availability["rcic"],
                hpci_available=self.bwr_system_availability["hpci"],
                ads_available=self.bwr_system_availability["ads"],
                lpci_available=self.bwr_system_availability["lpci"],
                core_spray_available=self.bwr_system_availability["core_spray"],
                critical_power_ratio=s.hot_min_dnbr,
                critical_power_valid_nodes=s.hot_dnbr_valid_nodes,
            )
        else:
            pwr_mode = getattr(self, "pwr_control_mode", "simplified")
            controls = PWRControlInputs(
                rod_pct=rod_pct, trim_pcm=trim_pcm,
                boron_ppm=self.control_vars["boron"].get(),
                pump_pct=self.control_vars["pump"].get(),
                sg_pct=self.control_vars["sg"].get(),
                break_pct=self.control_vars["break"].get(),
                eccs_pct=(
                    self.control_vars["eccs"].get()
                    if pwr_mode == "simplified" else 0.0
                ),
                hpsi_pct=(
                    self.control_vars["pwr_hpsi"].get()
                    if pwr_mode == "advanced" and "pwr_hpsi" in self.control_vars
                    else 0.0
                ),
                lpsi_pct=(
                    self.control_vars["pwr_lpsi"].get()
                    if pwr_mode == "advanced" and "pwr_lpsi" in self.control_vars
                    else 0.0
                ),
                recirculation_pct=(
                    self.control_vars["pwr_recirculation"].get()
                    if pwr_mode == "advanced" and "pwr_recirculation" in self.control_vars
                    else 0.0
                ),
                hpsi_available=getattr(
                    self, "pwr_system_availability", {}
                ).get("hpsi", True),
                lpsi_available=getattr(
                    self, "pwr_system_availability", {}
                ).get("lpsi", True),
                accumulator_available=getattr(
                    self, "pwr_system_availability", {}
                ).get("accumulator", True),
                recirculation_available=getattr(
                    self, "pwr_system_availability", {}
                ).get("recirculation", True),
                afw_pct=self.control_vars["afw"].get(),
                porv_pct=self.control_vars["porv"].get(),
                spray_pct=self.control_vars["spray"].get(),
                heater_pct=self.control_vars["heater"].get(),
                rhr_pct=self.control_vars["rhr"].get(),
                auto_eccs=bool(self.auto_eccs_var.get()),
                auto_eccs_demand=s.auto_eccs_demand,
                hot_channel_coupling=hot_coupling,
                hot_channel_peak_clad_C=s.hot_peak_clad_C,
                hot_channel_min_dnbr=s.hot_min_dnbr,
            )
        diagnostics = self.physics.step(s, controls, dt)
        s.autoECCS = (
            controls.auto_bwr_safety if self.c.plant_type == "BWR" else controls.auto_eccs
        )
        s.effective_eccs_fraction = diagnostics.eccs_fraction
        s.break_out_fraction_s = diagnostics.break_out
        s.porv_out_fraction_s = diagnostics.porv_out
        s.evaporation_out_fraction_s = diagnostics.evaporation_out
        if self.c.plant_type == "PWR":
            s.pwr_stored_mass_rate_fraction_s = diagnostics.pwr_stored_mass_rate_fraction_s
            s.pwr_boundary_mass_rate_fraction_s = diagnostics.pwr_boundary_mass_rate_fraction_s
            s.pwr_mass_balance_residual_fraction_s = diagnostics.pwr_mass_balance_residual_fraction_s
            s.pwr_stored_energy_rate_MW = diagnostics.pwr_stored_energy_rate_MW
            s.pwr_boundary_energy_rate_MW = diagnostics.pwr_boundary_energy_rate_MW
            s.pwr_energy_balance_residual_MW = diagnostics.pwr_energy_balance_residual_MW
            s.pwr_projection_mass_correction_fraction_s = diagnostics.pwr_projection_mass_correction_fraction_s
            s.pwr_projection_energy_correction_MW = diagnostics.pwr_projection_energy_correction_MW
            s.pwr_hpsi_flow_fraction_s = diagnostics.pwr_hpsi_in_fraction_s
            s.pwr_lpsi_flow_fraction_s = diagnostics.pwr_lpsi_in_fraction_s
            s.pwr_accumulator_flow_fraction_s = diagnostics.pwr_accumulator_in_fraction_s
            s.pwr_recirculation_flow_fraction_s = diagnostics.pwr_recirculation_in_fraction_s
            s.pwr_total_injection_fraction_s = diagnostics.pwr_total_injection_fraction_s
            s.pwr_hpsi_head_margin_mpa = diagnostics.pwr_hpsi_head_margin_mpa
            s.pwr_lpsi_head_margin_mpa = diagnostics.pwr_lpsi_head_margin_mpa

        # Discrete controls and observability are applied once after all four
        # RK stages; intermediate stages never mutate Tk variables or history.
        if s.trip:
            self.set_slider("rod", 100.0)
            self.set_slider("trim", trim_pcm)
        self.detect_timeline_events()
        self.append_history(
            diagnostics.decay_fraction,
            diagnostics.rho_total,
            diagnostics.flow_effective,
        )

    def _step_model_euler_reference(self, dt: float) -> None:
        """Retained temporarily as an equation-by-equation migration reference."""
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

        Kcc, boiling_demand, boiling_regime, chf_ratio = self.boiling_heat_transfer(
            flow_eff, coverage
        )
        s.boiling_regime = boiling_regime
        s.chf_ratio = chf_ratio

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

        # Break flow, relief/PORV flow, and boiling inventory loss.  Every mass
        # flow below also transports enthalpy in the coolant-energy balance.
        brk = max(0.0, break_pct / 100.0)
        porv = max(0.0, porv_pct / 100.0)
        break_out = c.break_coeff * brk * math.sqrt(max(s.P - 0.10, 0.0))
        porv_out = c.porv_coeff * porv * math.sqrt(max(s.P - 0.10, 0.0))
        tsat = self.saturation_temperature(s.P)
        boiling_fraction = self.clamp((s.Tc - (tsat - 5.0)) / 15.0, 0.0, 1.0)
        evap_power = boiling_fraction * max(0.0, min(boiling_demand, Qcc - 0.5 * Qsg))
        evap_loss = evap_power / (c.Ccool * c.latent_heat_equiv_C)
        eccs_in = c.eccs_coeff * eccs * self.pressure_eccs_factor(s.P)

        # Limit boundary flows at the declared classroom inventory bounds. The
        # same effective flows are used in both mass and energy equations.
        total_out = break_out + porv_out + evap_loss
        if s.M + dt * (eccs_in - total_out) < 0.05:
            permitted_out = max(0.0, eccs_in + (s.M - 0.05) / dt)
            out_scale = permitted_out / max(total_out, 1.0e-12)
            break_out *= out_scale
            porv_out *= out_scale
            evap_loss *= out_scale
            total_out = permitted_out
        elif s.M + dt * (eccs_in - total_out) > 1.20:
            eccs_in = max(0.0, total_out + (1.20 - s.M) / dt)

        spray = max(0.0, spray_pct / 100.0)

        # RHR/shutdown cooling is intentionally made mostly useful at low pressure.
        rhr = max(0.0, rhr_pct / 100.0)
        rhr_available = self.clamp((3.5 - s.P) / 2.5, 0.0, 1.0)
        Qrhr = 1800.0 * rhr * rhr_available * max(0.0, (s.Tc - 60.0) / 280.0)

        # Fuel and cladding thermal ODEs.
        dTf = (Qgen - Qfc) / c.Cfuel
        dTcl = (Qfc - Qcc) / c.Cclad
        s.Tf += dt * dTf
        s.Tcl += dt * dTcl
        s.Tf = self.clamp(s.Tf, 20.0, 2800.0)
        s.Tcl = self.clamp(s.Tcl, 20.0, 2200.0)

        # Conservative primary coolant balance. Ucool is measured relative to
        # a fixed reference; injection and discharge carry their own enthalpy.
        # Flashing discharge additionally carries latent heat.
        liquid_h = c.Ccool * max(0.0, s.Tc - c.coolant_energy_reference_C)
        injection_h = c.Ccool * max(
            0.0, c.eccs_temp_C - c.coolant_energy_reference_C
        )
        flash_quality = self.clamp(s.void_fraction + boiling_fraction * 0.20, 0.0, 1.0)
        discharge_h = liquid_h + c.Ccool * c.latent_heat_equiv_C * flash_quality
        steam_h = liquid_h + c.Ccool * c.latent_heat_equiv_C
        coolant_power = Qcc - Qsg - Qrhr
        dUcool = (
            coolant_power
            + eccs_in * injection_h
            - (break_out + porv_out) * discharge_h
            - evap_loss * steam_h
        )
        s.Ucool = max(0.0, s.Ucool + dt * dUcool)
        s.M += dt * (eccs_in - break_out - porv_out - evap_loss)
        s.Tc = c.coolant_energy_reference_C + s.Ucool / (c.Ccool * s.M)
        s.Tc = self.clamp(s.Tc, 20.0, 650.0)
        # Keep stored energy exactly synchronized if a classroom safety bound
        # was reached, rather than silently breaking the next-step balance.
        s.Ucool = c.Ccool * s.M * (s.Tc - c.coolant_energy_reference_C)

        equilibrium_void = boiling_fraction * self.clamp(
            evap_power / max(Qcc, 1.0), 0.0, 0.85
        )
        s.void_fraction += dt * (equilibrium_void - s.void_fraction) / 2.5
        s.void_fraction = self.clamp(s.void_fraction, 0.0, 0.95)

        # Saturated pressurizer state. Primary thermal expansion and inventory
        # surge alter pressurizer temperature; pressure is then obtained from
        # the same saturation curve used by the boiling model.
        prz_target = 344.8 + 0.55 * (s.Tc - c.TrefCool) + 45.0 * (s.M - 1.0)
        dTprz = (prz_target - s.Tprz) / c.pressurizer_tau
        dTprz -= 18.0 * brk * math.sqrt(max(s.P - 0.10, 0.0))
        dTprz -= 28.0 * porv * math.sqrt(max(s.P - 0.10, 0.0))
        dTprz -= 13.0 * spray
        dTprz += 7.0 * max(0.0, heat_pct / 100.0)
        dTprz += 12.0 * eccs_in
        s.Tprz = self.clamp(s.Tprz + dt * dTprz, 99.6, 355.0)
        s.P = self.saturation_pressure(s.Tprz)

        s.t += dt
        self.detect_timeline_events()
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
        hist.void.append(100.0 * s.void_fraction)
        hist.chf.append(s.chf_ratio)
        hist.hot_fuel.append(s.hot_peak_fuel_C)
        hist.hot_clad.append(s.hot_peak_clad_C)
        hist.hot_outlet.append(s.hot_outlet_C)
        hist.hot_dnbr.append(s.hot_min_dnbr)
        hist.pwr_mass_residual.append(s.pwr_mass_balance_residual_fraction_s)
        hist.pwr_energy_residual.append(s.pwr_energy_balance_residual_MW)
        hist.pwr_projection_mass.append(s.pwr_projection_mass_correction_fraction_s)
        hist.pwr_projection_energy.append(s.pwr_projection_energy_correction_MW)
        hist.pwr_primary_flow.append(100.0 * s.pwr_primary_flow_fraction)
        hist.pwr_core_temp.append(s.pwr_core_temperature_C)
        hist.pwr_hot_leg_temp.append(s.pwr_hot_leg_temperature_C)
        hist.pwr_cold_leg_temp.append(s.pwr_cold_leg_temperature_C)
        hist.pwr_prz_liquid_inventory.append(100.0 * s.pwr_pressurizer_liquid_inventory_fraction)
        hist.pwr_prz_steam_inventory.append(100.0 * s.pwr_pressurizer_steam_inventory_fraction)
        hist.pwr_secondary_mass.append(s.pwr_secondary_mass_kg)
        hist.pwr_secondary_pressure.append(s.pwr_secondary_pressure_mpa)
        for index, value in enumerate(s.pwr_axial_power_fraction, start=1):
            getattr(hist, f"pwr_axial_power_{index}").append(100.0 * value)
        for index, value in enumerate(s.pwr_axial_void_fraction, start=1):
            getattr(hist, f"pwr_axial_void_{index}").append(100.0 * value)

        self.write_csv_row(indicated_power, decay_frac_now, rho_total, flow_eff)

    # ----------------------------- Screen update --------------------------

    def refresh_all(self, force: bool) -> None:
        if force or not self.freeze_chart:
            self.update_plots()
        self.update_readouts()
        self.update_hot_channel()

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
            for ax in (self.ax_power, self.ax_decay, self.ax_temp, self.ax_press):
                ax.set_xlim(0.0, visible_window_s)
            self.ax_decay.set_ylim(0.0, 8.0)
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
        y_max_power = max(120.0, 1.15 * self.nanmax(np.concatenate([pow_y, np.array([110.0])]), 120.0))
        self.ax_power.set_xlim(xmin, xmax)
        self.ax_power.set_ylim(0.0, y_max_power)
        y_max_decay = max(
            8.0,
            1.15 * self.nanmax(np.concatenate([dec_y, np.array([7.0])]), 8.0),
        )
        self.ax_decay.set_xlim(xmin, xmax)
        self.ax_decay.set_ylim(0.0, y_max_decay)

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

        eccs_on = self.eccs_is_active()
        self.set_lamp("REACTOR TRIP", s.trip)
        self.set_lamp("ECCS ACTIVE", eccs_on)
        self.set_lamp("LOW INVENTORY", s.M < self.c.invLow)
        axial_high_clad = (
            bool(self.hot_channel_coupling_var.get())
            and np.isfinite(s.hot_peak_clad_C)
            and s.hot_peak_clad_C > self.c.cladWarn
        )
        self.set_lamp("HIGH CLAD TEMP", s.Tcl > self.c.cladWarn or axial_high_clad)

        if s.Tcl > self.c.cladTrip or (
            axial_high_clad and s.hot_peak_clad_C > self.c.cladTrip
        ):
            alarm = "SEVERE: cladding temperature above teaching limit. Discuss core uncovery and emergency cooling."
        elif axial_high_clad:
            alarm = "WARNING: representative hot-channel cladding exceeds the teaching warning limit."
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
        boiling_text = (
            f" | Heat transfer: {s.boiling_regime}, void {100.0 * s.void_fraction:.0f}%, "
            f"CHF ratio {s.chf_ratio:.2f}"
        )
        if np.isfinite(s.hot_min_dnbr):
            boiling_text += f", axial MDNBR {s.hot_min_dnbr:.2f}"
        self.status_var.set(
            f"t = {s.t:.1f} s | Scenario: {s.scenario_name}{demo_text}{log_text}"
            f"{boiling_text} | {alarm}"
        )

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
        duration_ms=3000,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
