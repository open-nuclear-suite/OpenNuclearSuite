"""GUI-neutral controls for the canonical thermal-hydraulics model."""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from types import MethodType

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent


class Value:
    """Small Tk variable-compatible adapter used by the unchanged model."""

    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


CONTROL_DEFAULTS = {
    "rod": 0.0, "trim": 0.0, "boron": 1000.0, "pump": 100.0,
    "sg": 100.0, "break": 0.0, "eccs": 0.0, "afw": 0.0,
    "porv": 0.0, "spray": 0.0, "heater": 0.0, "rhr": 0.0,
    "noise": 2.0, "speed": 1.0,
    "recirc": 100.0, "feedwater": 100.0, "main_steam": 100.0,
    "srv": 0.0,
    "msiv": 100.0, "bypass": 0.0, "rcic": 0.0, "hpci": 0.0,
    "ads": 0.0, "lpci": 0.0, "core_spray": 0.0,
    "shutdown_cooling": 0.0, "bwr_break": 0.0,
}
CONTROL_LIMITS = {
    "rod": (0, 100), "trim": (-500, 500), "boron": (0, 2500),
    "pump": (0, 120), "sg": (0, 140), "break": (0, 100),
    "eccs": (0, 100), "afw": (0, 100), "porv": (0, 100),
    "spray": (0, 100), "heater": (0, 100), "rhr": (0, 100),
    "noise": (0, 10), "speed": (0.2, 20),
    "recirc": (0, 120), "feedwater": (0, 140),
    "main_steam": (0, 140), "srv": (0, 100),
    "msiv": (0, 100), "bypass": (0, 100), "rcic": (0, 100),
    "hpci": (0, 100), "ads": (0, 100), "lpci": (0, 100),
    "core_spray": (0, 100), "shutdown_cooling": (0, 100),
    "bwr_break": (0, 100),
}


def hot_channel_interval_for_speed(speed: float, base_sim_interval_s: float = 0.25) -> float:
    """Keep costly axial solves near a fixed wall-clock rate above real time."""
    return base_sim_interval_s * max(1.0, float(speed))


