#!/usr/bin/env python3
"""
Interactive Core Loading and Thorium Fuel-Cycle Teaching Simulator
==================================================================

Purpose
-------
Undergraduate teaching application for exploring how assembly placement
changes a simplified 2-D neutron flux, assembly power, burnup, leakage and
thorium conversion indicators.

This is NOT a reactor-design, licensing, safety-analysis, depletion, or
criticality-safety code. The model deliberately uses reduced-order,
classroom-scaled physics for rapid visual feedback.

Features
--------
* 11 x 11 PWR-like core lattice with a rounded active-core mask
* Click-to-place fuel assemblies from an assembly palette
* Fresh, once-burned, twice-burned, burnable absorber, thorium blanket,
  U-233/thorium seed and reflector assembly types
* Coupled fast/thermal two-group diffusion eigenvalue iteration
* Flux, power, burnup and thorium breeding heat maps
* Approximate k-effective, radial peaking factor and leakage indicator
* Spatial U-235, Pu-239, absorber, Th-232/Pa-233/U-233 cycle evolution
* Assembly fuel/moderator feedback and equilibrium full-power xenon
* Pm-149/Sm-149 poisoning and symmetric 2-D control-bank insertion
* Persistent assembly IDs, named core positions and multi-cycle refueling history
* Used-fuel storage, outage decay, state-preserving shuffling and JSON save/load
* Built-in conventional PWR and thorium seed-blanket presets
* CSV export of the current core state
* Centre-to-edge ratio, directional tilts and flux-centroid diagnostics
* Top, rotatable interpolated 3-D and split result displays

Requirements
------------
    Python 3.9+
    numpy
    matplotlib

Optional:
    pillow   (optional, for smooth image scaling)

Run
---
    python main.py
"""

from __future__ import annotations

import csv
import copy
import json
import math
import tkinter as tk
import webbrowser
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

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
    pass

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


PROJECT_NAME = "Open Nuclear Engineering Teaching Suite"
MODULE_NAME = "Interactive Core Loading and Thorium Fuel-Cycle Explorer"

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

GRID_SIZE = 11
CELL_SIZE = 48
CORE_RADIUS = 5.15
ASSEMBLY_PITCH_CM = 21.5
BORON_ABSORPTION_PER_PPM = 9.0e-6
MAX_BORON_PPM = 2000.0
# A single calibration factor applied to the teaching cross-section dataset.
# Unlike the previous display transform, k remains the eigenvalue of A phi=F phi/k.
FISSION_DATA_SCALE = 1.176


@dataclass(frozen=True)
class AssemblyType:
    key: str
    short: str
    name: str
    color: str
    fissile: float
    absorption: float
    diffusion: float
    fertile_th: float
    fertile_u8: float
    burnable_poison: float
    initial_burnup: float
    notes: str


@dataclass
class AssemblyRecord:
    assembly_id: str
    assembly_type: str
    status: str = "in_core"
    position: Optional[str] = None
    cycles_completed: int = 0
    state: Dict[str, float] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)


ASSEMBLY_TYPES: Dict[str, AssemblyType] = {
    "EMPTY": AssemblyType(
        "EMPTY", "", "Empty position", "#12161c",
        fissile=0.0, absorption=0.0, diffusion=0.0,
        fertile_th=0.0, fertile_u8=0.0, burnable_poison=0.0,
        initial_burnup=0.0,
        notes="No active assembly; treated as leakage boundary.",
    ),
    "FRESH": AssemblyType(
        "FRESH", "F", "Fresh LEU fuel", "#e85d5d",
        fissile=1.00, absorption=0.27, diffusion=1.00,
        fertile_th=0.0, fertile_u8=0.90, burnable_poison=0.0,
        initial_burnup=0.0,
        notes="High reactivity and power potential.",
    ),
    "ONCE": AssemblyType(
        "ONCE", "1", "Once-burned fuel", "#f0a34a",
        fissile=0.78, absorption=0.26, diffusion=1.00,
        fertile_th=0.0, fertile_u8=0.82, burnable_poison=0.0,
        initial_burnup=18.0,
        notes="Moderate reactivity; useful for power flattening.",
    ),
    "TWICE": AssemblyType(
        "TWICE", "2", "Twice-burned fuel", "#d8c44f",
        fissile=0.58, absorption=0.25, diffusion=1.00,
        fertile_th=0.0, fertile_u8=0.75, burnable_poison=0.0,
        initial_burnup=36.0,
        notes="Lower reactivity; often placed in higher-importance regions.",
    ),
    "BA": AssemblyType(
        "BA", "B", "Fresh fuel + burnable absorber", "#9b6ad6",
        fissile=0.94, absorption=0.34, diffusion=0.96,
        fertile_th=0.0, fertile_u8=0.88, burnable_poison=0.20,
        initial_burnup=0.0,
        notes="Suppresses local power early in cycle.",
    ),
    "TH": AssemblyType(
        "TH", "T", "Thorium blanket", "#4ea8a1",
        fissile=0.10, absorption=0.23, diffusion=1.05,
        fertile_th=1.00, fertile_u8=0.0, burnable_poison=0.0,
        initial_burnup=0.0,
        notes="Fertile Th-232 region; breeds U-233 in the teaching model.",
    ),
    "SEED": AssemblyType(
        "SEED", "S", "U-233 / thorium seed", "#4b82d0",
        fissile=1.10, absorption=0.25, diffusion=1.03,
        fertile_th=0.55, fertile_u8=0.0, burnable_poison=0.0,
        initial_burnup=0.0,
        notes="Fissile driver containing thorium fertile material.",
    ),
    "REFL": AssemblyType(
        "REFL", "R", "Reflector / low-power blanket", "#7a8796",
        fissile=0.02, absorption=0.12, diffusion=1.25,
        fertile_th=0.15, fertile_u8=0.0, burnable_poison=0.0,
        initial_burnup=0.0,
        notes="Returns neutrons toward the active core; little local power.",
    ),
}


