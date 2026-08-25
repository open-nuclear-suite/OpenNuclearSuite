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
}
CONTROL_LIMITS = {
    "rod": (0, 100), "trim": (-500, 500), "boron": (0, 2500),
    "pump": (0, 120), "sg": (0, 140), "break": (0, 100),
    "eccs": (0, 100), "afw": (0, 100), "porv": (0, 100),
    "spray": (0, 100), "heater": (0, 100), "rhr": (0, 100),
    "noise": (0, 10), "speed": (0.2, 20),
}
SCENARIOS = {
    "NORMAL": ("Normal operation", False, True, {"rod": 0, "trim": 0, "boron": 1000, "pump": 100, "sg": 100, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "SBLOCA": ("Small-break LOCA", True, True, {"rod": 100, "trim": 0, "pump": 60, "sg": 100, "break": 12, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LBLOCA": ("Large-break LOCA", True, True, {"rod": 100, "trim": 0, "pump": 0, "sg": 60, "break": 70, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LOFA": ("Loss of flow accident", True, True, {"rod": 100, "trim": 0, "pump": 0, "sg": 100, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "LOHS": ("Loss of heat sink", True, True, {"rod": 100, "trim": 0, "pump": 80, "sg": 0, "break": 0, "eccs": 0, "afw": 0, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
    "SBO": ("Station blackout", True, False, {"rod": 100, "trim": 0, "pump": 0, "sg": 8, "break": 0, "eccs": 0, "afw": 10, "porv": 0, "spray": 0, "heater": 0, "rhr": 0}),
}

DEMO_SCRIPTS = (
    "SBLOCA recovery", "LBLOCA ECCS response",
    "Loss of heat sink recovery", "Station blackout recovery",
)


def build_headless_model(model_dir: Path = DEFAULT_MODEL_DIR):
    model_dir = Path(model_dir).resolve()
    if not getattr(sys, "frozen", False) and not (model_dir / "thermal_hydraulics_simulator.py").exists():
        raise FileNotFoundError(f"Thermal-hydraulics model not found in: {model_dir}")
    if str(model_dir) not in sys.path: sys.path.insert(0, str(model_dir))
    import thermal_hydraulics_simulator as th
    sim = th.LWRTeachingSimulator.__new__(th.LWRTeachingSimulator)
    sim.c, sim.state = th.Constants(), None
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
    sim.control_vars = {key: Value(value) for key, value in CONTROL_DEFAULTS.items()}
    sim.auto_eccs_var, sim.auto_trip_var = Value(True), Value(True)
    sim.hot_channel_coupling_var = Value(True)
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

    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR):
        self.model_dir = Path(model_dir).resolve()
        self.sim = build_headless_model(self.model_dir)
        self.running, self.physics_credit = False, 0.0
        self.demo_mode, self.demo_script = False, DEMO_SCRIPTS[0]
        self.demo_start_t = 0.0

    @property
    def state(self): return self.sim.state
    def start(self): self.running = True
    def pause(self): self.running = False

    def reset(self):
        self.running = False
        self.sim = build_headless_model(self.model_dir)
        self.physics_credit = 0.0
        self.demo_mode, self.demo_start_t = False, 0.0

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
        variables[name].set(bool(enabled))
        if name == "eccs" and not enabled: self.state.auto_eccs_demand = 0.0

    def select_scenario(self, name):
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
        if script not in DEMO_SCRIPTS: raise ValueError(f"Unknown demo: {script}")
        self.reset(); self.select_scenario("NORMAL")
        self.demo_mode, self.demo_script = True, script
        self.demo_start_t, self.sim.demo_stage = self.state.t, "Demo armed: initial full-power operation"
        self.state.scenario_name = f"Demo: {script}"
        self.running = True

    def stop_demo(self, completed=False):
        self.demo_mode = False
        if not completed: self.sim.demo_stage = "Demo stopped; manual control returned"

    def apply_demo_mode(self):
        if not self.demo_mode: return
        s, rel, script = self.state, self.state.t-self.demo_start_t, self.demo_script
        s.scenario_name = f"Demo: {script}"
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
        self.sim.demo_stage = stage; self.set_controls(**values)

    def advance_elapsed(self, elapsed, speed=1.0, max_steps=200):
        if not self.running: return 0
        self.physics_credit += max(0.0, float(elapsed)) * max(0.0, float(speed))
        steps = min(int(self.physics_credit / self.DT), max_steps)
        for _ in range(steps):
            self.apply_demo_mode()
            self.sim.step_model(self.DT)
        if steps: self.physics_credit -= steps * self.DT
        return steps