SCENARIOS = {
    "NORMAL": ("Normal operation", False, True, {"rod": 0, "trim": 0, "boron": 1000, "pump": 100, "sg": 100, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "SBLOCA": ("Small-break LOCA", True, True, {"rod": 100, "trim": 0, "pump": 60, "sg": 100, "break": 12, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LBLOCA": ("Large-break LOCA", True, True, {"rod": 100, "trim": 0, "pump": 0, "sg": 60, "break": 70, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LOFA": ("Loss of flow accident", True, True, {"rod": 100, "trim": 0, "pump": 0, "sg": 100, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LOHS": ("Loss of heat sink", True, True, {"rod": 100, "trim": 0, "pump": 80, "sg": 0, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "SBO": ("Station blackout", True, False, {"rod": 100, "trim": 0, "pump": 0, "sg": 8, "break": 0, "eccs": 0, "afw": 10, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
}

BWR_SCENARIOS = {
    "NORMAL": ("BWR normal operation", False, {
        "rod": 0, "trim": 0, "recirc": 100, "feedwater": 100,
        "main_steam": 100, "srv": 0,
    }),
    "RECIRC_TRIP": ("BWR recirculation pump trip", False, {
        "rod": 0, "trim": 0, "recirc": 0, "feedwater": 100,
        "main_steam": 100, "srv": 0,
    }),
    "TURBINE_TRIP": ("BWR turbine trip", True, {
        "rod": 100, "trim": 0, "recirc": 80, "feedwater": 0,
        "main_steam": 0, "srv": 0,
    }),
    "LOFW": ("BWR loss of feedwater", False, {
        "rod": 0, "trim": 0, "recirc": 100, "feedwater": 0,
        "main_steam": 100, "srv": 0,
    }),
    "SBLOCA": ("BWR small-break LOCA", True, {
        "rod": 100, "trim": 0, "recirc": 40, "feedwater": 0,
        "main_steam": 20, "msiv": 100, "bwr_break": 15,
        "rcic": 70, "hpci": 0, "ads": 0, "lpci": 0, "core_spray": 0,
    }),
    "SBO": ("BWR station blackout", True, {
        "rod": 100, "trim": 0, "recirc": 0, "feedwater": 0,
        "main_steam": 0, "msiv": 100, "bypass": 0, "srv": 0,
        "rcic": 80, "hpci": 0, "lpci": 0, "core_spray": 0,
    }),
}

DEMO_SCRIPTS = (
    "SBLOCA recovery", "LBLOCA ECCS response",
    "Loss of heat sink recovery", "Station blackout recovery",
)
BWR_DEMO_SCRIPTS = (
    "BWR recirculation trip and recovery",
    "BWR turbine trip and SRV response",
    "BWR loss of feedwater recovery",
)
DEMO_TARGETS = {
    "SBLOCA recovery": "Stable shutdown with inventory restored and RHR available",
    "LBLOCA ECCS response": "Stable shutdown with long-term injection and decay-heat removal",
    "Loss of heat sink recovery": "Stable shutdown with secondary and residual heat removal",
    "Station blackout recovery": "Stable shutdown after power recovery and shutdown cooling",
    BWR_DEMO_SCRIPTS[0]: "Return to controlled power operation after recirculation recovery",
    BWR_DEMO_SCRIPTS[1]: "Reactor shut down with vessel pressure controlled",
    BWR_DEMO_SCRIPTS[2]: "Reactor shut down with vessel inventory restored",
}
DEMO_RECOVERY_MODES = {
    name: ("return_to_power" if name == BWR_DEMO_SCRIPTS[0] else "stable_shutdown")
    for name in DEMO_TARGETS
}


def build_headless_model(model_dir: Path = DEFAULT_MODEL_DIR, plant_type: str = "PWR"):
    model_dir = Path(model_dir).resolve()
    if not getattr(sys, "frozen", False) and not (model_dir / "thermal_hydraulics_simulator.py").exists():
        raise FileNotFoundError(f"Thermal-hydraulics model not found in: {model_dir}")
    if str(model_dir) not in sys.path: sys.path.insert(0, str(model_dir))
    import thermal_hydraulics_simulator as th
    sim = th.LWRTeachingSimulator.__new__(th.LWRTeachingSimulator)
    plant_key = str(plant_type).upper()
    constant_types = {"PWR": th.Constants, "BWR": th.BWRConstants}
    state_types = {"PWR": th.State, "BWR": th.BWRState}
    if plant_key not in constant_types:
        raise ValueError(f"Unknown plant type: {plant_type}")
    sim.c, sim.state = constant_types[plant_key](), None
    sim.state = state_types[plant_key](sim.c)
    sim.steam_tables = th.SteamTables()
    sim.physics = th.create_plant_model(plant_key, sim.c, sim.steam_tables)
    sim.physics.initialize_state(sim.state)
    sim.hot_channel = th.HotChannelModel(sim.steam_tables)
    sim.bwr_hot_channel = th.BWRHotChannelModel(sim.steam_tables)
    sim.hot_channel_result = None
    sim.hot_channel_result_time = float("nan")
    sim.hot_channel_error = None
    sim.hot_channel_update_interval_s = 0.25
    sim.hot_flux_reference_max_MW_m2 = 6.0
    sim.hot_dnbr_reference_max = 6.0
    sim.control_vars = {key: Value(value) for key, value in CONTROL_DEFAULTS.items()}
    sim.auto_eccs_var, sim.auto_trip_var = Value(True), Value(True)
    sim.bwr_system_availability = {
        name: True for name in ("rcic", "hpci", "ads", "lpci", "core_spray")
    }
    sim.state.autoECCS = True
    if plant_key == "BWR":
        sim.state.scenario_name = "BWR normal operation"
    sim.hot_channel_coupling_var = Value(plant_key == "PWR")
    sim.events, sim.event_snapshot, sim.last_event_time = deque(maxlen=250), {}, {}
    sim.demo_stage, sim.csv_logging = "", False
    sim.csv_writer = sim.csv_file = None
    sim.csv_last_logged_t = -1.0e9
    def set_slider(self, key, value): self.control_vars[key].set(float(value))
    sim.set_slider = MethodType(set_slider, sim)
    sim.reset_event_timeline()
    return sim


class ThermalHydraulicsGUIBackend:
    """Operator-control API shared by responsive thermal-hydraulics UIs."""
    DT = 0.05
    CONTROL_LABELS = {
        "rod": "Control rods", "trim": "Fine reactivity", "boron": "Boron",
        "pump": "Primary pumps", "sg": "Steam-generator heat removal",
        "break": "Break size", "eccs": "ECCS", "afw": "Auxiliary feedwater",
        "porv": "PORV", "spray": "Pressurizer spray", "heater": "Pressurizer heaters",
        "rhr": "Residual heat removal", "recirc": "Recirculation",
        "feedwater": "Feedwater", "main_steam": "Main steam valve", "srv": "Manual SRV",
        "msiv": "Main steam isolation valves", "bypass": "Turbine bypass",
        "rcic": "RCIC", "hpci": "HPCI", "ads": "ADS", "lpci": "LPCI",
        "core_spray": "Core spray", "shutdown_cooling": "Shutdown cooling",
        "bwr_break": "Vessel break size",
    }

    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR):
        self.model_dir = Path(model_dir).resolve()
        self.plant_type = "PWR"
        self.sim = build_headless_model(self.model_dir, self.plant_type)
        self.running, self.physics_credit = False, 0.0
        self.demo_mode, self.demo_script = False, DEMO_SCRIPTS[0]
        self.demo_start_t = 0.0
        self.demo_action_log, self._last_demo_stage = [], None
        self.demo_target = ""

    @property
    def state(self): return self.sim.state
    @property
    def plant_metadata(self): return self.sim.physics.metadata
    @property
    def available_scenarios(self):
        return tuple((BWR_SCENARIOS if self.plant_type == "BWR" else SCENARIOS).keys())
    @property
    def available_demos(self):
        return BWR_DEMO_SCRIPTS if self.plant_type == "BWR" else DEMO_SCRIPTS
    def start(self): self.running = True
    def pause(self): self.running = False

    def reset(self):
        self.running = False
        self.sim = build_headless_model(self.model_dir, self.plant_type)
        self.physics_credit = 0.0
        self.demo_mode, self.demo_start_t = False, 0.0
        self.demo_action_log, self._last_demo_stage = [], None
        self.demo_target = ""

    def select_plant(self, plant_type):
        plant_key = str(plant_type).upper()
        if plant_key not in ("PWR", "BWR"):
            raise ValueError(f"Unknown plant type: {plant_type}")
        self.plant_type = plant_key
        self.reset()
        self.sim.record_event(
            "SYSTEM",
            f"Selected {self.plant_metadata.label} ({self.plant_metadata.development_status})",
        )
        return self.plant_metadata

    def scram(self):
        self.state.trip = True
        self.set_control("rod", 100.0)
        self.set_control("trim", 0.0)
        self.running = True

    def set_control(self, key, value):
        if key not in CONTROL_LIMITS: raise ValueError(f"Unknown control: {key}")
        low, high = CONTROL_LIMITS[key]
        value = min(max(float(value), low), high)
        self.sim.control_vars[key].set(value)
        return value

    def set_automatic(self, name, enabled):
        variables = {"eccs": self.sim.auto_eccs_var, "trip": self.sim.auto_trip_var, "hot_channel": self.sim.hot_channel_coupling_var}
        if name not in variables: raise ValueError(f"Unknown automatic control: {name}")
        if name == "hot_channel" and self.plant_type == "BWR" and enabled:
            raise ValueError("BWR axial-channel results are diagnostic only")
        variables[name].set(bool(enabled))
        if name == "eccs" and not enabled: self.state.auto_eccs_demand = 0.0

    def set_bwr_system_available(self, name, available):
        if name not in self.sim.bwr_system_availability:
            raise ValueError(f"Unknown BWR safety system: {name}")
        self.sim.bwr_system_availability[name] = bool(available)
        return bool(available)

    def select_scenario(self, name):
        if self.plant_type == "BWR":
            if name not in BWR_SCENARIOS: raise ValueError(f"Unknown BWR scenario: {name}")
            title, trip, values = BWR_SCENARIOS[name]
            auto_eccs = False
        else:
            if name not in SCENARIOS: raise ValueError(f"Unknown scenario: {name}")
            title, trip, auto_eccs, values = SCENARIOS[name]
        self.state.scenario_name, self.state.trip = title, trip
        self.state.auto_eccs_demand = 0.0
        self.set_automatic("eccs", auto_eccs)
        self.state.autoECCS = auto_eccs
        for key, value in values.items(): self.set_control(key, value)
        self.sim.record_event("SCENARIO", f"Selected {title}")

    def set_controls(self, **values):
        for key, value in values.items():
            if abs(self.sim.control_vars[key].get() - float(value)) > 0.05:
                self.set_control(key, value)

    def start_demo(self, script):
        if script not in self.available_demos: raise ValueError(f"Unknown demo: {script}")
        self.reset(); self.select_scenario("NORMAL")
        self.demo_mode, self.demo_script = True, script
        self.demo_start_t, self.sim.demo_stage = self.state.t, "Demo armed: initial full-power operation"
        self.state.scenario_name = f"Demo: {script}"
        self.demo_target = DEMO_TARGETS.get(script, "Bring the plant to a stable controlled condition")
        self._record_demo_action(self.sim.demo_stage, {})
        self.running = True

    def stop_demo(self, completed=False):
        self.demo_mode = False
        if not completed: self.sim.demo_stage = "Demo stopped; manual control returned"
        self._record_demo_action(self.sim.demo_stage, {})

    def _record_demo_action(self, stage, values):
        if stage == self._last_demo_stage:
            return
        changes = []
        for key, requested in values.items():
            if key not in self.sim.control_vars:
                continue
            previous = float(self.sim.control_vars[key].get())
            requested = float(requested)
            if abs(previous-requested) > 0.05:
                label = self.CONTROL_LABELS.get(key, key.replace("_", " ").title())
                unit = " ppm" if key == "boron" else " pcm" if key == "trim" else "%"
                changes.append(f"{label}: {previous:g}{unit} → {requested:g}{unit}")
        action_text = "; ".join(changes) if changes else "Monitor plant response; no new control movement."
        self.demo_action_log.append(
            f"{self.state.t:7.1f} s | {stage}\n           Actions: {action_text}"
        )
        self.demo_action_log = self.demo_action_log[-12:]
        self._last_demo_stage = stage

    def _publish_demo_stage(self, stage, values):
        self._record_demo_action(stage, values)
        self.sim.demo_stage = stage
        self.set_controls(**values)

    def apply_demo_mode(self):
        if not self.demo_mode: return
        s, rel, script = self.state, self.state.t-self.demo_start_t, self.demo_script
        s.scenario_name = f"Demo: {script}"
        if self.plant_type == "BWR":
            self.apply_bwr_demo(rel, script)
            return
        if script == "SBLOCA recovery":
            if rel < 20: stage, values = "Normal full-power operation before the fault.", dict(rod=0,trim=0,boron=1000,pump=100,sg=100,**{"break":0})
            elif rel < 35: stage, values = "Fault inserted: small-break LOCA. Primary inventory and pressure begin to fall.", dict(pump=75,sg=100,eccs=0,afw=0,porv=0,spray=0,rhr=0,**{"break":12})
            elif rel < 65: stage, values = "Protection response: reactor trip, rods inserted, decay heat remains.", dict(rod=100,trim=0,pump=60,sg=100,eccs=0,afw=20,porv=0,spray=0,rhr=0,**{"break":12}); s.trip=True
            elif rel < 120: stage, values = "Safety response: ECCS and auxiliary feedwater recover inventory and heat removal.", dict(rod=100,pump=60,sg=100,eccs=65,afw=55,porv=0,spray=0,rhr=0,**{"break":12}); s.trip=True
            elif rel < 170: stage, values = "Cooldown response: controlled depressurization prepares for residual heat removal.", dict(eccs=55,afw=75,porv=18,spray=35,rhr=0,**{"break":8})
            elif rel < 240: stage, values = "Long-term response: break isolated in the model; RHR removes decay heat at low pressure.", dict(eccs=35,afw=55,porv=8,spray=20,rhr=80,**{"break":0})
            else: self.sim.demo_stage="Demo complete: plant stabilized in shutdown cooling. Manual control returned."; self.stop_demo(completed=True); return
        elif script == "LBLOCA ECCS response":
            if rel < 15: stage, values = "Normal full-power operation before the large-break LOCA.", dict(rod=0,trim=0,pump=100,sg=100,eccs=0,afw=0,porv=0,spray=0,rhr=0,**{"break":0})
            elif rel < 30: stage, values = "Fault inserted: large break causes rapid depressurization and inventory loss.", dict(rod=100,pump=0,sg=60,eccs=0,afw=0,porv=0,spray=0,rhr=0,**{"break":70}); s.trip=True
            elif rel < 90: stage, values = "Emergency response: accumulators/LPSI surrogate inject strongly after pressure falls.", dict(rod=100,pump=0,sg=60,eccs=100,afw=40,porv=0,spray=0,rhr=0,**{"break":70}); s.trip=True
            elif rel < 150: stage, values = "Recovery response: break area is reduced and ECCS refloods the core.", dict(eccs=100,afw=60,rhr=40,**{"break":35})
            elif rel < 230: stage, values = "Long-term cooling: break isolated, ECCS reduced, RHR maintains decay-heat removal.", dict(eccs=45,afw=50,rhr=90,spray=20,porv=5,**{"break":0})
            else: self.sim.demo_stage="Demo complete: long-term cooling established. Manual control returned."; self.stop_demo(completed=True); return
        elif script == "Loss of heat sink recovery":
            if rel < 20: stage, values = "Normal operation with steam generator heat removal available.", dict(rod=0,trim=0,pump=100,sg=100,eccs=0,afw=0,porv=0,spray=0,rhr=0,**{"break":0})
            elif rel < 45: stage, values = "Fault inserted: main heat sink lost; pressure and coolant temperature rise.", dict(rod=100,pump=80,sg=0,eccs=0,afw=0,porv=0,spray=0,rhr=0); s.trip=True
            elif rel < 90: stage, values = "Operator response: auxiliary feedwater restores secondary-side heat removal.", dict(rod=100,pump=80,sg=0,afw=90,spray=20,porv=0,eccs=0,rhr=0); s.trip=True
            elif rel < 150: stage, values = "Pressure control: spray/PORV manage pressure while AFW removes decay heat.", dict(afw=95,spray=55,porv=12,pump=60,rhr=0)
            elif rel < 230: stage, values = "Cooldown: primary system depressurized enough for RHR contribution.", dict(afw=60,spray=25,porv=8,pump=40,rhr=75)
            else: self.sim.demo_stage="Demo complete: decay heat removal restored. Manual control returned."; self.stop_demo(completed=True); return
        else:
            if rel < 15: stage, values = "Normal operation before loss of offsite and onsite AC power.", dict(rod=0,trim=0,pump=100,sg=100,eccs=0,afw=0,porv=0,spray=0,rhr=0,**{"break":0}); self.set_automatic("eccs",True)
            elif rel < 45: stage, values = "Fault inserted: station blackout. Reactor trips; pumps and active injection are unavailable.", dict(rod=100,pump=0,sg=8,eccs=0,afw=10,porv=0,spray=0,heater=0,rhr=0); s.trip=True; self.set_automatic("eccs",False)
            elif rel < 90: stage, values = "Coping response: turbine-driven/portable feedwater surrogate removes some decay heat.", dict(rod=100,pump=0,sg=8,eccs=0,afw=45,porv=0,spray=0,rhr=0); s.trip=True
            elif rel < 140: stage, values = "Recovery response: power/injection restored; controlled depressurization begins.", dict(eccs=55,afw=80,porv=12,spray=25,pump=25,rhr=0); self.set_automatic("eccs",True)
            elif rel < 220: stage, values = "Shutdown cooling: RHR becomes available as pressure falls.", dict(eccs=45,afw=60,porv=10,spray=25,pump=35,rhr=85)
            else: self.sim.demo_stage="Demo complete: AC recovery and shutdown cooling established. Manual control returned."; self.stop_demo(completed=True); return
        self._publish_demo_stage(stage, values)

    def apply_bwr_demo(self, rel, script):
        s = self.state
        if script == BWR_DEMO_SCRIPTS[0]:
            if rel < 15: stage, values = "Normal BWR operation before recirculation-pump trip.", dict(rod=0,trim=0,recirc=100,feedwater=100,main_steam=100,msiv=100,bypass=0,srv=0)
            elif rel < 17: stage, values = "Recirculation trip: core flow coasts down; void feedback reduces power.", dict(recirc=0)
            elif rel < 25: stage, values = "Prompt partial recirculation recovery arrests the low-flow transient.", dict(recirc=80)
            elif rel < 45: stage, values = "Full recirculation restored; the vessel returns toward equilibrium.", dict(recirc=100)
            else: self.sim.demo_stage="Demo complete: recirculation and power stabilized."; self.stop_demo(completed=True); return
        elif script == BWR_DEMO_SCRIPTS[1]:
            if rel < 15: stage, values = "Normal BWR operation before turbine trip.", dict(rod=0,trim=0,recirc=100,feedwater=100,main_steam=100,msiv=100,bypass=0,srv=0)
            elif rel < 55: stage, values = "Turbine trip: main steam and feedwater close, reactor scrams, and vessel pressure rises.", dict(rod=100,recirc=80,feedwater=0,main_steam=0); s.trip=True
            elif rel < 95: stage, values = "Automatic SRV discharge limits pressure; turbine bypass is prepared for heat removal.", dict(feedwater=70,main_steam=0,bypass=20,srv=0); s.trip=True
            elif rel < 140: stage, values = "Turbine bypass and feedwater establish controlled cooldown.", dict(feedwater=10,main_steam=0,bypass=26,srv=0,recirc=45); s.trip=True
            else: self.sim.demo_stage="Demo complete: pressure controlled with the reactor shut down."; self.stop_demo(completed=True); return
        else:
            if rel < 15: stage, values = "Normal BWR operation before loss of feedwater.", dict(rod=0,trim=0,recirc=100,feedwater=100,main_steam=100,msiv=100,bypass=0,srv=0,rcic=0,hpci=0)
            elif rel < 50: stage, values = "Feedwater lost: steam export lowers vessel liquid inventory.", dict(feedwater=0)
            elif rel < 90: stage, values = "Low-level response: reactor scram plus RCIC/HPCI restore vessel inventory.", dict(rod=100,recirc=60,feedwater=0,rcic=80,hpci=50); s.trip=True
            elif rel < 135: stage, values = "Feedwater is restored at shutdown demand; emergency injection is reduced as level recovers.", dict(feedwater=55,main_steam=5,recirc=40,rcic=0,hpci=0); s.trip=True
            else: self.sim.demo_stage="Demo complete: feedwater restored and inventory recovering."; self.stop_demo(completed=True); return
        self._publish_demo_stage(stage, values)

    def advance_elapsed(self, elapsed, speed=1.0, max_steps=200):
        if not self.running: return 0
        self.physics_credit += max(0.0, float(elapsed)) * max(0.0, float(speed))
        steps = min(int(self.physics_credit / self.DT), max_steps)
        for _ in range(steps):
            self.apply_demo_mode()
            self.sim.step_model(self.DT)
        if steps: self.physics_credit -= steps * self.DT
        return steps