class CoreModel:
    """Two-group 2-D teaching model with persistent fuel-assembly records."""

    ASSEMBLY_STATE_FIELDS = (
        "burnup", "u235_inventory", "pu239_inventory", "u233_inventory",
        "pa233_inventory", "poison_inventory", "iodine135_inventory",
        "xenon135_inventory", "promethium149_inventory",
        "samarium149_inventory", "fuel_temperature",
        "moderator_temperature", "moderator_density",
    )

    def __init__(self) -> None:
        self.mask = self._build_mask()
        self.control_bank_mask = self._build_control_bank_mask()
        self.layout = np.full((GRID_SIZE, GRID_SIZE), "EMPTY", dtype=object)
        self.assembly_ids = np.full((GRID_SIZE, GRID_SIZE), "", dtype=object)
        self.assembly_registry: Dict[str, AssemblyRecord] = {}
        self.next_assembly_number = 1
        self.cycle_number = 1
        self.total_full_power_days = 0.0
        self.total_outage_days = 0.0
        self.cycle_completion_recorded = False
        self.burnup = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.u233_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.pa233_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.u235_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.pu239_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.poison_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.iodine135_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.xenon135_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.promethium149_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.samarium149_inventory = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.fuel_temperature = np.full((GRID_SIZE, GRID_SIZE), 600.0, dtype=float)
        self.moderator_temperature = np.full((GRID_SIZE, GRID_SIZE), 560.0, dtype=float)
        self.moderator_density = np.ones((GRID_SIZE, GRID_SIZE), dtype=float)
        self.control_fraction = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.fast_flux = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.thermal_flux = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.flux = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.power = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.power_index = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.breeding = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
        self.k_eff = 0.0
        self.operating_k_eff = 0.0
        self.required_boron_ppm = 0.0
        self.radial_peaking = 0.0
        self.leakage_index = 0.0
        self.conversion_ratio = 0.0
        self.centre_edge_ratio = 0.0
        self.north_south_tilt = 0.0
        self.east_west_tilt = 0.0
        self.flux_centroid_offset = 0.0
        self.shutdown_k_eff = 0.0
        self.shutdown_margin_pcm = 0.0
        self.control_worth_pcm = 0.0
        self.cycle_days = 0.0
        self.load_conventional_pwr()

    @staticmethod
    def _build_mask() -> np.ndarray:
        centre = (GRID_SIZE - 1) / 2.0
        mask = np.zeros((GRID_SIZE, GRID_SIZE), dtype=bool)
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                distance = math.hypot(r - centre, c - centre)
                mask[r, c] = distance <= CORE_RADIUS
        return mask

    @staticmethod
    def _build_control_bank_mask() -> np.ndarray:
        mask = np.zeros((GRID_SIZE, GRID_SIZE), dtype=bool)
        centre = (GRID_SIZE - 1) / 2.0
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if math.hypot(r - centre, c - centre) <= 4.3 and (r + c) % 2 == 0:
                    mask[r, c] = True
        return mask

    def reset_arrays(self) -> None:
        self.flux.fill(0.0)
        self.fast_flux.fill(0.0)
        self.thermal_flux.fill(0.0)
        self.power.fill(0.0)
        self.power_index.fill(0.0)
        self.breeding.fill(0.0)
        self.k_eff = 0.0
        self.operating_k_eff = 0.0
        self.required_boron_ppm = 0.0
        self.radial_peaking = 0.0
        self.leakage_index = 0.0
        self.conversion_ratio = 0.0
        self.centre_edge_ratio = 0.0
        self.north_south_tilt = 0.0
        self.east_west_tilt = 0.0
        self.flux_centroid_offset = 0.0
        self.shutdown_k_eff = 0.0
        self.shutdown_margin_pcm = 0.0
        self.control_worth_pcm = 0.0

    @staticmethod
    def position_id(row: int, col: int) -> str:
        return f"R{row + 1:02d}-C{col + 1:02d}"

    def _new_assembly_id(self, key: str) -> str:
        prefix = {
            "FRESH": "FA", "ONCE": "OB", "TWICE": "TB", "BA": "BA",
            "TH": "TH", "SEED": "SE", "REFL": "RF",
        }.get(key, "AS")
        assembly_id = f"{prefix}-{self.next_assembly_number:04d}"
        self.next_assembly_number += 1
        return assembly_id

    def _initialize_cell_state(self, row: int, col: int, key: str) -> None:
        if not self.mask[row, col]:
            return
        self.layout[row, col] = key
        self.burnup[row, col] = ASSEMBLY_TYPES[key].initial_burnup
        self.u233_inventory[row, col] = 0.0
        self.pa233_inventory[row, col] = 0.0
        initial_u235 = {
            "FRESH": 1.00, "ONCE": 0.76, "TWICE": 0.55, "BA": 0.96,
            "TH": 0.02, "SEED": 0.05, "REFL": 0.0, "EMPTY": 0.0,
        }[key]
        initial_pu239 = {
            "FRESH": 0.00, "ONCE": 0.11, "TWICE": 0.17, "BA": 0.00,
            "TH": 0.00, "SEED": 0.00, "REFL": 0.0, "EMPTY": 0.0,
        }[key]
        self.u235_inventory[row, col] = initial_u235
        self.pu239_inventory[row, col] = initial_pu239
        self.poison_inventory[row, col] = ASSEMBLY_TYPES[key].burnable_poison
        self.iodine135_inventory[row, col] = 0.0
        self.xenon135_inventory[row, col] = 0.0
        self.promethium149_inventory[row, col] = 0.0
        self.samarium149_inventory[row, col] = 0.0
        self.fuel_temperature[row, col] = 600.0
        self.moderator_temperature[row, col] = 560.0
        self.moderator_density[row, col] = 1.0
        if key == "SEED":
            self.u233_inventory[row, col] = 1.0

    def _capture_cell_state(self, row: int, col: int) -> Dict[str, float]:
        return {
            name: float(getattr(self, name)[row, col])
            for name in self.ASSEMBLY_STATE_FIELDS
        }

    def _restore_cell_state(self, row: int, col: int, state: Dict[str, float]) -> None:
        for name in self.ASSEMBLY_STATE_FIELDS:
            if name in state:
                getattr(self, name)[row, col] = float(state[name])

    def _empty_cell(self, row: int, col: int) -> None:
        self._initialize_cell_state(row, col, "EMPTY")
        self.assembly_ids[row, col] = ""

    def set_assembly(self, row: int, col: int, key: str) -> None:
        """Place a newly created assembly; replaced fuel moves to storage."""
        if not self.mask[row, col]:
            return
        if key not in ASSEMBLY_TYPES:
            raise ValueError(f"Unknown assembly type: {key}")
        existing_id = str(self.assembly_ids[row, col])
        if existing_id:
            record = self.assembly_registry[existing_id]
            record.state = self._capture_cell_state(row, col)
            record.status = "storage"
            record.position = None
        if key == "EMPTY":
            self._empty_cell(row, col)
            return
        self._initialize_cell_state(row, col, key)
        assembly_id = self._new_assembly_id(key)
        self.assembly_ids[row, col] = assembly_id
        record = AssemblyRecord(
            assembly_id=assembly_id,
            assembly_type=key,
            status="in_core",
            position=self.position_id(row, col),
            cycles_completed={"ONCE": 1, "TWICE": 2}.get(key, 0),
        )
        record.state = self._capture_cell_state(row, col)
        self.assembly_registry[assembly_id] = record

    def clear_core(self, clear_inventory: bool = True) -> None:
        self.layout[:] = "EMPTY"
        self.assembly_ids[:] = ""
        if clear_inventory:
            self.assembly_registry.clear()
            self.next_assembly_number = 1
            self.cycle_number = 1
            self.total_full_power_days = 0.0
            self.total_outage_days = 0.0
            self.cycle_completion_recorded = False
        self.burnup.fill(0.0)
        self.u233_inventory.fill(0.0)
        self.pa233_inventory.fill(0.0)
        self.u235_inventory.fill(0.0)
        self.pu239_inventory.fill(0.0)
        self.poison_inventory.fill(0.0)
        self.iodine135_inventory.fill(0.0)
        self.xenon135_inventory.fill(0.0)
        self.promethium149_inventory.fill(0.0)
        self.samarium149_inventory.fill(0.0)
        self.fuel_temperature.fill(600.0)
        self.moderator_temperature.fill(560.0)
        self.moderator_density.fill(1.0)
        self.cycle_days = 0.0
        self.reset_arrays()

    def load_conventional_pwr(self) -> None:
        self.clear_core()
        centre = (GRID_SIZE - 1) / 2.0
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if not self.mask[r, c]:
                    continue
                d = math.hypot(r - centre, c - centre)
                if d > 4.55:
                    key = "ONCE"
                elif d > 3.35:
                    key = "FRESH" if (r + c) % 2 == 0 else "TWICE"
                elif d > 1.75:
                    key = "BA" if (2 * r + c) % 5 == 0 else "ONCE"
                else:
                    key = "TWICE" if (r + c) % 2 == 0 else "ONCE"
                self.set_assembly(r, c, key)
        self.solve()
        self.record_assembly_histories("initial_loading")

    def load_thorium_seed_blanket(self) -> None:
        self.clear_core()
        centre = (GRID_SIZE - 1) / 2.0
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if not self.mask[r, c]:
                    continue
                d = math.hypot(r - centre, c - centre)
                if d > 4.35:
                    key = "REFL"
                elif d > 3.10:
                    key = "TH"
                elif d > 1.45:
                    key = "SEED" if (r + c) % 2 == 0 else "TH"
                else:
                    key = "SEED"
                self.set_assembly(r, c, key)
        self.solve()
        self.record_assembly_histories("initial_loading")

    def load_thorium_checkerboard(self) -> None:
        self.clear_core()
        centre = (GRID_SIZE - 1) / 2.0
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if not self.mask[r, c]:
                    continue
                d = math.hypot(r - centre, c - centre)
                if d > 4.45:
                    key = "REFL"
                else:
                    key = "SEED" if (r + c) % 2 == 0 else "TH"
                self.set_assembly(r, c, key)
        self.solve()
        self.record_assembly_histories("initial_loading")

    def _material_arrays(self, boron_ppm: float = 0.0) -> Tuple[np.ndarray, ...]:
        """Build classroom two-group constants from the current isotopic state."""
        shape = self.burnup.shape
        d_fast = np.zeros(shape)
        d_thermal = np.zeros(shape)
        absorb_fast = np.zeros(shape)
        absorb_thermal = np.zeros(shape)
        scatter_down = np.zeros(shape)
        nu_fission_fast = np.zeros(shape)
        nu_fission_thermal = np.zeros(shape)
        fertile_th = np.zeros(shape)
        fertile_u8 = np.zeros(shape)

        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if not self.mask[r, c] or self.layout[r, c] == "EMPTY":
                    continue
                spec = ASSEMBLY_TYPES[self.layout[r, c]]
                u235 = self.u235_inventory[r, c]
                pu239 = self.pu239_inventory[r, c]
                u233 = self.u233_inventory[r, c]
                fissile = 0.78 * u235 + 0.98 * pu239 + 1.06 * u233
                density = max(self.moderator_density[r, c], 0.60)
                doppler = max(math.sqrt(self.fuel_temperature[r, c] / 600.0) - 1.0, 0.0)
                rod = self.control_fraction[r, c]

                d_fast[r, c] = 1.35 * spec.diffusion / density
                d_thermal[r, c] = 0.36 * spec.diffusion / density
                absorb_fast[r, c] = 0.0085 + 0.0030 * spec.absorption + 0.0018 * doppler + 0.045 * rod
                absorb_thermal[r, c] = (
                    0.030 + density * (0.022 + 0.075 * spec.absorption)
                    + 0.16 * self.poison_inventory[r, c]
                    + 0.006 * self.xenon135_inventory[r, c]
                    + 0.004 * self.samarium149_inventory[r, c]
                    + 0.80 * rod
                    + BORON_ABSORPTION_PER_PPM * max(boron_ppm, 0.0)
                )
                scatter_down[r, c] = density * 0.0205 * (1.05 - 0.08 * spec.absorption)
                nu_fission_fast[r, c] = FISSION_DATA_SCALE * 0.0060 * fissile
                nu_fission_thermal[r, c] = FISSION_DATA_SCALE * 0.134 * fissile
                fertile_th[r, c] = spec.fertile_th
                fertile_u8[r, c] = spec.fertile_u8

        return (
            d_fast, d_thermal, absorb_fast, absorb_thermal, scatter_down,
            nu_fission_fast, nu_fission_thermal, fertile_th, fertile_u8,
        )

    @staticmethod
    def _build_loss_matrix(
        active: np.ndarray,
        diffusion: np.ndarray,
        removal: np.ndarray,
    ) -> Tuple[np.ndarray, List[Tuple[int, int]], Dict[Tuple[int, int], int]]:
        cells = [(int(r), int(c)) for r, c in zip(*np.where(active))]
        index = {cell: i for i, cell in enumerate(cells)}
        matrix = np.zeros((len(cells), len(cells)), dtype=float)
        mesh_sq = ASSEMBLY_PITCH_CM ** 2
        for cell, i in index.items():
            r, c = cell
            diagonal = removal[r, c]
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor = (r + dr, c + dc)
                if neighbor in index:
                    rr, cc = neighbor
                    pair_d = 2.0 * diffusion[r, c] * diffusion[rr, cc] / max(
                        diffusion[r, c] + diffusion[rr, cc], 1.0e-12,
                    )
                    coupling = pair_d / mesh_sq
                    diagonal += coupling
                    matrix[i, index[neighbor]] = -coupling
                else:
                    # Vacuum-like extrapolated boundary leakage.
                    diagonal += 2.0 * diffusion[r, c] / mesh_sq
            matrix[i, i] = diagonal
        return matrix, cells, index

    def _solve_two_group(
        self,
        boron_ppm: float,
        max_iterations: int,
        tolerance: float,
    ) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray, float, Tuple[np.ndarray, ...]]:
        active = self.mask & (self.layout != "EMPTY")
        xs = self._material_arrays(boron_ppm)
        d1, d2, sa1, sa2, scatter, nuf1, nuf2, _th, _u8 = xs
        matrix1, cells, _index = self._build_loss_matrix(active, d1, sa1 + scatter)
        matrix2, _cells2, _index2 = self._build_loss_matrix(active, d2, sa2)
        if not cells:
            zeros = np.zeros_like(self.burnup)
            return 0.0, zeros, zeros, zeros, 0.0, xs

        inv1 = np.linalg.inv(matrix1)
        inv2 = np.linalg.inv(matrix2)
        nuf1_v = np.array([nuf1[cell] for cell in cells])
        nuf2_v = np.array([nuf2[cell] for cell in cells])
        scatter_v = np.array([scatter[cell] for cell in cells])
        phi1 = np.ones(len(cells), dtype=float)
        phi2 = np.full(len(cells), 0.35, dtype=float)
        source = nuf1_v * phi1 + nuf2_v * phi2
        scale = max(float(np.sum(source)), 1.0e-12)
        phi1 /= scale
        phi2 /= scale
        k_value = 1.0

        for _ in range(max_iterations):
            old1, old2, old_k = phi1.copy(), phi2.copy(), k_value
            old_source = nuf1_v * old1 + nuf2_v * old2
            phi1 = inv1 @ (old_source / max(old_k, 1.0e-12))
            phi2 = inv2 @ (scatter_v * phi1)
            new_source = nuf1_v * phi1 + nuf2_v * phi2
            k_value = old_k * float(np.sum(new_source)) / max(float(np.sum(old_source)), 1.0e-12)
            normalization = max(float(np.sum(new_source)), 1.0e-12)
            phi1 /= normalization
            phi2 /= normalization
            flux_error = max(float(np.max(np.abs(phi1 - old1))), float(np.max(np.abs(phi2 - old2))))
            if abs(k_value - old_k) < tolerance and flux_error < 10.0 * tolerance:
                break

        fast = np.zeros_like(self.burnup)
        thermal = np.zeros_like(self.burnup)
        for i, cell in enumerate(cells):
            fast[cell], thermal[cell] = phi1[i], phi2[i]
        sigma_f_fast = nuf1 / 2.43
        sigma_f_thermal = nuf2 / 2.43
        power_raw = sigma_f_fast * fast + sigma_f_thermal * thermal
        leakage = self._two_group_boundary_leakage(fast, thermal, active, d1, d2)
        total_loss = float(np.sum((sa1 * fast + sa2 * thermal)[active])) + leakage
        leakage_fraction = leakage / max(total_loss, 1.0e-12)
        return k_value, fast, thermal, power_raw, leakage_fraction, xs

    def solve(
        self,
        max_iterations: int = 250,
        tolerance: float = 1.0e-8,
        feedback_iterations: int = 240,
        feedback_tolerance: float = 1.0e-7,
        feedback_relaxation: float = 0.40,
        _previous_feedback_residual: Optional[float] = None,
        _feedback_restarts: int = 0,
    ) -> None:
        if _previous_feedback_residual is None and _feedback_restarts == 0:
            self.feedback_restart_count = 0
        active = self.mask & (self.layout != "EMPTY")
        if not np.any(active):
            self.reset_arrays()
            return

        uncontrolled = self._solve_two_group(0.0, max_iterations, tolerance)
        self.k_eff = float(uncontrolled[0])
        operating = uncontrolled
        self.required_boron_ppm = 0.0
        if self.k_eff > 1.0:
            high_solution = self._solve_two_group(MAX_BORON_PPM, max_iterations, tolerance)
            if high_solution[0] <= 1.0:
                low, high = 0.0, MAX_BORON_PPM
                for _ in range(16):
                    midpoint = 0.5 * (low + high)
                    trial = self._solve_two_group(midpoint, max_iterations, tolerance)
                    if trial[0] > 1.0:
                        low = midpoint
                    else:
                        high = midpoint
                        operating = trial
                self.required_boron_ppm = high
                operating = self._solve_two_group(high, max_iterations, tolerance)
            else:
                self.required_boron_ppm = MAX_BORON_PPM
                operating = high_solution

        self.operating_k_eff = float(operating[0])
        _k, fast, thermal, power_raw, leakage_fraction, xs = operating
        _d1, _d2, _sa1, _sa2, _scatter, _nuf1, _nuf2, fertile_th, _fertile_u8 = xs
        total_flux = fast + thermal
        flux_scale = max(float(np.max(total_flux[active])), 1.0e-12)
        self.fast_flux = np.where(active, fast / flux_scale, 0.0)
        self.thermal_flux = np.where(active, thermal / flux_scale, 0.0)
        self.flux = self.fast_flux + self.thermal_flux

        fuel = active & (self.layout != "REFL")
        self.power_index = np.where(fuel, power_raw, 0.0)
        mean_power = float(np.mean(power_raw[fuel])) if np.any(fuel) else 0.0
        self.power = np.where(fuel, power_raw / max(mean_power, 1.0e-12), 0.0)

        # Reaction-rate breeding proxy uses the solved thermal-group flux.
        self.breeding = np.where(active, 0.070 * fertile_th * self.thermal_flux, 0.0)
        bred_rate = float(np.sum(self.breeding[active]))
        fission_rate = float(np.sum(power_raw[fuel])) if np.any(fuel) else 0.0
        self.conversion_ratio = bred_rate / max(0.32 * fission_rate, 1.0e-12)
        self.radial_peaking = float(np.max(self.power[fuel])) if np.any(fuel) else 0.0
        self.leakage_index = leakage_fraction
        self._update_shape_diagnostics(active)

        # Assembly-level equilibrium thermal feedback and full-power xenon.
        target_fuel_temp = np.where(fuel, 600.0 + 350.0 * self.power, 600.0)
        target_moderator_temp = np.where(active, 560.0 + 12.0 * self.power, 560.0)
        target_density = np.where(
            active,
            np.clip(1.0 - 0.0018 * (target_moderator_temp - 560.0), 0.82, 1.02),
            1.0,
        )
        target_iodine = np.where(fuel, 0.80 * self.power, 0.0)
        target_xenon = np.where(
            fuel,
            (0.16 * self.power + 0.84 * target_iodine)
            / (1.0 + 0.90 * self.thermal_flux),
            0.0,
        )
        feedback_fields = (
                (self.fuel_temperature, target_fuel_temp),
                (self.moderator_temperature, target_moderator_temp),
                (self.moderator_density, target_density),
                (self.iodine135_inventory, target_iodine),
                (self.xenon135_inventory, target_xenon),
        )
        feedback_residual = max(
            float(np.max(
                np.abs(target[active] - field[active])
                / np.maximum(np.abs(target[active]), 1.0)
            ))
            for field, target in feedback_fields
        )
        self.feedback_residual = feedback_residual
        if feedback_iterations > 1 and feedback_residual > feedback_tolerance:
            relaxation = feedback_relaxation
            if (
                _previous_feedback_residual is not None
                and feedback_residual > 1.02 * _previous_feedback_residual
            ):
                relaxation = max(0.05, 0.5 * relaxation)
            elif (
                _previous_feedback_residual is not None
                and feedback_residual < 0.85 * _previous_feedback_residual
            ):
                relaxation = min(0.50, 1.10 * relaxation)
            for field, target in feedback_fields:
                field[active] += relaxation * (target[active] - field[active])
            self.solve(
                max_iterations, tolerance, feedback_iterations - 1,
                feedback_tolerance, relaxation, feedback_residual,
                _feedback_restarts,
            )
            return
        if feedback_residual > feedback_tolerance:
            if _feedback_restarts < 4:
                self.feedback_restart_count = _feedback_restarts + 1
                self.solve(
                    max_iterations=max_iterations,
                    tolerance=tolerance,
                    feedback_iterations=240,
                    feedback_tolerance=feedback_tolerance,
                    feedback_relaxation=0.40,
                    _previous_feedback_residual=None,
                    _feedback_restarts=_feedback_restarts + 1,
                )
                return
            raise RuntimeError(
                "Coupled neutronics/thermal/xenon feedback did not converge "
                f"(residual {feedback_residual:.3e}, target {feedback_tolerance:.3e})."
            )

        # Calculate rod worth and the all-banks-in shutdown state at the
        # converged temperature and poison condition without altering the core.
        current_control = self.control_fraction.copy()
        current_rho = (self.k_eff - 1.0) / max(self.k_eff, 1.0e-12)
        self.control_fraction.fill(0.0)
        no_rod_k = self._solve_two_group(0.0, max_iterations, tolerance)[0]
        no_rod_rho = (no_rod_k - 1.0) / max(no_rod_k, 1.0e-12)
        self.control_worth_pcm = max(0.0, (no_rod_rho - current_rho) * 1.0e5)
        self.control_fraction[:] = 0.0
        self.control_fraction[self.control_bank_mask & active] = 1.0
        self.shutdown_k_eff = self._solve_two_group(0.0, max_iterations, tolerance)[0]
        shutdown_rho = (self.shutdown_k_eff - 1.0) / max(self.shutdown_k_eff, 1.0e-12)
        self.shutdown_margin_pcm = max(0.0, -shutdown_rho * 1.0e5)
        self.control_fraction[:] = current_control

    def set_control_insertion(self, insertion_percent: float) -> None:
        fraction = max(0.0, min(100.0, insertion_percent)) / 100.0
        self.control_fraction.fill(0.0)
        active_banks = self.control_bank_mask & self.mask & (self.layout != "EMPTY")
        self.control_fraction[active_banks] = fraction
        self.solve()

    def _update_shape_diagnostics(self, active: np.ndarray) -> None:
        """Derive radial and directional indicators from the solved flux map."""
        rows, cols = np.indices(self.flux.shape)
        centre = (GRID_SIZE - 1) / 2.0
        radius = np.hypot(rows - centre, cols - centre)
        central = active & (radius <= 1.75)
        outer = active & (radius >= 3.75)
        central_mean = float(np.mean(self.flux[central])) if np.any(central) else 0.0
        outer_mean = float(np.mean(self.flux[outer])) if np.any(outer) else 0.0
        self.centre_edge_ratio = central_mean / max(outer_mean, 1.0e-12)

        north = active & (rows < centre)
        south = active & (rows > centre)
        west = active & (cols < centre)
        east = active & (cols > centre)

        def symmetric_tilt(first: np.ndarray, second: np.ndarray) -> float:
            a = float(np.mean(self.flux[first])) if np.any(first) else 0.0
            b = float(np.mean(self.flux[second])) if np.any(second) else 0.0
            return (a - b) / max(0.5 * (a + b), 1.0e-12)

        self.north_south_tilt = symmetric_tilt(north, south)
        self.east_west_tilt = symmetric_tilt(east, west)
        total = float(np.sum(self.flux[active]))
        centroid_r = float(np.sum(rows[active] * self.flux[active]) / max(total, 1.0e-12))
        centroid_c = float(np.sum(cols[active] * self.flux[active]) / max(total, 1.0e-12))
        self.flux_centroid_offset = math.hypot(centroid_r - centre, centroid_c - centre)

    @staticmethod
    def _two_group_boundary_leakage(
        fast: np.ndarray,
        thermal: np.ndarray,
        active: np.ndarray,
        d_fast: np.ndarray,
        d_thermal: np.ndarray,
    ) -> float:
        leakage = 0.0
        mesh_sq = ASSEMBLY_PITCH_CM ** 2
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if not active[r, c]:
                    continue
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    rr, cc = r + dr, c + dc
                    if not (0 <= rr < GRID_SIZE and 0 <= cc < GRID_SIZE and active[rr, cc]):
                        leakage += 2.0 * (
                            d_fast[r, c] * fast[r, c]
                            + d_thermal[r, c] * thermal[r, c]
                        ) / mesh_sq
        return leakage

    def advance_cycle(self, days: float) -> None:
        if days <= 0.0:
            return
        # Explicit depletion updates remain well conditioned at the normal
        # teaching step of 30 FPD.  Split unusually large requests internally
        # instead of applying one oversized nonlinear isotope update.
        if days > 30.0:
            increments = int(math.ceil(days / 30.0))
            increment = days / increments
            for _ in range(increments):
                self.advance_cycle(increment)
            return
        self.solve()
        active = self.mask & (self.layout != "EMPTY")
        fuel = active & (self.layout != "REFL")
        if not np.any(fuel):
            return

        # Approximate assembly burnup gain. Normalized power of 1.0 corresponds
        # to roughly 0.045 GWd/tHM per full-power day in this teaching model.
        burnup_gain = 0.045 * days * self.power
        self.burnup[fuel] += burnup_gain[fuel]

        # Reduced Bateman-style heavy-metal evolution. Rates are deliberately
        # classroom-scaled but are driven by each assembly's solved group flux
        # and fission power rather than burnup alone.
        u235_decay = np.exp(-0.00021 * days * self.power)
        pu_decay = np.exp(-0.00013 * days * self.power)
        u233_decay = np.exp(-0.00018 * days * self.power)
        self.u235_inventory[fuel] *= u235_decay[fuel]
        self.pu239_inventory[fuel] *= pu_decay[fuel]
        self.u233_inventory[fuel] *= u233_decay[fuel]
        for r, c in zip(*np.where(fuel)):
            spec = ASSEMBLY_TYPES[str(self.layout[r, c])]
            self.pu239_inventory[r, c] += (
                0.00018 * days * spec.fertile_u8 * self.fast_flux[r, c]
            )
        self.poison_inventory[active] *= np.exp(
            -0.0030 * days * self.thermal_flux[active]
        )

        # Track an explicit Pa-233 precursor.  The analytic constant-source
        # update avoids making U-233 production an arbitrary function of the
        # selected cycle-step length.
        decay_constant = math.log(2.0) / 26.97
        decay = math.exp(-decay_constant * days)
        production_rate = 0.020 * self.breeding
        old_pa = self.pa233_inventory.copy()
        self.pa233_inventory[active] = (
            old_pa[active] * decay
            + production_rate[active] * (1.0 - decay) / decay_constant
        )
        u233_gain = (
            old_pa * (1.0 - decay)
            + production_rate * (days - (1.0 - decay) / decay_constant)
        )
        self.u233_inventory[active] += np.maximum(u233_gain[active], 0.0)

        # Pm-149 decays to stable Sm-149, which is removed only by neutron
        # capture in this reduced chain. The analytic precursor update remains
        # stable for the multi-day cycle steps used by the interface.
        pm_decay_constant = math.log(2.0) / 2.21
        pm_decay = math.exp(-pm_decay_constant * days)
        pm_production = 0.0008 * self.power
        old_pm = self.promethium149_inventory.copy()
        self.promethium149_inventory[fuel] = (
            old_pm[fuel] * pm_decay
            + pm_production[fuel] * (1.0 - pm_decay) / pm_decay_constant
        )
        sm_gain = (
            old_pm * (1.0 - pm_decay)
            + pm_production * (days - (1.0 - pm_decay) / pm_decay_constant)
        )
        self.samarium149_inventory[fuel] += np.maximum(sm_gain[fuel], 0.0)
        self.samarium149_inventory[fuel] *= np.exp(
            -0.0018 * days * self.thermal_flux[fuel]
        )
        self.cycle_days += days
        self.total_full_power_days += days
        self.solve()
        self.record_assembly_histories("cycle_step")

    def reset_depletion(self) -> None:
        """Restore beginning-of-cycle isotopes for the current loading map."""
        current_layout = self.layout.copy()
        for r, c in zip(*np.where(self.mask)):
            self._initialize_cell_state(int(r), int(c), str(current_layout[r, c]))
        self.cycle_days = 0.0
        self.solve()
        self.record_assembly_histories("depletion_reset")

    def _locate_assembly(self, assembly_id: str) -> Optional[Tuple[int, int]]:
        matches = np.argwhere(self.assembly_ids == assembly_id)
        if matches.size == 0:
            return None
        return int(matches[0, 0]), int(matches[0, 1])

    def sync_assembly_registry(self) -> None:
        for assembly_id, record in self.assembly_registry.items():
            if record.status != "in_core":
                continue
            cell = self._locate_assembly(assembly_id)
            if cell is None:
                continue
            record.position = self.position_id(*cell)
            record.state = self._capture_cell_state(*cell)

    def record_assembly_histories(self, event: str) -> None:
        self.sync_assembly_registry()
        for assembly_id, record in self.assembly_registry.items():
            cell = self._locate_assembly(assembly_id) if record.status == "in_core" else None
            entry: Dict[str, Any] = {
                "event": event,
                "cycle": self.cycle_number,
                "cycle_fpd": float(self.cycle_days),
                "total_fpd": float(self.total_full_power_days),
                "total_outage_days": float(self.total_outage_days),
                "status": record.status,
                "position": record.position,
                "assembly_type": record.assembly_type,
            }
            entry.update(record.state)
            if cell is not None:
                r, c = cell
                entry.update({
                    "flux": float(self.flux[r, c]),
                    "fast_flux": float(self.fast_flux[r, c]),
                    "thermal_flux": float(self.thermal_flux[r, c]),
                    "power": float(self.power[r, c]),
                    "breeding": float(self.breeding[r, c]),
                })
            else:
                entry.update({"flux": 0.0, "fast_flux": 0.0, "thermal_flux": 0.0, "power": 0.0, "breeding": 0.0})
            record.history.append(entry)

    def move_or_swap_assemblies(
        self,
        source: Tuple[int, int],
        target: Tuple[int, int],
        recalculate: bool = True,
        record_event: bool = True,
    ) -> None:
        if source == target:
            return
        sr, sc = source
        tr, tc = target
        if not self.mask[sr, sc] or not self.mask[tr, tc]:
            raise ValueError("Both source and target must be active core positions.")
        source_id = str(self.assembly_ids[sr, sc])
        if not source_id:
            raise ValueError("The source position contains no assembly.")
        target_id = str(self.assembly_ids[tr, tc])
        source_key, target_key = str(self.layout[sr, sc]), str(self.layout[tr, tc])
        source_state = self._capture_cell_state(sr, sc)
        target_state = self._capture_cell_state(tr, tc)

        self._initialize_cell_state(tr, tc, source_key)
        self._restore_cell_state(tr, tc, source_state)
        self.assembly_ids[tr, tc] = source_id
        self.assembly_registry[source_id].position = self.position_id(tr, tc)
        if target_id:
            self._initialize_cell_state(sr, sc, target_key)
            self._restore_cell_state(sr, sc, target_state)
            self.assembly_ids[sr, sc] = target_id
            self.assembly_registry[target_id].position = self.position_id(sr, sc)
        else:
            self._empty_cell(sr, sc)
        if recalculate:
            self.solve()
        if record_event:
            self.record_assembly_histories("refueling_move")

    def discharge_assembly(
        self,
        row: int,
        col: int,
        recalculate: bool = True,
        record_event: bool = True,
    ) -> Optional[str]:
        assembly_id = str(self.assembly_ids[row, col])
        if not assembly_id:
            return None
        record = self.assembly_registry[assembly_id]
        record.state = self._capture_cell_state(row, col)
        record.status = "storage"
        record.position = None
        self._empty_cell(row, col)
        if recalculate:
            self.solve()
        if record_event:
            self.record_assembly_histories("discharged")
        return assembly_id

    def load_stored_assembly(
        self,
        assembly_id: str,
        row: int,
        col: int,
        recalculate: bool = True,
        record_event: bool = True,
    ) -> None:
        if assembly_id not in self.assembly_registry:
            raise ValueError("Unknown assembly ID.")
        record = self.assembly_registry[assembly_id]
        if record.status != "storage":
            raise ValueError("Selected assembly is not in storage.")
        existing_id = str(self.assembly_ids[row, col])
        if existing_id:
            existing = self.assembly_registry[existing_id]
            existing.state = self._capture_cell_state(row, col)
            existing.status = "storage"
            existing.position = None
        self._initialize_cell_state(row, col, record.assembly_type)
        self._restore_cell_state(row, col, record.state)
        self.assembly_ids[row, col] = assembly_id
        record.status = "in_core"
        record.position = self.position_id(row, col)
        if recalculate:
            self.solve()
        if record_event:
            self.record_assembly_histories("loaded_from_storage")

    def unload_all_to_staging(self) -> int:
        """Unload every in-core assembly without solving an incomplete draft core."""
        count = 0
        for r, c in zip(*np.where(self.mask & (self.assembly_ids != ""))):
            assembly_id = str(self.assembly_ids[r, c])
            if self.discharge_assembly(int(r), int(c), recalculate=False, record_event=False):
                self.assembly_registry[assembly_id].cycles_completed += 1
                count += 1
        self.reset_arrays()
        self.record_assembly_histories("unloaded_to_staging")
        self.cycle_completion_recorded = True
        return count

    def refueling_category(self, assembly_id: str) -> str:
        record = self.assembly_registry[assembly_id]
        if record.assembly_type in ("TH", "SEED", "REFL"):
            return "special"
        if record.status == "spent" or record.cycles_completed >= 3:
            return "spent"
        if record.cycles_completed == 1:
            return "once"
        if record.cycles_completed == 2:
            return "twice"
        return "other"

    @staticmethod
    def _decay_outage_state(state: Dict[str, float], days: float) -> Dict[str, float]:
        result = dict(state)
        iodine = result.get("iodine135_inventory", 0.0)
        xenon = result.get("xenon135_inventory", 0.0)
        lambda_i = math.log(2.0) / 0.274
        lambda_x = math.log(2.0) / 0.377
        exp_i, exp_x = math.exp(-lambda_i * days), math.exp(-lambda_x * days)
        iodine_new = iodine * exp_i
        xenon_from_iodine = (
            iodine * lambda_i * (exp_i - exp_x) / (lambda_x - lambda_i)
            if abs(lambda_x - lambda_i) > 1.0e-12 else 0.0
        )
        result["iodine135_inventory"] = max(iodine_new, 0.0)
        result["xenon135_inventory"] = max(xenon * exp_x + xenon_from_iodine, 0.0)

        pa = result.get("pa233_inventory", 0.0)
        pa_decay = math.exp(-math.log(2.0) * days / 26.97)
        result["pa233_inventory"] = pa * pa_decay
        result["u233_inventory"] = result.get("u233_inventory", 0.0) + pa * (1.0 - pa_decay)

        pm = result.get("promethium149_inventory", 0.0)
        pm_decay = math.exp(-math.log(2.0) * days / 2.21)
        result["promethium149_inventory"] = pm * pm_decay
        result["samarium149_inventory"] = result.get("samarium149_inventory", 0.0) + pm * (1.0 - pm_decay)
        result["fuel_temperature"] = 300.0
        result["moderator_temperature"] = 300.0
        result["moderator_density"] = 1.0
        return result

    def begin_next_cycle(self, outage_days: float) -> None:
        if not math.isfinite(outage_days) or outage_days < 0.0:
            raise ValueError("Outage duration must be a non-negative number of days.")
        self.sync_assembly_registry()
        old_cycle = self.cycle_number
        for assembly_id, record in self.assembly_registry.items():
            if not self.cycle_completion_recorded and any(entry.get("cycle") == old_cycle and entry.get("status") == "in_core" for entry in record.history):
                record.cycles_completed += 1
            record.state = self._decay_outage_state(record.state, outage_days)
            if record.status == "in_core":
                cell = self._locate_assembly(assembly_id)
                if cell is not None:
                    self._restore_cell_state(*cell, record.state)
        self.total_outage_days += outage_days
        self.cycle_number += 1
        self.cycle_completion_recorded = False
        self.cycle_days = 0.0
        self.solve()
        self.record_assembly_histories("begin_cycle")

    def storage_ids(self) -> List[str]:
        return sorted(
            assembly_id for assembly_id, record in self.assembly_registry.items()
            if record.status == "storage"
        )

    def save_state(self, path: str) -> None:
        self.sync_assembly_registry()
        arrays = {
            name: getattr(self, name).tolist()
            for name in self.ASSEMBLY_STATE_FIELDS + ("control_fraction",)
        }
        payload = {
            "format_version": 1,
            "layout": self.layout.tolist(),
            "assembly_ids": self.assembly_ids.tolist(),
            "arrays": arrays,
            "registry": {key: asdict(value) for key, value in self.assembly_registry.items()},
            "next_assembly_number": self.next_assembly_number,
            "cycle_number": self.cycle_number,
            "cycle_days": self.cycle_days,
            "total_full_power_days": self.total_full_power_days,
            "total_outage_days": self.total_outage_days,
            "cycle_completion_recorded": self.cycle_completion_recorded,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def load_state(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        layout = np.asarray(payload["layout"], dtype=object)
        assembly_ids = np.asarray(payload["assembly_ids"], dtype=object)
        if layout.shape != (GRID_SIZE, GRID_SIZE) or assembly_ids.shape != layout.shape:
            raise ValueError("Saved core does not contain an 11 x 11 layout.")
        self.layout[:] = layout
        self.assembly_ids[:] = assembly_ids
        for name in self.ASSEMBLY_STATE_FIELDS + ("control_fraction",):
            values = np.asarray(payload["arrays"][name], dtype=float)
            if values.shape != layout.shape:
                raise ValueError(f"Invalid saved array shape for {name}.")
            getattr(self, name)[:] = values
        self.assembly_registry = {
            key: AssemblyRecord(**value)
            for key, value in payload["registry"].items()
        }
        self.next_assembly_number = int(payload["next_assembly_number"])
        self.cycle_number = int(payload["cycle_number"])
        self.cycle_days = float(payload["cycle_days"])
        self.total_full_power_days = float(payload["total_full_power_days"])
        self.total_outage_days = float(payload["total_outage_days"])
        self.cycle_completion_recorded = bool(payload.get("cycle_completion_recorded", False))
        self.solve()

    def assembly_counts(self) -> Dict[str, int]:
        counts = {key: 0 for key in ASSEMBLY_TYPES}
        for value in self.layout[self.mask]:
            counts[str(value)] += 1
        return counts

    def export_csv(self, path: str) -> int:
        rows = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if not self.mask[r, c]:
                    continue
                key = str(self.layout[r, c])
                rows.append({
                    "row": r + 1,
                    "column": c + 1,
                    "position_id": self.position_id(r, c),
                    "assembly_id": str(self.assembly_ids[r, c]),
                    "assembly_key": key,
                    "assembly_name": ASSEMBLY_TYPES[key].name,
                    "burnup_GWd_tHM": self.burnup[r, c],
                    "relative_flux": self.flux[r, c],
                    "relative_fast_flux": self.fast_flux[r, c],
                    "relative_thermal_flux": self.thermal_flux[r, c],
                    "relative_power": self.power[r, c],
                    "breeding_index": self.breeding[r, c],
                    "u233_inventory_index": self.u233_inventory[r, c],
                    "pa233_inventory_index": self.pa233_inventory[r, c],
                    "u235_inventory_index": self.u235_inventory[r, c],
                    "pu239_inventory_index": self.pu239_inventory[r, c],
                    "burnable_poison_inventory": self.poison_inventory[r, c],
                    "iodine135_inventory_index": self.iodine135_inventory[r, c],
                    "xenon135_inventory_index": self.xenon135_inventory[r, c],
                    "promethium149_inventory_index": self.promethium149_inventory[r, c],
                    "samarium149_inventory_index": self.samarium149_inventory[r, c],
                    "fuel_temperature_K": self.fuel_temperature[r, c],
                    "moderator_temperature_K": self.moderator_temperature[r, c],
                    "moderator_relative_density": self.moderator_density[r, c],
                    "control_insertion_fraction": self.control_fraction[r, c],
                    "cycle_days": self.cycle_days,
                    "cycle_number": self.cycle_number,
                    "total_full_power_days": self.total_full_power_days,
                    "total_outage_days": self.total_outage_days,
                    "k_eff_teaching": self.k_eff,
                    "operating_k_eff_teaching": self.operating_k_eff,
                    "required_boron_ppm_teaching": self.required_boron_ppm,
                    "all_banks_in_k_teaching": self.shutdown_k_eff,
                    "shutdown_margin_pcm_teaching": self.shutdown_margin_pcm,
                    "inserted_control_worth_pcm_teaching": self.control_worth_pcm,
                    "unnormalized_power_index": self.power_index[r, c],
                    "radial_peaking": self.radial_peaking,
                    "conversion_ratio_teaching": self.conversion_ratio,
                    "leakage_index": self.leakage_index,
                    "centre_to_edge_flux_ratio": self.centre_edge_ratio,
                    "north_south_flux_tilt": self.north_south_tilt,
                    "east_west_flux_tilt": self.east_west_tilt,
                    "flux_centroid_offset_cells": self.flux_centroid_offset,
                })

        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)


def find_logo_path(filename: str) -> Optional[Path]:
    candidates = [
        Path(__file__).resolve().parent / filename,
        Path(__file__).resolve().parent.parent / filename,
        Path(__file__).resolve().parent.parent.parent / filename,
        Path(__file__).resolve().parent.parent.parent / "assets" / filename,
        Path.cwd() / filename,
        Path.cwd() / "assets" / filename,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_logo(
    master: tk.Misc,
    max_width: int,
    max_height: int,
    filename: str = "",
) -> Optional[tk.PhotoImage]:
    path = find_logo_path(filename)
    if path is None:
        return None

    if Image is not None and ImageTk is not None:
        try:
            with Image.open(path) as source:
                image = source.convert("RGBA")
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image, master=master)
        except (OSError, ValueError):
            pass

    try:
        image = tk.PhotoImage(master=master, file=str(path))
        factor = max(1, math.ceil(max(image.width() / max_width, image.height() / max_height)))
        return image.subsample(factor, factor) if factor > 1 else image
    except tk.TclError:
        return None


class CoreLoadingApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(MODULE_NAME)
        self.root.geometry("1510x900")
        self.root.minsize(900, 700)
        self.root.configure(bg="#0f1115")

        self.model = CoreModel()
        self.selected_type = tk.StringVar(value="FRESH")
        self.display_mode = tk.StringVar(value="Power")
        self.plot_view = tk.StringVar(value="Split")
        self.cycle_days_var = tk.DoubleVar(value=30.0)
        self.animation_delay_var = tk.DoubleVar(value=0.8)
        self.stop_exposure_var = tk.DoubleVar(value=1000.0)
        self.stop_on_warning_var = tk.BooleanVar(value=True)
        self.control_insertion_var = tk.DoubleVar(value=0.0)
        self.refueling_mode_var = tk.BooleanVar(value=False)
        self.outage_days_var = tk.DoubleVar(value=30.0)
        self.pool_assembly_var = tk.StringVar(value="")
        self.fixed_scale_var = tk.BooleanVar(value=True)
        self.show_numbers_var = tk.BooleanVar(value=True)
        self.cell_items: Dict[Tuple[int, int], Tuple[int, int]] = {}
        self.hover_cell: Optional[Tuple[int, int]] = None
        self.surface_elev = 28.0
        self.surface_azim = -55.0
        self.surface_zoom = 1.0
        self.selected_cell: Tuple[int, int] = (GRID_SIZE // 2, GRID_SIZE // 2)
        self.refuel_source: Optional[Tuple[int, int]] = None
        self.running = False
        self.run_after_id: Optional[str] = None
        self.history: Dict[str, List[object]] = {}
        self.display_scales: Dict[str, Tuple[float, float]] = {}

        self._make_style()
        self._build_gui()
        self._refresh_pool_choices()
        self._reset_history()
        self.refresh_all()

    def _make_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#0f1115")
        style.configure("Panel.TFrame", background="#1c2128")
        style.configure("TLabel", background="#1c2128", foreground="#e6edf3", font=("Segoe UI", 9))
        style.configure("Header.TLabel", background="#0f1115", foreground="#f4f7fa", font=("Segoe UI", 17, "bold"))
        style.configure("Sub.TLabel", background="#0f1115", foreground="#aebdca", font=("Segoe UI", 9))
        style.configure("Section.TLabel", background="#1c2128", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.configure("Value.TLabel", background="#07120b", foreground="#9cff9c", font=("Consolas", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 9, "bold"))
        style.configure("TRadiobutton", background="#1c2128", foreground="#e6edf3")
        style.configure("TCheckbutton", background="#1c2128", foreground="#e6edf3")

    def _build_gui(self) -> None:
        header = tk.Frame(self.root, bg="#0f1115")
        header.pack(fill=tk.X, padx=20, pady=(10, 6))
        header.grid_columnconfigure(0, weight=1)

        title_block = tk.Frame(header, bg="#0f1115")
        title_block.grid(row=0, column=0, sticky="w")
        ttk.Label(title_block, text=MODULE_NAME.upper(), style="Header.TLabel").pack(anchor="w")
        ttk.Label(title_block, text=PROJECT_NAME, style="Sub.TLabel").pack(anchor="w", pady=(3, 0))


        ttk.Button(header, text="ABOUT", command=lambda: show_suite_about(self.root)).grid(
            row=0, column=1, sticky="e", padx=(18, 0),
        )

        body = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg="#56616d", bd=0,
            sashwidth=8, sashrelief=tk.RAISED, showhandle=True,
        )
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))

        left_shell = ttk.Frame(body, style="Panel.TFrame")
        centre = ttk.Frame(body, style="Panel.TFrame", padding=10)
        right_shell = ttk.Frame(body, style="Panel.TFrame")
        body.add(left_shell, minsize=210, width=300, stretch="never")
        body.add(centre, minsize=260, width=570, stretch="always")
        body.add(right_shell, minsize=260, width=600, stretch="always")
        self.main_panes = body

        left = self._make_scrollable_left_panel(left_shell)
        right = self._make_scrollable_right_panel(right_shell)
        self._build_left_panel(left)
        self._build_core_canvas(centre)
        self._build_right_panel(right)

    def _make_scrollable_left_panel(self, parent: ttk.Frame) -> ttk.Frame:
        """Create a fixed-width control pane with vertical scrolling."""
        canvas = tk.Canvas(
            parent, width=290, bg="#1c2128", highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        panel = ttk.Frame(canvas, style="Panel.TFrame", padding=12)
        window = canvas.create_window((0, 0), window=panel, anchor="nw")

        def update_scroll_region(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_panel_width(event: tk.Event) -> None:
            canvas.itemconfigure(window, width=event.width)

        def scroll_when_hovered(event: tk.Event) -> None:
            x0, y0 = canvas.winfo_rootx(), canvas.winfo_rooty()
            x1, y1 = x0 + canvas.winfo_width(), y0 + canvas.winfo_height()
            if x0 <= event.x_root <= x1 and y0 <= event.y_root <= y1:
                widget = self.root.winfo_containing(event.x_root, event.y_root)
                plot_widget = self.plot_canvas.get_tk_widget() if hasattr(self, "plot_canvas") else None
                current = widget
                while current is not None:
                    if current == plot_widget:
                        return
                    current = getattr(current, "master", None)
                canvas.yview_scroll(-int(event.delta / 120), "units")

        panel.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_panel_width)
        self.root.bind_all("<MouseWheel>", scroll_when_hovered, add="+")
        self.left_control_canvas = canvas
        return panel

    def _make_scrollable_right_panel(self, parent: ttk.Frame) -> ttk.Frame:
        """Create a results pane whose plots and indicators can all be reached."""
        canvas = tk.Canvas(
            parent, width=590, bg="#1c2128", highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        panel = ttk.Frame(canvas, style="Panel.TFrame", padding=10)
        window = canvas.create_window((0, 0), window=panel, anchor="nw")

        def update_scroll_region(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_panel_width(event: tk.Event) -> None:
            canvas.itemconfigure(window, width=event.width)

        def scroll_when_hovered(event: tk.Event) -> None:
            x0, y0 = canvas.winfo_rootx(), canvas.winfo_rooty()
            x1, y1 = x0 + canvas.winfo_width(), y0 + canvas.winfo_height()
            if x0 <= event.x_root <= x1 and y0 <= event.y_root <= y1:
                widget = self.root.winfo_containing(event.x_root, event.y_root)
                plot_widget = self.plot_canvas.get_tk_widget() if hasattr(self, "plot_canvas") else None
                current = widget
                while current is not None:
                    if current == plot_widget:
                        return
                    current = getattr(current, "master", None)
                canvas.yview_scroll(-int(event.delta / 120), "units")

        panel.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_panel_width)
        self.root.bind_all("<MouseWheel>", scroll_when_hovered, add="+")
        self.right_result_canvas = canvas
        return panel

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="ASSEMBLY PALETTE", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

        palette = ttk.Frame(parent, style="Panel.TFrame")
        palette.pack(fill=tk.X)
        order = ["FRESH", "ONCE", "TWICE", "BA", "TH", "SEED", "REFL", "EMPTY"]
        for key in order:
            spec = ASSEMBLY_TYPES[key]
            row = tk.Frame(palette, bg="#1c2128")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, bg=spec.color, width=3, relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 6), ipady=5)
            ttk.Radiobutton(
                row, text=f"{spec.short or '×'}  {spec.name}",
                variable=self.selected_type, value=key,
                command=self._update_selected_description,
            ).pack(side=tk.LEFT, anchor="w")

        ttk.Separator(parent).pack(fill=tk.X, pady=10)
        ttk.Label(parent, text="SELECTED ASSEMBLY", style="Section.TLabel").pack(anchor="w")
        self.selected_description = tk.StringVar()
        tk.Label(
            parent, textvariable=self.selected_description, bg="#11161c", fg="#dce7ef",
            justify=tk.LEFT, wraplength=270, padx=8, pady=8, anchor="nw",
            font=("Segoe UI", 9),
        ).pack(fill=tk.X, pady=(5, 10))

        ttk.Label(parent, text="LOADING PRESETS", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        ttk.Button(parent, text="Conventional 3-batch PWR", command=self.preset_pwr).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="Thorium seed-blanket", command=self.preset_seed_blanket).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="Thorium checkerboard", command=self.preset_checkerboard).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="Clear active core", command=self.clear_core).pack(fill=tk.X, pady=2)

        ttk.Separator(parent).pack(fill=tk.X, pady=10)
        ttk.Label(parent, text="CONTROL BANKS", style="Section.TLabel").pack(anchor="w")
        ttk.Label(parent, text="Symmetric bank insertion (%):").pack(anchor="w", pady=(5, 1))
        ttk.Entry(parent, textvariable=self.control_insertion_var, width=12).pack(anchor="w")
        control_row = ttk.Frame(parent, style="Panel.TFrame")
        control_row.pack(fill=tk.X, pady=(5, 2))
        ttk.Button(control_row, text="Apply insertion", command=self.apply_control_insertion).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(control_row, text="Withdraw", command=self.withdraw_control_banks).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        ttk.Separator(parent).pack(fill=tk.X, pady=10)
        ttk.Label(parent, text="REFUELING AND ASSEMBLY TRACKING", style="Section.TLabel").pack(anchor="w")
        ttk.Button(
            parent, text="OPEN GUIDED REFUELING WORKSPACE",
            command=self.open_refueling_workspace,
        ).pack(fill=tk.X, pady=(5, 4))
        ttk.Checkbutton(
            parent, text="Refueling move/swap mode",
            variable=self.refueling_mode_var, command=self.toggle_refueling_mode,
        ).pack(anchor="w", pady=(5, 2))
        ttk.Label(parent, text="Outage duration before next cycle (days):").pack(anchor="w", pady=(4, 1))
        ttk.Entry(parent, textvariable=self.outage_days_var, width=12).pack(anchor="w")
        ttk.Button(parent, text="Begin next cycle", command=self.begin_next_cycle).pack(fill=tk.X, pady=(5, 2))
        ttk.Button(parent, text="Discharge selected to storage", command=self.discharge_selected).pack(fill=tk.X, pady=2)
        ttk.Label(parent, text="Stored assembly:").pack(anchor="w", pady=(5, 1))
        self.pool_assembly_box = ttk.Combobox(
            parent, textvariable=self.pool_assembly_var, state="readonly", width=25,
        )
        self.pool_assembly_box.pack(fill=tk.X)
        ttk.Button(parent, text="Load stored assembly at selected position", command=self.load_pool_to_selected).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="Open assembly inventory", command=self.show_assembly_inventory).pack(fill=tk.X, pady=2)
        state_row = ttk.Frame(parent, style="Panel.TFrame")
        state_row.pack(fill=tk.X, pady=(3, 0))
        ttk.Button(state_row, text="Save refueling state", command=self.save_refueling_state).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(state_row, text="Load state", command=self.load_refueling_state).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        ttk.Separator(parent).pack(fill=tk.X, pady=10)
        ttk.Label(parent, text="CYCLE EVOLUTION", style="Section.TLabel").pack(anchor="w")
        ttk.Label(parent, text="Full-power days per step:").pack(anchor="w", pady=(5, 1))
        ttk.Entry(parent, textvariable=self.cycle_days_var, width=12).pack(anchor="w")
        ttk.Label(parent, text="Animation delay (seconds):").pack(anchor="w", pady=(5, 1))
        ttk.Entry(parent, textvariable=self.animation_delay_var, width=12).pack(anchor="w")
        ttk.Label(parent, text="Stop at exposure (FPD):").pack(anchor="w", pady=(5, 1))
        ttk.Entry(parent, textvariable=self.stop_exposure_var, width=12).pack(anchor="w")
        ttk.Checkbutton(
            parent, text="Stop on k/peaking warning",
            variable=self.stop_on_warning_var,
        ).pack(anchor="w", pady=(5, 2))
        run_row = ttk.Frame(parent, style="Panel.TFrame")
        run_row.pack(fill=tk.X, pady=(5, 2))
        ttk.Button(run_row, text="Run cycle", command=self.run_cycle).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(run_row, text="Pause", command=self.pause_cycle).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        ttk.Button(parent, text="Single cycle step", command=self.advance_cycle).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="Reset burnup only", command=self.reset_burnup).pack(fill=tk.X, pady=2)

        ttk.Separator(parent).pack(fill=tk.X, pady=10)
        ttk.Button(parent, text="Export current core CSV", command=self.export_csv).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="About model", command=self.show_about).pack(fill=tk.X, pady=2)

        self._update_selected_description()

    def _build_core_canvas(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent, style="Panel.TFrame")
        bar.pack(fill=tk.X, pady=(0, 7))
        ttk.Label(bar, text="CORE LOADING MAP", style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(bar, text="RECALCULATE CURRENT STATE", command=self.calculate).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Checkbutton(bar, text="Show values", variable=self.show_numbers_var, command=self.refresh_core_canvas).pack(side=tk.RIGHT)

        canvas_width = GRID_SIZE * CELL_SIZE + 30
        canvas_height = GRID_SIZE * CELL_SIZE + 30
        map_frame = ttk.Frame(parent, style="Panel.TFrame")
        map_frame.pack(fill=tk.BOTH, expand=True)
        map_frame.grid_rowconfigure(0, weight=1)
        map_frame.grid_columnconfigure(0, weight=1)

        self.core_canvas = tk.Canvas(
            map_frame, width=canvas_width, height=canvas_height,
            bg="#090c10", highlightbackground="#56616d", highlightthickness=1,
            scrollregion=(0, 0, canvas_width, canvas_height),
        )
        core_vscroll = ttk.Scrollbar(map_frame, orient=tk.VERTICAL, command=self.core_canvas.yview)
        core_hscroll = ttk.Scrollbar(map_frame, orient=tk.HORIZONTAL, command=self.core_canvas.xview)
        self.core_canvas.configure(
            xscrollcommand=core_hscroll.set, yscrollcommand=core_vscroll.set,
        )
        self.core_canvas.grid(row=0, column=0, sticky="nsew")
        core_vscroll.grid(row=0, column=1, sticky="ns")
        core_hscroll.grid(row=1, column=0, sticky="ew")
        self.core_canvas.bind("<Button-1>", self.on_core_click)
        self.core_canvas.bind("<Shift-Button-1>", self.on_core_select)
        self.core_canvas.bind("<Button-3>", self.on_core_right_click)
        self.core_canvas.bind("<Motion>", self.on_core_motion)
        self.core_canvas.bind("<Leave>", lambda _e: self._clear_hover())

        self.hover_text = tk.StringVar(value="Click to place. Shift-click selects an assembly for history. Right-click clears.")
        tk.Label(
            parent, textvariable=self.hover_text, bg="#11161c", fg="#cbd7e1",
            anchor="w", padx=8, pady=6, font=("Segoe UI", 9),
        ).pack(fill=tk.X, pady=(7, 0))

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="RESULT DISPLAY", style="Section.TLabel").pack(anchor="w")
        modes = ttk.Frame(parent, style="Panel.TFrame")
        modes.pack(fill=tk.X, pady=(4, 6))
        ttk.Label(modes, text="Metric:").pack(side=tk.LEFT, padx=(0, 5))
        metric_box = ttk.Combobox(
            modes, textvariable=self.display_mode, state="readonly", width=22,
            values=(
                "Flux", "Fast flux", "Thermal flux", "Power", "Power index", "Power change: previous",
                "Power change: BOC", "Burnup", "Breeding", "Fuel temperature",
                "Moderator temperature", "Moderator density", "Xenon-135",
                "Samarium-149", "Control insertion",
            ),
        )
        metric_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        metric_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_all())
        ttk.Checkbutton(
            modes, text="Lock scale to BOC", variable=self.fixed_scale_var,
            command=self.refresh_all,
        ).pack(side=tk.LEFT, padx=(7, 0))

        view_bar = ttk.Frame(parent, style="Panel.TFrame")
        view_bar.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(view_bar, text="View:").pack(side=tk.LEFT, padx=(0, 5))
        for view in ("Top", "3D", "Split", "Trends"):
            ttk.Radiobutton(
                view_bar, text=view, variable=self.plot_view, value=view,
                command=self.refresh_plot,
            ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(view_bar, text="Reset camera", command=self.reset_camera).pack(side=tk.RIGHT)
        ttk.Label(view_bar, text="3D: drag to rotate, wheel to zoom").pack(side=tk.RIGHT, padx=(0, 8))

        self.figure = Figure(figsize=(5.65, 4.65), dpi=100, facecolor="#1c2128")
        self.plot_canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=False)
        self.plot_canvas.mpl_connect("scroll_event", self._on_plot_scroll)

        ttk.Label(parent, text="CORE INDICATORS", style="Section.TLabel").pack(anchor="w", pady=(8, 4))
        self.metric_vars: Dict[str, tk.StringVar] = {}
        metrics = [
            ("k", "Uncontrolled k-effective"),
            ("operating_k", "Controlled operating k"),
            ("boron", "Required soluble boron"),
            ("peak", "Radial power peak"),
            ("leak", "Leakage index"),
            ("conv", "Thorium conversion ratio"),
            ("ce", "Centre-to-edge flux ratio"),
            ("ns", "North-south flux tilt"),
            ("ew", "East-west flux tilt"),
            ("centroid", "Flux centroid offset"),
            ("fuel_temp", "Peak fuel temperature"),
            ("moderator_temp", "Peak moderator temperature"),
            ("density", "Minimum moderator density"),
            ("xenon", "Average Xe-135 index"),
            ("samarium", "Average Sm-149 index"),
            ("control", "Control-bank insertion"),
            ("control_worth", "Inserted control worth"),
            ("shutdown_k", "All-banks-in k"),
            ("shutdown_margin", "Shutdown margin"),
            ("avg_burn", "Average fuel burnup"),
            ("burn_spread", "Fuel burnup spread"),
            ("cycle_number", "Current fuel cycle"),
            ("selected_position", "Selected core position"),
            ("selected_id", "Selected assembly ID"),
            ("storage_count", "Assemblies in storage"),
            ("days", "Cycle exposure"),
            ("count", "Loaded assemblies"),
        ]
        for key, label in metrics:
            row = ttk.Frame(parent, style="Panel.TFrame")
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=25).pack(side=tk.LEFT)
            var = tk.StringVar(value="---")
            self.metric_vars[key] = var
            ttk.Label(row, textvariable=var, style="Value.TLabel", anchor="e", width=15).pack(side=tk.RIGHT)

        self.status_var = tk.StringVar()
        tk.Label(
            parent, textvariable=self.status_var, bg="#101419", fg="#f2e7b6",
            wraplength=430, justify=tk.LEFT, anchor="nw", padx=9, pady=8,
            font=("Segoe UI", 9),
        ).pack(fill=tk.X, pady=(8, 0))

    def _update_selected_description(self) -> None:
        spec = ASSEMBLY_TYPES[self.selected_type.get()]
        self.selected_description.set(
            f"{spec.name}\n\n{spec.notes}\n\n"
            f"Relative fissile strength: {spec.fissile:.2f}\n"
            f"Thorium fertile loading: {spec.fertile_th:.2f}\n"
            f"Initial burnup: {spec.initial_burnup:.1f} GWd/tHM"
        )

    def _canvas_cell(self, event: tk.Event) -> Optional[Tuple[int, int]]:
        x = self.core_canvas.canvasx(event.x)
        y = self.core_canvas.canvasy(event.y)
        col = int((x - 15) // CELL_SIZE)
        row = int((y - 15) // CELL_SIZE)
        if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
            return row, col
        return None

    def on_core_click(self, event: tk.Event) -> None:
        cell = self._canvas_cell(event)
        if cell is None:
            return
        r, c = cell
        if not self.model.mask[r, c]:
            return
        if self.refueling_mode_var.get():
            self._handle_refueling_click(cell)
            return
        self.pause_cycle()
        self.selected_cell = (r, c)
        self.model.set_assembly(r, c, self.selected_type.get())
        self.model.solve()
        self.model.record_assembly_histories("new_assembly_loaded")
        self._reset_history()
        self.refresh_all()

    def on_core_select(self, event: tk.Event) -> str:
        cell = self._canvas_cell(event)
        if cell is not None and self.model.mask[cell]:
            self.selected_cell = cell
            self.refresh_core_canvas()
            self.refresh_metrics()
            if self.plot_view.get() == "Trends":
                self.refresh_plot()
        return "break"

    def on_core_right_click(self, event: tk.Event) -> None:
        cell = self._canvas_cell(event)
        if cell is None:
            return
        r, c = cell
        if self.model.mask[r, c]:
            self.pause_cycle()
            self.selected_cell = (r, c)
            if self.refueling_mode_var.get():
                self.model.discharge_assembly(r, c)
                self.refuel_source = None
            else:
                self.model.set_assembly(r, c, "EMPTY")
                self.model.solve()
                self.model.record_assembly_histories("discharged")
            self._reset_history()
            self._refresh_pool_choices()
            self.refresh_all()

    def on_core_motion(self, event: tk.Event) -> None:
        cell = self._canvas_cell(event)
        if cell == self.hover_cell:
            return
        self.hover_cell = cell
        if cell is None:
            self.hover_text.set("Click to place. Shift-click selects an assembly for history. Right-click clears.")
            return
        r, c = cell
        if not self.model.mask[r, c]:
            self.hover_text.set(f"Row {r + 1}, column {c + 1}: outside the active-core mask.")
            return
        key = str(self.model.layout[r, c])
        spec = ASSEMBLY_TYPES[key]
        assembly_id = str(self.model.assembly_ids[r, c]) or "EMPTY"
        self.hover_text.set(
            f"{self.model.position_id(r, c)} | {assembly_id} | {spec.name} | burnup {self.model.burnup[r,c]:.1f} GWd/tHM | "
            f"flux {self.model.flux[r,c]:.3f} | power {self.model.power[r,c]:.3f}"
        )

    def _clear_hover(self) -> None:
        self.hover_cell = None
        self.hover_text.set("Click to place. Shift-click selects an assembly for history. Right-click clears.")

    def _display_field(self) -> Tuple[np.ndarray, str, str, str]:
        mode = self.display_mode.get()
        previous_power = self.history["power"][-2] if len(self.history.get("power", [])) >= 2 else self.model.power
        boc_power = self.history["power"][0] if self.history.get("power") else self.model.power
        return {
            "Flux": (self.model.flux, "Relative neutron flux", "Relative flux", "viridis"),
            "Fast flux": (self.model.fast_flux, "Fast-group neutron flux", "Relative fast flux", "plasma"),
            "Thermal flux": (self.model.thermal_flux, "Thermal-group neutron flux", "Relative thermal flux", "viridis"),
            "Power": (self.model.power, "Normalized assembly power", "Power / current core average", "inferno"),
            "Power index": (self.model.power_index, "Unnormalized assembly power index", "Fissile-weighted power index", "inferno"),
            "Power change: previous": (
                self.model.power - previous_power, "Power change since previous step",
                "Change in normalized power", "coolwarm",
            ),
            "Power change: BOC": (
                self.model.power - boc_power, "Power change since beginning of cycle",
                "Change in normalized power", "coolwarm",
            ),
            "Burnup": (self.model.burnup, "Assembly burnup", "GWd/tHM", "magma"),
            "Breeding": (self.model.breeding, "Thorium breeding index", "Relative U-233 production", "viridis"),
            "Fuel temperature": (self.model.fuel_temperature, "Assembly fuel temperature", "Fuel temperature (K)", "inferno"),
            "Moderator temperature": (self.model.moderator_temperature, "Assembly moderator temperature", "Moderator temperature (K)", "plasma"),
            "Moderator density": (self.model.moderator_density, "Relative moderator density", "Relative density", "viridis"),
            "Xenon-135": (self.model.xenon135_inventory, "Equilibrium Xe-135 poison", "Xe-135 inventory index", "cividis"),
            "Samarium-149": (self.model.samarium149_inventory, "Sm-149 poison inventory", "Sm-149 inventory index", "cividis"),
            "Control insertion": (self.model.control_fraction, "Symmetric control-bank insertion", "Inserted fraction", "Greys"),
        }[mode]

    def _display_limits(self, field: np.ndarray, mode: str) -> Tuple[Optional[float], Optional[float]]:
        active = self.model.mask & (self.model.layout != "EMPTY")
        if mode.startswith("Power change"):
            extent = float(np.max(np.abs(field[active]))) if np.any(active) else 1.0
            extent = max(extent, 1.0e-6)
            return -extent, extent
        if self.fixed_scale_var.get() and mode in self.display_scales:
            return self.display_scales[mode]
        return None, None

    def refresh_core_canvas(self) -> None:
        self.core_canvas.delete("all")
        mode = self.display_mode.get()
        field, _title, _label, _cmap = self._display_field()

        active_values = field[self.model.mask & (self.model.layout != "EMPTY")]
        vmin, vmax = self._display_limits(field, mode)
        field_max = vmax if vmax is not None else (float(np.max(active_values)) if active_values.size else 1.0)

        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                x0 = 15 + c * CELL_SIZE
                y0 = 15 + r * CELL_SIZE
                x1 = x0 + CELL_SIZE - 2
                y1 = y0 + CELL_SIZE - 2

                if not self.model.mask[r, c]:
                    self.core_canvas.create_rectangle(x0, y0, x1, y1, fill="#090c10", outline="#151a20")
                    continue

                key = str(self.model.layout[r, c])
                spec = ASSEMBLY_TYPES[key]
                base_color = spec.color
                if key == "EMPTY":
                    fill = "#171b20"
                elif mode.startswith("Power change"):
                    norm = (field[r, c] - float(vmin)) / max(float(vmax) - float(vmin), 1.0e-12)
                    fill = matplotlib.colors.to_hex(matplotlib.colormaps["coolwarm"](norm))
                else:
                    intensity = field[r, c] / max(field_max, 1.0e-12)
                    fill = self._blend_color(base_color, "#ffffff", 0.10 + 0.32 * intensity)

                selected = (r, c) == self.selected_cell
                refuel_source = (r, c) == self.refuel_source
                self.core_canvas.create_rectangle(
                    x0, y0, x1, y1, fill=fill,
                    outline="#ffd45c" if refuel_source else ("#7ee7ff" if selected else "#d9e1e8"),
                    width=3 if selected or refuel_source else 1,
                )
                self.core_canvas.create_text(
                    (x0 + x1) / 2, y0 + 15,
                    text=spec.short or "×", fill="#ffffff",
                    font=("Segoe UI", 10, "bold"),
                )
                if self.show_numbers_var.get() and key != "EMPTY":
                    if mode == "Burnup":
                        value_text = f"{field[r,c]:.1f}"
                    elif mode in ("Fuel temperature", "Moderator temperature"):
                        value_text = f"{field[r,c]:.0f}"
                    elif mode == "Control insertion":
                        value_text = f"{field[r,c]:.0%}"
                    elif mode.startswith("Power change"):
                        value_text = f"{field[r,c]:+.3f}"
                    else:
                        value_text = f"{field[r,c]:.3f}"
                    self.core_canvas.create_text(
                        (x0 + x1) / 2, y0 + 33,
                        text=value_text, fill="#071015",
                        font=("Consolas", 8, "bold"),
                    )

        for c in range(GRID_SIZE):
            self.core_canvas.create_text(
                15 + c * CELL_SIZE + CELL_SIZE / 2, 7,
                text=f"C{c + 1:02d}", fill="#aebdca", font=("Segoe UI", 7),
            )
        for r in range(GRID_SIZE):
            self.core_canvas.create_text(
                7, 15 + r * CELL_SIZE + CELL_SIZE / 2,
                text=f"R{r + 1:02d}", fill="#aebdca", font=("Segoe UI", 7), angle=90,
            )

    @staticmethod
    def _blend_color(color_a: str, color_b: str, fraction: float) -> str:
        fraction = max(0.0, min(1.0, fraction))
        a = tuple(int(color_a[i:i+2], 16) for i in (1, 3, 5))
        b = tuple(int(color_b[i:i+2], 16) for i in (1, 3, 5))
        rgb = tuple(round((1.0 - fraction) * x + fraction * y) for x, y in zip(a, b))
        return "#%02x%02x%02x" % rgb

    def _interpolated_surface(self, field: np.ndarray, mode: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return a display-only smooth field; it never feeds the core model."""
        points_mask = self.model.mask & (self.model.layout != "EMPTY")
        if mode.startswith("Power") or mode == "Burnup":
            points_mask &= self.model.layout != "REFL"
        point_rows, point_cols = np.where(points_mask)
        fine = np.linspace(0.0, GRID_SIZE - 1.0, 81)
        x_grid, y_grid = np.meshgrid(fine, fine)
        if point_rows.size == 0:
            return x_grid, y_grid, np.zeros_like(x_grid)

        # Smooth inverse-distance interpolation reproduces assembly-centre
        # values closely without adding another runtime dependency.
        dx = x_grid[..., None] - point_cols
        dy = y_grid[..., None] - point_rows
        distance_sq = dx * dx + dy * dy
        weights = 1.0 / np.maximum(distance_sq, 0.018)
        values = field[point_rows, point_cols]
        surface = np.sum(weights * values, axis=2) / np.sum(weights, axis=2)

        centre = (GRID_SIZE - 1) / 2.0
        radial_distance = np.hypot(x_grid - centre, y_grid - centre)
        outside = np.maximum(radial_distance - CORE_RADIUS, 0.0)
        if mode in ("Flux", "Fast flux", "Thermal flux"):
            surface *= np.exp(-1.15 * outside)
        elif mode.startswith("Power"):
            surface *= np.exp(-3.0 * outside)
        else:
            surface = np.where(radial_distance <= CORE_RADIUS, surface, 0.0)
        if mode.startswith("Power change"):
            return x_grid, y_grid, surface
        return x_grid, y_grid, np.maximum(surface, 0.0)

    def _style_plot_axis(self, axis, is_3d: bool = False) -> None:
        axis.set_xlabel("Core column", color="white")
        axis.set_ylabel("Core row", color="white")
        axis.tick_params(colors="white", labelsize=7)
        axis.set_facecolor("#11161c")
        if not is_3d:
            for spine in axis.spines.values():
                spine.set_color("white")

    def _apply_surface_zoom(self, axis) -> None:
        centre = (GRID_SIZE - 1) / 2.0
        half_span = 5.65 / max(self.surface_zoom, 1.0e-6)
        axis.set_xlim(centre - half_span, centre + half_span)
        axis.set_ylim(centre + half_span, centre - half_span)

    def _on_plot_scroll(self, event) -> None:
        axis = event.inaxes
        if axis is None or getattr(axis, "name", "") != "3d":
            return
        direction = getattr(event, "step", 0.0)
        if direction == 0.0:
            direction = 1.0 if getattr(event, "button", "") == "up" else -1.0
        factor = 1.16 if direction > 0.0 else 1.0 / 1.16
        self.surface_zoom = max(0.65, min(5.0, self.surface_zoom * factor))
        self._apply_surface_zoom(axis)
        self.plot_canvas.draw_idle()

    def _reset_history(self) -> None:
        self.history = {
            key: [] for key in (
                "days", "k", "operating_k", "boron", "peak", "leak", "conversion", "average_burnup",
                "flux", "fast_flux", "thermal_flux", "power", "power_index", "burnup", "breeding",
                "u235", "pu239", "poison", "pa233", "u233",
                "fuel_temperature", "moderator_temperature", "moderator_density",
                "xenon135", "samarium149", "control_fraction",
            )
        }
        self._record_history()
        self.display_scales = {}
        for mode, field in (
            ("Flux", self.model.flux), ("Fast flux", self.model.fast_flux),
            ("Thermal flux", self.model.thermal_flux), ("Power", self.model.power),
            ("Power index", self.model.power_index), ("Burnup", self.model.burnup),
            ("Breeding", self.model.breeding),
            ("Fuel temperature", self.model.fuel_temperature),
            ("Moderator temperature", self.model.moderator_temperature),
            ("Moderator density", self.model.moderator_density),
            ("Xenon-135", self.model.xenon135_inventory),
            ("Samarium-149", self.model.samarium149_inventory),
            ("Control insertion", self.model.control_fraction),
        ):
            active = self.model.mask & (self.model.layout != "EMPTY")
            upper = float(np.max(field[active])) if np.any(active) else 1.0
            self.display_scales[mode] = (0.0, max(upper, 1.0e-9))

    def _record_history(self) -> None:
        fuel = self.model.mask & (self.model.layout != "EMPTY") & (self.model.layout != "REFL")
        average_burnup = float(np.mean(self.model.burnup[fuel])) if np.any(fuel) else 0.0
        self.history["days"].append(float(self.model.cycle_days))
        self.history["k"].append(float(self.model.k_eff))
        self.history["operating_k"].append(float(self.model.operating_k_eff))
        self.history["boron"].append(float(self.model.required_boron_ppm))
        self.history["peak"].append(float(self.model.radial_peaking))
        self.history["leak"].append(float(self.model.leakage_index))
        self.history["conversion"].append(float(self.model.conversion_ratio))
        self.history["average_burnup"].append(average_burnup)
        for key, field in (
            ("flux", self.model.flux), ("fast_flux", self.model.fast_flux),
            ("thermal_flux", self.model.thermal_flux), ("power", self.model.power),
            ("power_index", self.model.power_index), ("burnup", self.model.burnup),
            ("breeding", self.model.breeding), ("pa233", self.model.pa233_inventory),
            ("u233", self.model.u233_inventory), ("u235", self.model.u235_inventory),
            ("pu239", self.model.pu239_inventory), ("poison", self.model.poison_inventory),
            ("fuel_temperature", self.model.fuel_temperature),
            ("moderator_temperature", self.model.moderator_temperature),
            ("moderator_density", self.model.moderator_density),
            ("xenon135", self.model.xenon135_inventory),
            ("samarium149", self.model.samarium149_inventory),
            ("control_fraction", self.model.control_fraction),
        ):
            self.history[key].append(field.copy())

    def _plot_trends(self) -> None:
        days = np.asarray(self.history["days"], dtype=float)
        core_axis = self.figure.add_subplot(2, 2, 1)
        burn_core_axis = self.figure.add_subplot(2, 2, 2)
        assembly_axis = self.figure.add_subplot(2, 2, 3)
        inventory_axis = self.figure.add_subplot(2, 2, 4)
        for axis in (core_axis, burn_core_axis, assembly_axis, inventory_axis):
            axis.set_facecolor("#11161c")
            axis.tick_params(colors="white", labelsize=7)
            axis.grid(True, color="#39434d", alpha=0.45)
            for spine in axis.spines.values():
                spine.set_color("white")

        core_axis.plot(days, self.history["k"], label="uncontrolled k", color="#7ee7ff")
        core_axis.plot(days, self.history["operating_k"], label="operating k", color="#ffffff", linestyle="--")
        core_axis.plot(days, self.history["peak"], label="power peak", color="#ff9f55")
        core_axis.plot(days, self.history["conversion"], label="conversion", color="#77dd88")
        core_axis.set_title("Core cycle history", color="white", fontsize=10, fontweight="bold")
        core_axis.set_ylabel("Relative indicator", color="white")
        core_axis.legend(loc="best", fontsize=7, facecolor="#1c2128", labelcolor="white")

        burn_core_axis.plot(days, self.history["average_burnup"], color="#e5c95c", label="average burnup")
        boron_axis = burn_core_axis.twinx()
        boron_axis.plot(days, self.history["boron"], color="#c58cff", label="required boron")
        boron_axis.set_ylabel("Illustrative boron (ppm)", color="#c58cff")
        boron_axis.tick_params(colors="#c58cff", labelsize=7)
        burn_core_axis.set_title("Exposure indicators", color="white", fontsize=10, fontweight="bold")
        burn_core_axis.set_ylabel("Burnup / leakage", color="white")
        burn_core_axis.legend(loc="best", fontsize=7, facecolor="#1c2128", labelcolor="white")
        boron_axis.legend(loc="upper right", fontsize=7, facecolor="#1c2128", labelcolor="white")

        r, c = self.selected_cell
        assembly_id = str(self.model.assembly_ids[r, c])
        record = self.model.assembly_registry.get(assembly_id)
        if record is not None and record.history:
            entries = record.history
            assembly_days = np.asarray([float(entry.get("total_fpd", 0.0)) for entry in entries])
            flux = [float(entry.get("flux", 0.0)) for entry in entries]
            power = [float(entry.get("power", 0.0)) for entry in entries]
            burnup = [float(entry.get("burnup", 0.0)) for entry in entries]
            pa233 = [float(entry.get("pa233_inventory", 0.0)) for entry in entries]
            u233 = [float(entry.get("u233_inventory", 0.0)) for entry in entries]
            u235 = [float(entry.get("u235_inventory", 0.0)) for entry in entries]
            pu239 = [float(entry.get("pu239_inventory", 0.0)) for entry in entries]
            xenon = [float(entry.get("xenon135_inventory", 0.0)) for entry in entries]
            samarium = [float(entry.get("samarium149_inventory", 0.0)) for entry in entries]
        else:
            assembly_days = days
            flux = [float(snapshot[r, c]) for snapshot in self.history["flux"]]
            power = [float(snapshot[r, c]) for snapshot in self.history["power"]]
            burnup = [float(snapshot[r, c]) for snapshot in self.history["burnup"]]
            pa233 = [float(snapshot[r, c]) for snapshot in self.history["pa233"]]
            u233 = [float(snapshot[r, c]) for snapshot in self.history["u233"]]
            u235 = [float(snapshot[r, c]) for snapshot in self.history["u235"]]
            pu239 = [float(snapshot[r, c]) for snapshot in self.history["pu239"]]
            xenon = [float(snapshot[r, c]) for snapshot in self.history["xenon135"]]
            samarium = [float(snapshot[r, c]) for snapshot in self.history["samarium149"]]
        assembly_axis.plot(assembly_days, flux, label="flux", color="#58b7ff")
        assembly_axis.plot(assembly_days, power, label="power", color="#ff665f")
        assembly_axis.set_title(
            f"{assembly_id or 'Empty'} at {self.model.position_id(r, c)}",
            color="white", fontsize=9, fontweight="bold",
        )
        assembly_axis.set_xlabel("Full-power days", color="white")
        assembly_axis.set_ylabel("Relative flux / power", color="white")
        assembly_axis.legend(loc="upper left", fontsize=7, facecolor="#1c2128", labelcolor="white")

        inventory_axis.plot(assembly_days, burnup, label="burnup", color="#e5c95c")
        inventory_axis.set_title("Selected assembly depletion", color="white", fontsize=9, fontweight="bold")
        inventory_axis.set_xlabel("Full-power days", color="white")
        inventory_axis.set_ylabel("Burnup (GWd/tHM)", color="#e5c95c")
        isotope_axis = inventory_axis.twinx()
        isotope_axis.plot(assembly_days, pa233, label="Pa-233", color="#c58cff", linestyle="--")
        isotope_axis.plot(assembly_days, u233, label="U-233", color="#77dd88", linestyle=":")
        isotope_axis.plot(assembly_days, u235, label="U-235", color="#58b7ff", linestyle="-.")
        isotope_axis.plot(assembly_days, pu239, label="Pu-239", color="#ff9f55", linestyle="--")
        isotope_axis.plot(assembly_days, xenon, label="Xe-135", color="#f06cff", linestyle=":")
        isotope_axis.plot(assembly_days, samarium, label="Sm-149", color="#b8b8b8", linestyle="-.")
        isotope_axis.set_ylabel("Inventory index", color="#9fe7b0")
        isotope_axis.tick_params(colors="#9fe7b0", labelsize=7)
        inventory_axis.legend(loc="upper left", fontsize=7, facecolor="#1c2128", labelcolor="white")
        isotope_axis.legend(loc="upper right", fontsize=7, facecolor="#1c2128", labelcolor="white")
        self.figure.subplots_adjust(left=0.10, right=0.90, top=0.94, bottom=0.10, hspace=0.55, wspace=0.38)

    def refresh_plot(self) -> None:
        # Preserve the user's rotation when recalculating or changing metrics.
        for axis in self.figure.axes:
            if getattr(axis, "name", "") == "3d":
                self.surface_elev, self.surface_azim = axis.elev, axis.azim
        self.figure.clear()
        if self.plot_view.get() == "Trends":
            self._plot_trends()
            self.plot_canvas.draw_idle()
            return
        mode = self.display_mode.get()
        field, title, label, cmap = self._display_field()
        vmin, vmax = self._display_limits(field, mode)

        masked = np.ma.masked_where(~self.model.mask | (self.model.layout == "EMPTY"), field)
        view = self.plot_view.get()
        color_mappable = None
        if view in ("Top", "Split"):
            top_axis = self.figure.add_subplot(1, 2, 1) if view == "Split" else self.figure.add_subplot(111)
            color_mappable = top_axis.imshow(
                masked, origin="upper", interpolation="nearest", cmap=cmap,
                vmin=vmin, vmax=vmax,
            )
            top_axis.set_title(title if view == "Top" else "Calculated top view", color="white", fontweight="bold", fontsize=10)
            top_axis.set_xticks(range(GRID_SIZE), labels=[str(i + 1) for i in range(GRID_SIZE)])
            top_axis.set_yticks(range(GRID_SIZE), labels=[str(i + 1) for i in range(GRID_SIZE)])
            self._style_plot_axis(top_axis)

        if view in ("3D", "Split"):
            surface_axis = self.figure.add_subplot(1, 2, 2, projection="3d") if view == "Split" else self.figure.add_subplot(111, projection="3d")
            x_grid, y_grid, surface = self._interpolated_surface(field, mode)
            color_mappable = surface_axis.plot_surface(
                x_grid, y_grid, surface, cmap=cmap, linewidth=0,
                antialiased=True, rcount=81, ccount=81, vmin=vmin, vmax=vmax,
            )
            theta = np.linspace(0.0, 2.0 * math.pi, 200)
            boundary_x = (GRID_SIZE - 1) / 2.0 + CORE_RADIUS * np.cos(theta)
            boundary_y = (GRID_SIZE - 1) / 2.0 + CORE_RADIUS * np.sin(theta)
            surface_axis.plot(boundary_x, boundary_y, np.zeros_like(theta), color="white", linewidth=1.0, alpha=0.8)
            surface_axis.set_title("Interpolated surface", color="white", fontweight="bold", fontsize=10)
            surface_axis.set_zlabel(label, color="white", fontsize=8)
            surface_axis.view_init(elev=self.surface_elev, azim=self.surface_azim)
            self._apply_surface_zoom(surface_axis)
            self._style_plot_axis(surface_axis, is_3d=True)

        self.figure.suptitle(
            "Interpolated display; only assembly-centre values are calculated" if view != "Top" else "",
            color="#cbd5de", fontsize=8,
        )
        if color_mappable is not None:
            cbar = self.figure.colorbar(color_mappable, ax=self.figure.axes, fraction=0.035, pad=0.05)
            cbar.set_label(label, color="white", fontsize=8)
            cbar.ax.tick_params(colors="white", labelsize=7)
        self.plot_canvas.draw_idle()

    def reset_camera(self) -> None:
        self.surface_elev = 28.0
        self.surface_azim = -55.0
        self.surface_zoom = 1.0
        self.refresh_plot()

    def refresh_metrics(self) -> None:
        counts = self.model.assembly_counts()
        loaded = sum(value for key, value in counts.items() if key != "EMPTY")
        self.metric_vars["k"].set(f"{self.model.k_eff:.4f}")
        self.metric_vars["operating_k"].set(f"{self.model.operating_k_eff:.4f}")
        self.metric_vars["boron"].set(f"{self.model.required_boron_ppm:.0f} ppm")
        self.metric_vars["peak"].set(f"{self.model.radial_peaking:.3f}")
        self.metric_vars["leak"].set(f"{self.model.leakage_index:.3f}")
        self.metric_vars["conv"].set(f"{self.model.conversion_ratio:.3f}")
        self.metric_vars["ce"].set(f"{self.model.centre_edge_ratio:.3f}")
        self.metric_vars["ns"].set(f"{self.model.north_south_tilt:+.3f}")
        self.metric_vars["ew"].set(f"{self.model.east_west_tilt:+.3f}")
        self.metric_vars["centroid"].set(f"{self.model.flux_centroid_offset:.3f} cells")
        fuel = self.model.mask & (self.model.layout != "EMPTY") & (self.model.layout != "REFL")
        active = self.model.mask & (self.model.layout != "EMPTY")
        self.metric_vars["fuel_temp"].set(f"{float(np.max(self.model.fuel_temperature[fuel])) if np.any(fuel) else 0.0:.0f} K")
        self.metric_vars["moderator_temp"].set(f"{float(np.max(self.model.moderator_temperature[active])) if np.any(active) else 0.0:.0f} K")
        self.metric_vars["density"].set(f"{float(np.min(self.model.moderator_density[active])) if np.any(active) else 0.0:.3f}")
        self.metric_vars["xenon"].set(f"{float(np.mean(self.model.xenon135_inventory[fuel])) if np.any(fuel) else 0.0:.3f}")
        self.metric_vars["samarium"].set(f"{float(np.mean(self.model.samarium149_inventory[fuel])) if np.any(fuel) else 0.0:.3f}")
        insertion = 100.0 * float(np.max(self.model.control_fraction))
        self.metric_vars["control"].set(f"{insertion:.1f}%")
        self.metric_vars["control_worth"].set(f"{self.model.control_worth_pcm:.0f} pcm")
        self.metric_vars["shutdown_k"].set(f"{self.model.shutdown_k_eff:.4f}")
        self.metric_vars["shutdown_margin"].set(f"{self.model.shutdown_margin_pcm:.0f} pcm")
        average_burnup = float(np.mean(self.model.burnup[fuel])) if np.any(fuel) else 0.0
        burnup_spread = float(np.std(self.model.burnup[fuel])) if np.any(fuel) else 0.0
        self.metric_vars["avg_burn"].set(f"{average_burnup:.2f} GWd/tHM")
        self.metric_vars["burn_spread"].set(f"{burnup_spread:.2f} GWd/tHM")
        self.metric_vars["cycle_number"].set(str(self.model.cycle_number))
        self.metric_vars["selected_position"].set(self.model.position_id(*self.selected_cell))
        self.metric_vars["selected_id"].set(str(self.model.assembly_ids[self.selected_cell]) or "EMPTY")
        self.metric_vars["storage_count"].set(str(len(self.model.storage_ids())))
        self.metric_vars["days"].set(f"{self.model.cycle_days:.1f} d")
        self.metric_vars["count"].set(str(loaded))

        warnings: List[str] = []
        if self.model.k_eff < 0.995:
            warnings.append("Uncontrolled k is below the illustrative end-of-cycle range; no boron compensation remains.")
        elif self.model.k_eff > 1.10:
            warnings.append("Large uncontrolled excess reactivity in the teaching estimate.")
        elif self.model.k_eff >= 1.0:
            warnings.append(
                f"Illustrative boron control holds operating k at 1.0000; required boron is {self.model.required_boron_ppm:.0f} ppm."
            )
        else:
            warnings.append("Uncontrolled k is approaching the illustrative end-of-cycle condition.")

        if self.model.radial_peaking > 2.10:
            warnings.append("Power peaking is high; redistribute strong fissile assemblies.")
        else:
            warnings.append("Radial power peaking is moderate for this simplified model.")

        peak_fuel_temperature = float(np.max(self.model.fuel_temperature[fuel])) if np.any(fuel) else 0.0
        if peak_fuel_temperature > 1800.0:
            warnings.append("Illustrative fuel-temperature warning threshold exceeded.")
        if self.model.shutdown_margin_pcm < 500.0 and np.any(fuel):
            warnings.append("All-banks-in shutdown margin is small in the teaching estimate.")

        if counts["TH"] + counts["SEED"] > 0:
            warnings.append(
                f"Thorium-bearing positions: {counts['TH'] + counts['SEED']}; "
                f"conversion ratio proxy: {self.model.conversion_ratio:.2f}."
            )
        else:
            warnings.append("No thorium-bearing assemblies are currently loaded.")

        self.status_var.set(" ".join(warnings))

    def refresh_all(self) -> None:
        self.refresh_core_canvas()
        self.refresh_plot()
        self.refresh_metrics()

    def calculate(self) -> None:
        try:
            self.model.solve()
        except Exception as exc:
            messagebox.showerror("Calculation failed", str(exc))
            return
        self.refresh_all()

    def _refresh_pool_choices(self) -> None:
        values = self.model.storage_ids()
        if hasattr(self, "pool_assembly_box"):
            self.pool_assembly_box.configure(values=values)
        if self.pool_assembly_var.get() not in values:
            self.pool_assembly_var.set(values[0] if values else "")

    def toggle_refueling_mode(self) -> None:
        self.pause_cycle()
        self.refuel_source = None
        self.refresh_core_canvas()
        if self.refueling_mode_var.get():
            self.status_var.set("Refueling mode: click an occupied source position, then click a target to move or swap it.")
        else:
            self.status_var.set("Refueling mode closed. Ordinary clicks place newly created palette assemblies.")

    def open_refueling_workspace(self) -> None:
        self.pause_cycle()
        RefuelingWorkspace(self)

    def _handle_refueling_click(self, cell: Tuple[int, int]) -> None:
        self.pause_cycle()
        self.selected_cell = cell
        if self.refuel_source is None:
            if not str(self.model.assembly_ids[cell]):
                self.status_var.set(f"{self.model.position_id(*cell)} is empty; select an occupied source position.")
                self.refresh_core_canvas()
                return
            self.refuel_source = cell
            assembly_id = str(self.model.assembly_ids[cell])
            self.status_var.set(
                f"Selected {assembly_id} at {self.model.position_id(*cell)}. Click a target position to move or swap it."
            )
            self.refresh_core_canvas()
            return
        source = self.refuel_source
        try:
            self.model.move_or_swap_assemblies(source, cell)
        except ValueError as exc:
            messagebox.showwarning("Refueling move", str(exc))
            return
        self.refuel_source = None
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()
        self.status_var.set(
            f"Completed refueling move/swap between {self.model.position_id(*source)} and {self.model.position_id(*cell)}."
        )

    def discharge_selected(self) -> None:
        self.pause_cycle()
        assembly_id = self.model.discharge_assembly(*self.selected_cell)
        if assembly_id is None:
            messagebox.showwarning("Discharge assembly", "The selected core position is empty.")
            return
        self.refuel_source = None
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()
        self.status_var.set(f"Discharged {assembly_id} from {self.model.position_id(*self.selected_cell)} to storage.")

    def load_pool_to_selected(self) -> None:
        self.pause_cycle()
        assembly_id = self.pool_assembly_var.get()
        if not assembly_id:
            messagebox.showwarning("Load stored assembly", "No stored assembly is selected.")
            return
        try:
            self.model.load_stored_assembly(assembly_id, *self.selected_cell)
        except ValueError as exc:
            messagebox.showwarning("Load stored assembly", str(exc))
            return
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()
        self.status_var.set(f"Loaded {assembly_id} at {self.model.position_id(*self.selected_cell)} with its prior state preserved.")

    def begin_next_cycle(self) -> None:
        self.pause_cycle()
        try:
            outage_days = float(self.outage_days_var.get())
            if not math.isfinite(outage_days) or outage_days < 0.0:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showwarning("Invalid outage duration", "Enter a non-negative outage duration in days.")
            return
        self.model.begin_next_cycle(outage_days)
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()
        self.status_var.set(
            f"Started cycle {self.model.cycle_number} after a {outage_days:g}-day outage; assembly burnup and long-lived inventories were retained."
        )

    def show_assembly_inventory(self) -> None:
        self.model.sync_assembly_registry()
        window = tk.Toplevel(self.root)
        window.title("Assembly inventory and position register")
        window.geometry("1000x520")
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        columns = ("id", "type", "status", "position", "burnup", "cycles", "power", "history")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "id": "Assembly ID", "type": "Type", "status": "Status",
            "position": "Core position", "burnup": "Burnup (GWd/tHM)",
            "cycles": "Cycles", "power": "Last power", "history": "History points",
        }
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=115, anchor="center")
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        for assembly_id, record in sorted(self.model.assembly_registry.items()):
            last = record.history[-1] if record.history else {}
            tree.insert("", tk.END, iid=assembly_id, values=(
                assembly_id, ASSEMBLY_TYPES[record.assembly_type].name, record.status,
                record.position or "—", f"{record.state.get('burnup', 0.0):.2f}",
                record.cycles_completed, f"{last.get('power', 0.0):.3f}", len(record.history),
            ))

        buttons = ttk.Frame(window, padding=(10, 0, 10, 10))
        buttons.pack(fill=tk.X)

        def selected_id() -> Optional[str]:
            selection = tree.selection()
            return selection[0] if selection else None

        def locate_or_choose() -> None:
            assembly_id = selected_id()
            if not assembly_id:
                return
            record = self.model.assembly_registry[assembly_id]
            if record.status == "in_core":
                cell = self.model._locate_assembly(assembly_id)
                if cell is not None:
                    self.selected_cell = cell
                    self.refresh_core_canvas()
            else:
                self.pool_assembly_var.set(assembly_id)
            window.destroy()

        def show_history() -> None:
            assembly_id = selected_id()
            if assembly_id:
                self.show_assembly_history(assembly_id)

        ttk.Button(buttons, text="Locate / choose assembly", command=locate_or_choose).pack(side=tk.LEFT)
        ttk.Button(buttons, text="View complete history", command=show_history).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side=tk.RIGHT)
        tree.bind("<Double-1>", lambda _event: show_history())

    def show_assembly_history(self, assembly_id: str) -> None:
        record = self.model.assembly_registry[assembly_id]
        window = tk.Toplevel(self.root)
        window.title(f"Assembly history — {assembly_id}")
        window.geometry("1120x500")
        columns = ("cycle", "total", "event", "status", "position", "burnup", "flux", "power", "u235", "pu239")
        tree = ttk.Treeview(window, columns=columns, show="headings")
        labels = ("Cycle", "Total FPD", "Event", "Status", "Position", "Burnup", "Flux", "Power", "U-235", "Pu-239")
        for column, label in zip(columns, labels):
            tree.heading(column, text=label)
            tree.column(column, width=105, anchor="center")
        scrollbar = ttk.Scrollbar(window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        for entry in record.history:
            tree.insert("", tk.END, values=(
                entry.get("cycle"), f"{entry.get('total_fpd', 0.0):.1f}", entry.get("event"),
                entry.get("status"), entry.get("position") or "—",
                f"{entry.get('burnup', 0.0):.2f}", f"{entry.get('flux', 0.0):.3f}",
                f"{entry.get('power', 0.0):.3f}", f"{entry.get('u235_inventory', 0.0):.4f}",
                f"{entry.get('pu239_inventory', 0.0):.4f}",
            ))

    def save_refueling_state(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save core and assembly inventory",
            defaultextension=".json", initialfile="core_refueling_state.json",
            filetypes=(("JSON state files", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            self.model.save_state(path)
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror("Save state failed", str(exc))
            return
        messagebox.showinfo("State saved", f"Saved core, pool, and assembly histories to:\n{path}")

    def load_refueling_state(self) -> None:
        path = filedialog.askopenfilename(
            title="Load core and assembly inventory",
            filetypes=(("JSON state files", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        self.pause_cycle()
        try:
            self.model.load_state(path)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("Load state failed", str(exc))
            return
        self.refuel_source = None
        self.control_insertion_var.set(100.0 * float(np.max(self.model.control_fraction)))
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()
        self.status_var.set(f"Loaded cycle {self.model.cycle_number} core and persistent assembly inventory.")

    def preset_pwr(self) -> None:
        self.pause_cycle()
        self.model.load_conventional_pwr()
        self.refuel_source = None
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()

    def apply_control_insertion(self) -> None:
        self.pause_cycle()
        try:
            insertion = float(self.control_insertion_var.get())
            if not math.isfinite(insertion) or not 0.0 <= insertion <= 100.0:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showwarning("Invalid control insertion", "Enter a value from 0 to 100 percent.")
            return
        self.model.set_control_insertion(insertion)
        self._reset_history()
        self.refresh_all()
        self.status_var.set(f"Applied {insertion:.1f}% symmetric control-bank insertion and recalculated boron control.")

    def withdraw_control_banks(self) -> None:
        self.control_insertion_var.set(0.0)
        self.apply_control_insertion()

    def preset_seed_blanket(self) -> None:
        self.pause_cycle()
        self.model.load_thorium_seed_blanket()
        self.refuel_source = None
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()

    def preset_checkerboard(self) -> None:
        self.pause_cycle()
        self.model.load_thorium_checkerboard()
        self.refuel_source = None
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()

    def clear_core(self) -> None:
        self.pause_cycle()
        self.model.clear_core()
        self.refuel_source = None
        self._reset_history()
        self._refresh_pool_choices()
        self.refresh_all()

    def _cycle_settings(self) -> Optional[Tuple[float, float, float]]:
        try:
            days = float(self.cycle_days_var.get())
            delay = float(self.animation_delay_var.get())
            stop_exposure = float(self.stop_exposure_var.get())
            if not all(math.isfinite(value) for value in (days, delay, stop_exposure)):
                raise ValueError
            if days <= 0.0 or delay < 0.05 or stop_exposure <= 0.0:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showwarning(
                "Invalid cycle controls",
                "Enter positive full-power days and stop exposure, and an animation delay of at least 0.05 seconds.",
            )
            return None
        return days, delay, stop_exposure

    def _advance_cycle_once(self, days: float) -> bool:
        fuel = self.model.mask & (self.model.layout != "EMPTY") & (self.model.layout != "REFL")
        if not np.any(fuel):
            messagebox.showwarning("No fuel loaded", "Load at least one fuel assembly before advancing the cycle.")
            return False
        self.model.advance_cycle(days)
        self._record_history()
        self.refresh_all()
        return True

    def advance_cycle(self) -> None:
        self.pause_cycle()
        settings = self._cycle_settings()
        if settings is None:
            return
        days, _delay, _stop_exposure = settings
        if self._advance_cycle_once(days):
            self.status_var.set(f"Advanced one {days:g}-FPD cycle step. Select Trends to inspect progression.")

    def run_cycle(self) -> None:
        if self.running:
            return
        settings = self._cycle_settings()
        if settings is None:
            return
        _days, _delay, stop_exposure = settings
        if self.model.cycle_days >= stop_exposure:
            messagebox.showwarning(
                "Stop exposure reached",
                "Set a stop exposure greater than the current cycle exposure.",
            )
            return
        self.running = True
        self.status_var.set("Cycle evolution running...")
        self.run_after_id = self.root.after(0, self._run_cycle_tick)

    def pause_cycle(self) -> None:
        was_running = self.running
        self.running = False
        if self.run_after_id is not None:
            try:
                self.root.after_cancel(self.run_after_id)
            except tk.TclError:
                pass
            self.run_after_id = None
        if was_running:
            self.status_var.set(f"Cycle evolution paused at {self.model.cycle_days:.1f} FPD.")

    def _run_cycle_tick(self) -> None:
        self.run_after_id = None
        if not self.running:
            return
        settings = self._cycle_settings()
        if settings is None:
            self.pause_cycle()
            return
        days, delay, stop_exposure = settings
        remaining = stop_exposure - self.model.cycle_days
        step_days = min(days, remaining)
        if step_days <= 0.0 or not self._advance_cycle_once(step_days):
            self.pause_cycle()
            return

        stop_reason = ""
        if self.model.cycle_days >= stop_exposure - 1.0e-9:
            stop_reason = f"Reached the requested {stop_exposure:g}-FPD exposure."
        elif self.stop_on_warning_var.get():
            if self.model.k_eff < 0.995 or self.model.k_eff > 1.10:
                stop_reason = f"Uncontrolled k-effective warning threshold reached ({self.model.k_eff:.4f})."
            elif self.model.radial_peaking > 2.10:
                stop_reason = f"Radial power peaking warning threshold reached ({self.model.radial_peaking:.3f})."

        if stop_reason:
            self.running = False
            self.status_var.set(f"Cycle evolution stopped. {stop_reason}")
            return

        self.status_var.set(
            f"Cycle evolution running: {self.model.cycle_days:.1f} / {stop_exposure:g} FPD."
        )
        self.run_after_id = self.root.after(max(50, int(delay * 1000.0)), self._run_cycle_tick)

    def reset_burnup(self) -> None:
        self.pause_cycle()
        self.model.reset_depletion()
        self._reset_history()
        self.refresh_all()

    def export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export core loading and results",
            defaultextension=".csv",
            initialfile="core_loading_results.csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            count = self.model.export_csv(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Export complete", f"Exported {count} active-core positions to:\n{path}")

    def show_about(self) -> None:
        messagebox.showinfo(
            "About this simulator",
            "This application provides an interactive core-loading teaching workflow.\n\n"
            "The solver is an assembly-level two-group diffusion eigenvalue model with classroom-scaled cross sections. "
            "It is intended to reveal qualitative relationships among loading pattern, flux, power, leakage, "
            "burnup, soluble-boron control, plutonium production and thorium breeding.\n\n"
            "It must not be used for reactor design, licensing, criticality safety, fuel management decisions, "
            "or prediction of an actual reactor core.",
        )


class RefuelingWorkspace:
    """Transactional staging-rack workspace for building the next-cycle core."""

    CELL = 48
    MARGIN = 28

    def __init__(self, app: CoreLoadingApp) -> None:
        self.app = app
        self.original = copy.deepcopy(app.model)
        self.draft = copy.deepcopy(app.model)
        self.undo_stack: List[CoreModel] = []
        self.redo_stack: List[CoreModel] = []
        self.active_token: Optional[str] = None
        self.core_source: Optional[Tuple[int, int]] = None
        self.unloaded = False
        self.outage_var = tk.DoubleVar(value=float(app.outage_days_var.get()))
        self.detail_var = tk.StringVar(value="Select an assembly card or an in-core assembly.")
        self.status_var = tk.StringVar(value="Unload the outgoing core to begin constructing the reload.")

        self.window = tk.Toplevel(app.root)
        self.window.title("Guided Refueling Workspace — Draft Next-Cycle Loading")
        self.window.geometry("1540x900")
        self.window.minsize(800, 620)
        self.window.configure(bg="#0f1115")
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        toolbar_shell = ttk.Frame(self.window)
        toolbar_shell.pack(fill=tk.X)
        toolbar_canvas = tk.Canvas(
            toolbar_shell, height=46, bg="#0f1115", highlightthickness=0,
            borderwidth=0,
        )
        toolbar_scroll = ttk.Scrollbar(
            toolbar_shell, orient=tk.HORIZONTAL, command=toolbar_canvas.xview,
        )
        toolbar_canvas.configure(xscrollcommand=toolbar_scroll.set)
        toolbar_canvas.pack(fill=tk.X, expand=True)
        toolbar_scroll.pack(fill=tk.X)
        toolbar = ttk.Frame(toolbar_canvas, padding=8)
        toolbar_window = toolbar_canvas.create_window((0, 0), window=toolbar, anchor="nw")
        toolbar.bind(
            "<Configure>",
            lambda _event: toolbar_canvas.configure(scrollregion=toolbar_canvas.bbox("all")),
        )
        toolbar_canvas.bind(
            "<Configure>",
            lambda event: toolbar_canvas.itemconfigure(
                toolbar_window, height=max(event.height, toolbar.winfo_reqheight()),
            ),
        )
        ttk.Button(toolbar, text="1  Unload core to staging", command=self.unload_core).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Redo", command=self.redo).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Validate loading", command=self.validate_dialog).pack(side=tk.LEFT, padx=(12, 2))
        ttk.Button(toolbar, text="Preview EOC → BOC", command=self.preview).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="Outage days:").pack(side=tk.LEFT, padx=(14, 3))
        ttk.Entry(toolbar, textvariable=self.outage_var, width=8).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="COMMIT LOADING AND BEGIN NEXT CYCLE", command=self.commit).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=2)

        body = tk.PanedWindow(
            self.window, orient=tk.HORIZONTAL, bg="#56616d", bd=0,
            sashwidth=8, sashrelief=tk.RAISED, showhandle=True,
        )
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body, style="Panel.TFrame", padding=8)
        centre = ttk.Frame(body, style="Panel.TFrame", padding=8)
        right_shell = ttk.Frame(body, style="Panel.TFrame")
        body.add(left, minsize=210, width=410, stretch="always")
        body.add(centre, minsize=240, width=680, stretch="always")
        body.add(right_shell, minsize=210, width=410, stretch="always")
        self.workspace_panes = body

        right_canvas = tk.Canvas(
            right_shell, bg="#1c2128", highlightthickness=0, borderwidth=0,
        )
        right_scroll = ttk.Scrollbar(right_shell, orient=tk.VERTICAL, command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_scroll.set)
        right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        right = ttk.Frame(right_canvas, style="Panel.TFrame", padding=8)
        right_window = right_canvas.create_window((0, 0), window=right, anchor="nw")
        right.bind(
            "<Configure>",
            lambda _event: right_canvas.configure(scrollregion=right_canvas.bbox("all")),
        )
        right_canvas.bind(
            "<Configure>",
            lambda event: right_canvas.itemconfigure(right_window, width=event.width),
        )
        self.workspace_right_canvas = right_canvas

        ttk.Label(left, text="STAGING RACKS", style="Section.TLabel").pack(anchor="w")
        self.notebook = ttk.Notebook(left, width=390)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(6, 4))
        self.rack_trees: Dict[str, ttk.Treeview] = {}
        for category, label in (
            ("once", "Once burned"), ("twice", "Twice burned"),
            ("special", "Special / extended"), ("new", "New fuel supply"),
            ("spent", "Spent pool"),
        ):
            self._build_rack_tab(category, label)
        rack_buttons = ttk.Frame(left, style="Panel.TFrame")
        rack_buttons.pack(fill=tk.X)
        ttk.Button(rack_buttons, text="Mark selected as spent", command=self.mark_spent).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(rack_buttons, text="Clear selection", command=self.clear_selection).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        ttk.Label(centre, text="DRAFT NEXT-CYCLE CORE", style="Section.TLabel").pack(anchor="w")
        canvas_size = GRID_SIZE * self.CELL + 2 * self.MARGIN
        core_frame = ttk.Frame(centre, style="Panel.TFrame")
        core_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 4))
        core_frame.grid_rowconfigure(0, weight=1)
        core_frame.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            core_frame, width=canvas_size, height=canvas_size,
            bg="#090c10", highlightbackground="#56616d", highlightthickness=1,
            scrollregion=(0, 0, canvas_size, canvas_size),
        )
        core_vscroll = ttk.Scrollbar(core_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        core_hscroll = ttk.Scrollbar(core_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(
            xscrollcommand=core_hscroll.set, yscrollcommand=core_vscroll.set,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        core_vscroll.grid(row=0, column=1, sticky="ns")
        core_hscroll.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<Button-1>", self.on_core_click)
        self.canvas.bind("<ButtonPress-1>", self.on_core_press, add="+")
        self.canvas.bind("<ButtonRelease-1>", self.on_core_release, add="+")
        tk.Label(
            centre,
            text="Click a rack card then a position, or drag a card onto the core. Drag an in-core assembly to rearrange it.",
            bg="#11161c", fg="#cbd7e1", padx=8, pady=6, wraplength=650,
        ).pack(fill=tk.X)

        ttk.Label(right, text="ASSEMBLY INSPECTOR", style="Section.TLabel").pack(anchor="w")
        tk.Label(
            right, textvariable=self.detail_var, bg="#11161c", fg="#e4edf4",
            justify=tk.LEFT, anchor="nw", wraplength=315, padx=9, pady=9,
        ).pack(fill=tk.X, pady=(6, 8))
        ttk.Label(right, text="VALIDATION / WORKFLOW", style="Section.TLabel").pack(anchor="w")
        self.validation_text = tk.Text(
            right, width=42, height=25, bg="#101419", fg="#f2e7b6",
            insertbackground="white", wrap=tk.WORD, font=("Segoe UI", 9),
        )
        self.validation_text.pack(fill=tk.BOTH, expand=True, pady=(6, 8))
        self.validation_text.configure(state=tk.DISABLED)
        tk.Label(
            right, textvariable=self.status_var, bg="#0d171e", fg="#7ee7ff",
            justify=tk.LEFT, anchor="nw", wraplength=315, padx=8, pady=7,
        ).pack(fill=tk.X)

    def _build_rack_tab(self, category: str, label: str) -> None:
        frame = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(frame, text=label)
        columns = ("id", "burnup", "cycles", "previous")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=23, selectmode="browse")
        for column, heading, width in (
            ("id", "Assembly / supply", 110), ("burnup", "Burnup", 78),
            ("cycles", "Cycles", 55), ("previous", "Previous", 85),
        ):
            tree.heading(column, text=heading, command=lambda col=column, tr=tree: self.sort_tree(tr, col))
            tree.column(column, width=width, anchor="center")
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.bind("<<TreeviewSelect>>", lambda _event, cat=category: self.on_rack_select(cat))
        tree.bind("<ButtonPress-1>", lambda event, cat=category: self.on_rack_press(event, cat))
        tree.bind("<ButtonRelease-1>", self.on_rack_release)
        self.rack_trees[category] = tree

    @staticmethod
    def sort_tree(tree: ttk.Treeview, column: str) -> None:
        rows = [(tree.set(item, column), item) for item in tree.get_children("")]
        def key(value: Tuple[str, str]):
            text = value[0]
            try:
                return 0, float(text.split()[0])
            except ValueError:
                return 1, text.lower()
        rows.sort(key=key)
        for index, (_value, item) in enumerate(rows):
            tree.move(item, "", index)

    def _push_undo(self) -> None:
        self.undo_stack.append(copy.deepcopy(self.draft))
        if len(self.undo_stack) > 30:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        self.redo_stack.append(copy.deepcopy(self.draft))
        self.draft = self.undo_stack.pop()
        self.active_token = None
        self.core_source = None
        self.refresh()
        self.status_var.set("Undid the previous refueling action.")

    def redo(self) -> None:
        if not self.redo_stack:
            return
        self.undo_stack.append(copy.deepcopy(self.draft))
        self.draft = self.redo_stack.pop()
        self.active_token = None
        self.core_source = None
        self.refresh()
        self.status_var.set("Redid the refueling action.")

    def unload_core(self) -> None:
        if not np.any(self.draft.assembly_ids != ""):
            self.status_var.set("The draft core is already empty.")
            return
        self._push_undo()
        count = self.draft.unload_all_to_staging()
        self.unloaded = True
        self.active_token = None
        self.core_source = None
        self.refresh()
        self.status_var.set(f"Unloaded {count} assemblies into categorized staging racks.")

    def _rack_records(self, category: str) -> List[AssemblyRecord]:
        records = []
        for assembly_id, record in self.draft.assembly_registry.items():
            if record.status not in ("storage", "spent"):
                continue
            if self.draft.refueling_category(assembly_id) == category:
                records.append(record)
        return sorted(records, key=lambda item: (item.state.get("burnup", 0.0), item.assembly_id))

    def refresh_racks(self) -> None:
        for category, tree in self.rack_trees.items():
            tree.delete(*tree.get_children(""))
            if category == "new":
                for key in ("FRESH", "BA", "TH", "SEED", "REFL"):
                    token = f"NEW:{key}"
                    tree.insert("", tk.END, iid=token, values=(ASSEMBLY_TYPES[key].name, "0.00", "0", "NEW"))
                continue
            for record in self._rack_records(category):
                previous = "—"
                for entry in reversed(record.history):
                    if entry.get("position"):
                        previous = str(entry["position"])
                        break
                tree.insert("", tk.END, iid=record.assembly_id, values=(
                    record.assembly_id, f"{record.state.get('burnup', 0.0):.2f}",
                    record.cycles_completed, previous,
                ))
        if self.active_token:
            for tree in self.rack_trees.values():
                if tree.exists(self.active_token):
                    tree.selection_set(self.active_token)
                    tree.focus(self.active_token)
                    tree.see(self.active_token)
                    break

    def refresh_canvas(self) -> None:
        self.canvas.delete("all")
        for c in range(GRID_SIZE):
            self.canvas.create_text(
                self.MARGIN + c * self.CELL + self.CELL / 2, 12,
                text=f"C{c + 1:02d}", fill="#aebdca", font=("Segoe UI", 8),
            )
        for r in range(GRID_SIZE):
            self.canvas.create_text(
                12, self.MARGIN + r * self.CELL + self.CELL / 2,
                text=f"R{r + 1:02d}", fill="#aebdca", font=("Segoe UI", 8), angle=90,
            )
            for c in range(GRID_SIZE):
                x0 = self.MARGIN + c * self.CELL
                y0 = self.MARGIN + r * self.CELL
                x1, y1 = x0 + self.CELL - 2, y0 + self.CELL - 2
                if not self.draft.mask[r, c]:
                    self.canvas.create_rectangle(x0, y0, x1, y1, fill="#090c10", outline="#151a20")
                    continue
                key = str(self.draft.layout[r, c])
                assembly_id = str(self.draft.assembly_ids[r, c])
                outline = "#ffd45c" if (r, c) == self.core_source else "#d9e1e8"
                fill = ASSEMBLY_TYPES[key].color if assembly_id else "#171b20"
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=3 if (r, c) == self.core_source else 1)
                if assembly_id:
                    self.canvas.create_text((x0+x1)/2, y0+13, text=ASSEMBLY_TYPES[key].short, fill="white", font=("Segoe UI", 9, "bold"))
                    self.canvas.create_text((x0+x1)/2, y0+27, text=assembly_id[-4:], fill="#071015", font=("Consolas", 7, "bold"))
                    self.canvas.create_text((x0+x1)/2, y0+39, text=f"{self.draft.burnup[r,c]:.0f}", fill="#071015", font=("Consolas", 7))

    def refresh(self) -> None:
        self.refresh_racks()
        self.refresh_canvas()
        self._write_validation_summary()

    def _cell_from_xy(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        x = self.canvas.canvasx(x)
        y = self.canvas.canvasy(y)
        col = int((x - self.MARGIN) // self.CELL)
        row = int((y - self.MARGIN) // self.CELL)
        if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE and self.draft.mask[row, col]:
            return row, col
        return None

    def _cell_from_root(self, x_root: int, y_root: int) -> Optional[Tuple[int, int]]:
        return self._cell_from_xy(x_root - self.canvas.winfo_rootx(), y_root - self.canvas.winfo_rooty())

    def on_rack_select(self, category: str) -> None:
        tree = self.rack_trees[category]
        selection = tree.selection()
        if not selection:
            return
        for other_category, other_tree in self.rack_trees.items():
            if other_category != category:
                other_tree.selection_remove(other_tree.selection())
        self.active_token = selection[0]
        self.core_source = None
        self.show_token_details(self.active_token)

    def on_rack_press(self, event: tk.Event, category: str) -> None:
        item = self.rack_trees[category].identify_row(event.y)
        if item:
            self.active_token = item
            self.core_source = None
            self.show_token_details(item)

    def on_rack_release(self, event: tk.Event) -> None:
        cell = self._cell_from_root(event.x_root, event.y_root)
        if cell is not None and self.active_token:
            self.place_token(self.active_token, cell)

    def on_core_press(self, event: tk.Event) -> None:
        cell = self._cell_from_xy(event.x, event.y)
        if cell is not None and str(self.draft.assembly_ids[cell]):
            self.core_source = cell

    def on_core_release(self, event: tk.Event) -> None:
        if self.core_source is None:
            return
        target = self._cell_from_xy(event.x, event.y)
        source = self.core_source
        if target is not None and target != source and not self.active_token:
            self._push_undo()
            self.draft.move_or_swap_assemblies(source, target, recalculate=False, record_event=False)
            self.draft.record_assembly_histories("draft_core_move")
            self.core_source = None
            self.refresh()
            self.status_var.set(f"Moved/swapped {self.draft.position_id(*source)} → {self.draft.position_id(*target)} in the draft.")

    def on_core_click(self, event: tk.Event) -> None:
        cell = self._cell_from_xy(event.x, event.y)
        if cell is None:
            return
        if self.active_token:
            self.place_token(self.active_token, cell)
            return
        assembly_id = str(self.draft.assembly_ids[cell])
        if assembly_id:
            self.core_source = cell
            self.show_token_details(assembly_id)
            self.refresh_canvas()

    def place_token(self, token: str, cell: Tuple[int, int]) -> None:
        sticky_new_supply = token.startswith("NEW:")
        if sticky_new_supply:
            key = token.split(":", 1)[1]
            self._push_undo()
            self.draft.set_assembly(*cell, key)
        else:
            record = self.draft.assembly_registry.get(token)
            if record is None or record.status not in ("storage", "spent"):
                self.status_var.set("That assembly is no longer available in a staging rack.")
                return
            if self.draft.refueling_category(token) == "spent":
                self.status_var.set("Spent assemblies cannot be reloaded without changing their eligibility policy.")
                return
            self._push_undo()
            self.draft.load_stored_assembly(token, *cell, recalculate=False, record_event=False)
        self.draft.record_assembly_histories("draft_placement")
        self.active_token = token if sticky_new_supply else None
        self.core_source = None
        self.refresh()
        if sticky_new_supply:
            self.status_var.set(
                f"Placed new {ASSEMBLY_TYPES[key].name} at {self.draft.position_id(*cell)}. "
                "The new-fuel type remains selected; click more positions or use Clear selection when finished."
            )
        else:
            self.status_var.set(f"Placed assembly at {self.draft.position_id(*cell)} in the draft loading.")

    def show_token_details(self, token: str) -> None:
        if token.startswith("NEW:"):
            key = token.split(":", 1)[1]
            spec = ASSEMBLY_TYPES[key]
            self.detail_var.set(f"NEW SUPPLY\n\n{spec.name}\n{spec.notes}\n\nDropping this card creates a new permanent assembly ID.")
            return
        record = self.draft.assembly_registry[token]
        previous = "—"
        for entry in reversed(record.history):
            if entry.get("position"):
                previous = str(entry["position"])
                break
        self.detail_var.set(
            f"{record.assembly_id}\n{ASSEMBLY_TYPES[record.assembly_type].name}\n\n"
            f"Rack/status: {self.draft.refueling_category(token)} / {record.status}\n"
            f"Burnup: {record.state.get('burnup', 0.0):.2f} GWd/tHM\n"
            f"Completed cycles: {record.cycles_completed}\n"
            f"Previous position: {previous}\n"
            f"U-235: {record.state.get('u235_inventory', 0.0):.4f}\n"
            f"Pu-239: {record.state.get('pu239_inventory', 0.0):.4f}\n"
            f"History records: {len(record.history)}"
        )

    def clear_selection(self) -> None:
        self.active_token = None
        self.core_source = None
        for tree in self.rack_trees.values():
            tree.selection_remove(tree.selection())
        self.detail_var.set("Select an assembly card or an in-core assembly.")
        self.refresh_canvas()

    def mark_spent(self) -> None:
        token = self.active_token
        if not token or token.startswith("NEW:") or token not in self.draft.assembly_registry:
            return
        record = self.draft.assembly_registry[token]
        if record.status == "in_core":
            self.status_var.set("Remove the assembly from the draft core before marking it spent.")
            return
        self._push_undo()
        record.status = "spent"
        self.active_token = None
        self.refresh()
        self.status_var.set(f"Moved {token} to the spent-fuel pool.")

    def validate(self, solve: bool = True) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []
        active_ids = [str(value) for value in self.draft.assembly_ids[self.draft.mask] if str(value)]
        empty_count = int(np.sum(self.draft.mask & (self.draft.assembly_ids == "")))
        if empty_count:
            errors.append(f"{empty_count} active core positions are empty.")
        if len(active_ids) != len(set(active_ids)):
            errors.append("One or more assembly IDs appear more than once in the core.")
        for assembly_id in active_ids:
            record = self.draft.assembly_registry[assembly_id]
            if self.draft.refueling_category(assembly_id) == "spent":
                errors.append(f"{assembly_id} exceeds the ordinary three-cycle eligibility policy.")
        for assembly_id, record in self.draft.assembly_registry.items():
            cell = self.draft._locate_assembly(assembly_id)
            if record.status == "in_core" and cell is None:
                errors.append(f"{assembly_id} is marked in-core but has no position.")
            if record.status != "in_core" and cell is not None:
                errors.append(f"{assembly_id} appears in-core but is marked {record.status}.")
        if solve and not errors:
            self.draft.solve()
            if self.draft.k_eff < 0.995:
                warnings.append(f"Unborated k is low ({self.draft.k_eff:.4f}).")
            if self.draft.required_boron_ppm >= MAX_BORON_PPM - 1.0:
                warnings.append("Required boron reaches the configured search limit.")
            if self.draft.radial_peaking > 2.10:
                warnings.append(f"Radial peaking is high ({self.draft.radial_peaking:.3f}).")
            if self.draft.shutdown_margin_pcm <= 0.0:
                errors.append("Calculated shutdown margin is not positive.")
            elif self.draft.shutdown_margin_pcm < 500.0:
                warnings.append(f"Shutdown margin is small ({self.draft.shutdown_margin_pcm:.0f} pcm).")
        return errors, warnings

    def _write_validation_summary(self) -> None:
        loaded = int(np.sum(self.draft.assembly_ids[self.draft.mask] != ""))
        lines = [
            f"Draft positions loaded: {loaded} / {int(np.sum(self.draft.mask))}",
            f"Once-burned rack: {len(self._rack_records('once'))}",
            f"Twice-burned rack: {len(self._rack_records('twice'))}",
            f"Special rack: {len(self._rack_records('special'))}",
            f"Spent pool: {len(self._rack_records('spent'))}",
            "",
            "Workflow:",
            "1. Unload the outgoing core.",
            "2. Place eligible used and new assemblies.",
            "3. Validate and preview.",
            "4. Commit the next cycle.",
        ]
        self.validation_text.configure(state=tk.NORMAL)
        self.validation_text.delete("1.0", tk.END)
        self.validation_text.insert("1.0", "\n".join(lines))
        self.validation_text.configure(state=tk.DISABLED)

    def validate_dialog(self) -> None:
        errors, warnings = self.validate(solve=True)
        self.refresh()
        text = "VALIDATION PASSED" if not errors else "VALIDATION FAILED"
        if errors:
            text += "\n\nErrors:\n- " + "\n- ".join(errors)
        if warnings:
            text += "\n\nWarnings:\n- " + "\n- ".join(warnings)
        messagebox.showinfo("Refueling validation", text, parent=self.window)

    def _outage_days(self) -> Optional[float]:
        try:
            value = float(self.outage_var.get())
            if not math.isfinite(value) or value < 0.0:
                raise ValueError
            return value
        except (ValueError, tk.TclError):
            messagebox.showwarning("Invalid outage", "Enter a non-negative outage duration.", parent=self.window)
            return None

    def preview(self) -> None:
        outage = self._outage_days()
        if outage is None:
            return
        errors, warnings = self.validate(solve=True)
        if errors:
            messagebox.showwarning("Cannot preview", "Correct validation errors before previewing the next cycle.", parent=self.window)
            return
        proposed = copy.deepcopy(self.draft)
        proposed.begin_next_cycle(outage)
        preview = tk.Toplevel(self.window)
        preview.title("Refueling Preview — Previous EOC vs Proposed BOC")
        preview.geometry("1120x650")
        figure = Figure(figsize=(10.8, 5.4), dpi=100, facecolor="#1c2128")
        for index, (model, title) in enumerate(((self.original, "Previous EOC power"), (proposed, "Proposed next-cycle BOC power")), 1):
            axis = figure.add_subplot(1, 2, index)
            masked = np.ma.masked_where(~model.mask | (model.layout == "EMPTY"), model.power)
            image = axis.imshow(masked, cmap="inferno", vmin=0.0, vmax=max(2.1, float(np.max(masked))))
            axis.set_title(title, color="white", fontweight="bold")
            axis.tick_params(colors="white")
            figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
        canvas = FigureCanvasTkAgg(figure, master=preview)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw_idle()
        summary = (
            f"Previous EOC: k={self.original.k_eff:.4f}, peak={self.original.radial_peaking:.3f}, "
            f"boron={self.original.required_boron_ppm:.0f} ppm\n"
            f"Proposed BOC: k={proposed.k_eff:.4f}, peak={proposed.radial_peaking:.3f}, "
            f"boron={proposed.required_boron_ppm:.0f} ppm, shutdown margin={proposed.shutdown_margin_pcm:.0f} pcm"
        )
        tk.Label(preview, text=summary, bg="#101419", fg="#f2e7b6", padx=10, pady=8).pack(fill=tk.X)

    def commit(self) -> None:
        outage = self._outage_days()
        if outage is None:
            return
        errors, warnings = self.validate(solve=True)
        if errors:
            messagebox.showerror("Cannot commit loading", "Correct these errors first:\n\n- " + "\n- ".join(errors), parent=self.window)
            return
        if warnings and not messagebox.askyesno(
            "Commit with warnings?", "Warnings:\n\n- " + "\n- ".join(warnings) + "\n\nCommit this loading?", parent=self.window,
        ):
            return
        committed = copy.deepcopy(self.draft)
        committed.begin_next_cycle(outage)
        self.app.model = committed
        self.app.outage_days_var.set(outage)
        self.app.refuel_source = None
        self.app.refueling_mode_var.set(False)
        self.app.control_insertion_var.set(100.0 * float(np.max(committed.control_fraction)))
        self.app._reset_history()
        self.app._refresh_pool_choices()
        self.app.refresh_all()
        self.app.status_var.set(
            f"Committed refueling loading and began cycle {committed.cycle_number} after a {outage:g}-day outage."
        )
        self.window.destroy()

    def cancel(self) -> None:
        self.window.destroy()


def show_splash(root: tk.Tk, duration_ms: int = 3000) -> None:
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg="#0f1115")
    try:
        splash.attributes("-topmost", True)
    except tk.TclError:
        pass
    border = tk.Frame(splash, bg="#7d1238", padx=3, pady=3)
    border.pack(fill=tk.BOTH, expand=True)
    panel = tk.Frame(border, bg="#12161c", padx=34, pady=24)
    panel.pack(fill=tk.BOTH, expand=True)
    tk.Label(panel, text=PROJECT_NAME, bg="#12161c", fg="#f3f5f7", font=("Segoe UI", 21, "bold")).pack()
    tk.Label(panel, text=MODULE_NAME, bg="#12161c", fg="#c7d1db", font=("Segoe UI", 11)).pack(pady=(8, 0))

    splash.update_idletasks()
    width = splash.winfo_reqwidth()
    height = splash.winfo_reqheight()
    x = max(0, (splash.winfo_screenwidth() - width) // 2)
    y = max(0, (splash.winfo_screenheight() - height) // 2)
    splash.geometry(f"{width}x{height}+{x}+{y}")

    def close() -> None:
        if splash.winfo_exists():
            splash.destroy()
        root.deiconify()
        root.lift()
        try:
            root.focus_force()
        except tk.TclError:
            pass

    root.after(duration_ms, close)


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    CoreLoadingApp(root)
    show_splash(root)
    root.mainloop()


if __name__ == "__main__":
    main()
