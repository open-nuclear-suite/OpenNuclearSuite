"""Full PySide6/PyQtGraph front end for the reactor teaching simulator."""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider, QSplitter,
    QTabWidget, QVBoxLayout, QWidget,
)

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent
PLOT_POINTS = 2200
VISIBLE_WINDOW_S = 40.0

STYLE = """
QWidget { background:#0d1218; color:#edf4fa; font:14px 'Segoe UI'; }
QGroupBox { border:1px solid #40505d; border-radius:5px; margin-top:11px;
 padding-top:9px; font-weight:bold; color:#67c7ff; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }
QPushButton { background:#1d4e70; border:1px solid #39789e; border-radius:4px; padding:7px 10px; }
QPushButton:hover { background:#286c99; } QPushButton:pressed { background:#13384f; }
QComboBox { background:#1b2631; border:1px solid #40505d; padding:5px; }
QTabWidget::pane { border:1px solid #40505d; background:#111820; }
QTabBar::tab { background:#1b2631; color:#dceaf4; border:1px solid #40505d;
 padding:8px 14px; margin-right:2px; }
QTabBar::tab:selected { background:#1d4e70; color:#ffffff; }
QTabBar::tab:hover { background:#286c99; color:#ffffff; }
QSlider::groove:horizontal { height:7px; background:#293945; border-radius:3px; }
QSlider::handle:horizontal { width:17px; margin:-5px 0; background:#67c7ff; border-radius:8px; }
QProgressBar { border:1px solid #40505d; border-radius:3px; text-align:center; background:#17212a; }
QProgressBar::chunk { background:#2980b9; }
"""


def load_backend(model_dir: Path):
    model_dir = model_dir.resolve()
    if not getattr(sys, "frozen", False) and not (model_dir / "reactor_teaching_simulator.py").exists():
        raise SystemExit(f"Reactor model not found in: {model_dir}")
    if str(model_dir) not in sys.path:
        sys.path.insert(0, str(model_dir))
    from reactor_gui_backend import ReactorGUIBackend
    import reactor_teaching_simulator as canonical
    return ReactorGUIBackend, canonical


class FloatSlider(QWidget):
    def __init__(self, title, low, high, value, callback, decimals=1, suffix=""):
        super().__init__()
        self.low, self.high, self.decimals, self.suffix = low, high, decimals, suffix
        self.callback, self.syncing = callback, False
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 3)
        row = QHBoxLayout(); self.title_label = QLabel(title); row.addWidget(self.title_label); self.value_label = QLabel(); row.addStretch(); row.addWidget(self.value_label)
        layout.addLayout(row); self.slider = QSlider(Qt.Orientation.Horizontal); self.slider.setRange(0, 1000); layout.addWidget(self.slider)
        self.slider.valueChanged.connect(self._changed); self.set_value(value)

    def _to_value(self, raw): return self.low + (self.high - self.low) * raw / 1000.0
    def _changed(self, raw):
        value = self._to_value(raw); self.value_label.setText(f"{value:.{self.decimals}f}{self.suffix}")
        if not self.syncing: self.callback(value)

    def set_value(self, value):
        self.syncing = True
        raw = round(1000 * (float(value) - self.low) / (self.high - self.low))
        self.slider.setValue(max(0, min(1000, raw))); self._changed(self.slider.value()); self.syncing = False


class PlantMimic(QWidget):
    def __init__(self, canonical, parent=None):
        super().__init__(parent); self.canonical = canonical; self.state = None; self.setMinimumSize(470, 235)

    def paintEvent(self, _event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.fillRect(self.rect(), QColor("#111820"))
        if self.state is None: return
        s = self.state; sx, sy = self.width() / 470.0, self.height() / 235.0
        p.scale(sx, sy); power = max(0.0, min(s.powerPct / 150.0, 1.0))
        core = QColor(int(40 + 215 * power), int(100 + 100 * (1-power)), 45)
        coolant = QColor("#289bf0") if s.coolantFlow >= 35 else QColor("#ff6428")
        p.setPen(QPen(QColor("#96aab9"), 3)); p.setBrush(QColor("#1e2830")); p.drawRect(QRectF(45,35,130,170))
        p.setPen(QPen(core, 3)); fill = QColor(core); fill.setAlpha(90); p.setBrush(fill); p.drawRect(QRectF(75,68,70,110))
        p.setPen(QColor("#ebf0f5")); p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold)); p.drawText(QRectF(75,100,70,35), Qt.AlignmentFlag.AlignCenter, "CORE")
        rod_y = 70 + 1.05 * self.canonical.rod_insertion_from_withdrawn(s.rod_pos)
        p.setPen(QPen(QColor("#dddddd"), 5));
        for x in (88,110,132): p.drawLine(QPointF(x,42), QPointF(x,rod_y))
        p.setPen(QPen(coolant, 10));
        for a,b in (((175,70),(285,70)),((285,70),(285,185)),((285,185),(175,185)),((285,70),(325,85)),((325,170),(285,185))): p.drawLine(QPointF(*a), QPointF(*b))
        p.setPen(QPen(QColor("#8caab9"),3)); p.setBrush(QColor("#1c2630")); p.drawEllipse(QPointF(355,128),53,53)
        p.setPen(QColor("#ebf0f5")); p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold)); p.drawText(QRectF(305,103,100,50), Qt.AlignmentFlag.AlignCenter, "STEAM\nGEN.")
        p.setFont(QFont("Segoe UI", 11)); p.setPen(QColor("#78dcff")); p.drawText(QRectF(0,3,470,25), Qt.AlignmentFlag.AlignCenter, f"{s.powerPct:6.2f}% power   {s.fuelT:5.1f} C fuel   {s.coolantFlow:4.0f}% flow")
        if s.scram:
            p.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold)); p.setPen(QColor("#ff2d2d")); p.drawText(QRectF(175,90,120,45), Qt.AlignmentFlag.AlignCenter, "SCRAM")


class SettingsDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.owner = owner; c = owner.canonical
        self.setWindowTitle("Instructor - Pedagogical Settings"); self.resize(690, 470)
        layout = QVBoxLayout(self); layout.addWidget(QLabel("These controls alter the model equations, not wall-clock simulation speed."))
        form = QFormLayout(); layout.addLayout(form)
        self.kinetics = QComboBox(); self.kinetics.addItems(owner.kinetics_labels); form.addRow("Kinetics preset", self.kinetics)
        self.xenon = QComboBox(); self.xenon.addItems(owner.xenon_labels); form.addRow("Xenon timescale", self.xenon)
        self.load = FloatSlider("Load-follow period",60,600,180,lambda _v:None,0," s"); form.addRow(self.load)
        self.profile = QComboBox(); self.profile.addItems(c.PHYSICS_PROFILES); form.addRow("Core-physics detail",self.profile)
        self.initial = QComboBox(); self.initial.addItems(c.INITIAL_CONDITIONS); form.addRow("Initial condition",self.initial)
        self.cycle = QComboBox(); self.cycle.addItems(c.CYCLE_PRESETS); form.addRow("Exposure state",self.cycle)
        layout.addWidget(QLabel("Applying settings resets the run and initializes delayed-neutron and poison state consistently."))
        buttons=QHBoxLayout(); layout.addLayout(buttons)
        for text,fn in (("Restore validated defaults",self.defaults),("Cancel",self.reject),("Apply and reset",self.apply)):
            b=QPushButton(text); b.clicked.connect(fn); buttons.addWidget(b)
        self.profile.currentTextChanged.connect(self.availability)

    def availability(self, profile):
        advanced = profile == "Advanced core physics"
        self.initial.setEnabled(advanced); self.cycle.setEnabled(advanced)
        if not advanced:
            self.initial.setCurrentText("Full-power equilibrium"); self.cycle.setCurrentText("Steady classroom")

    def populate(self, settings):
        c=self.owner.canonical; self.kinetics.setCurrentText(c.kinetics_preset_label(settings.kinetics_preset)); self.xenon.setCurrentText(c.xenon_preset_label(settings.xenon_preset))
        self.load.set_value(settings.load_follow_period_s); self.profile.setCurrentText(settings.physics_profile); self.initial.setCurrentText(settings.initial_condition); self.cycle.setCurrentText(settings.cycle_preset); self.availability(settings.physics_profile)

    def defaults(self): self.populate(self.owner.canonical.PedagogicalSettings())
    def apply(self):
        c=self.owner.canonical
        settings=c.PedagogicalSettings(kinetics_preset=self.owner.kinetics_labels[self.kinetics.currentText()], xenon_preset=self.owner.xenon_labels[self.xenon.currentText()], load_follow_period_s=self.load._to_value(self.load.slider.value()), physics_profile=self.profile.currentText(), initial_condition=self.initial.currentText(), cycle_preset=self.cycle.currentText())
        try: self.owner.backend.apply_settings(settings)
        except RuntimeError as exc: QMessageBox.warning(self,"Settings",str(exc)); return
        self.accept(); self.owner.sync_controls(); self.owner.refresh()


class DiagnosticsDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.owner=owner; self.setWindowTitle("Core Physics Diagnostics"); self.resize(800,740)
        layout=QVBoxLayout(self); self.profile=QLabel(); self.profile.setStyleSheet("font-size:15px;font-weight:bold;color:#67c7ff"); layout.addWidget(self.profile)
        tabs=QTabWidget(); layout.addWidget(tabs,1)
        reactivity_tab=QWidget(); reactivity_layout=QVBoxLayout(reactivity_tab); self.reactivity_text=QLabel(); self.reactivity_text.setFont(QFont("Consolas",10)); self.reactivity_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); reactivity_layout.addWidget(self.reactivity_text)
        self.plot=pg.PlotWidget(title="Control-rod worth"); self.plot.addLegend(); self.plot.showGrid(x=True,y=True,alpha=.25); self.plot.setLabel("bottom","Rod bank inserted",units="%"); self.plot.setLabel("left","Worth","pcm / pcm per %")
        self.integral=self.plot.plot(pen=pg.mkPen("#55aaff",width=2),name="Integral worth"); self.differential=self.plot.plot(pen=pg.mkPen("#ff9933",width=2),name="Differential worth"); reactivity_layout.addWidget(self.plot,1); tabs.addTab(reactivity_tab,"Reactivity balance")
        poisons_tab=QWidget(); poisons_layout=QVBoxLayout(poisons_tab); self.poisons_text=QLabel(); self.poisons_text.setFont(QFont("Consolas",10)); self.poisons_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); poisons_layout.addWidget(self.poisons_text); poisons_layout.addStretch(); tabs.addTab(poisons_tab,"Poisons and exposure")
        startup_tab=QWidget(); startup_layout=QVBoxLayout(startup_tab); self.startup_text=QLabel(); self.startup_text.setFont(QFont("Consolas",10)); self.startup_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); startup_layout.addWidget(self.startup_text)
        self.source=FloatSlider("External source strength (log10 model units)",-8,-3,-5,self.set_source,2); startup_layout.addWidget(self.source); startup_layout.addStretch(); tabs.addTab(startup_tab,"Startup instrumentation")
        close=QPushButton("CLOSE"); close.clicked.connect(self.close); layout.addWidget(close)

    def set_source(self,value):
        if self.owner.state.pedagogical_settings.advanced_physics: self.owner.backend.set_control("source_strength",10.0**value)

    def refresh(self):
        s=self.owner.state; advanced=s.pedagogical_settings.advanced_physics
        components=(("Rod bank",s.rho_rods),("SCRAM protection",s.rho_scram),("Manual trim",s.rho_manual),("Fuel Doppler",s.rho_fuel),("Moderator temperature",s.rho_moderator_temp),("Moderator density",s.rho_density),("Void",s.rho_void),("Boron",s.rho_boron),("Xe-135",s.rho_xe),("Sm-149",s.rho_sm),("Cycle depletion",s.rho_depletion if advanced else 0.0))
        balance="\n".join(f"{name:<24} {1e5*value:+9.1f} pcm" for name,value in components); mult="infinite/critical" if math.isinf(s.subcritical_multiplication) else f"{s.subcritical_multiplication:.2f}"
        insertion=self.owner.canonical.rod_insertion_from_withdrawn(s.rod_pos); differential=-self.owner.canonical.differential_rod_worth_pcm_per_pct(s.rod_pos,advanced)
        self.profile.setText(f"Active profile: {s.pedagogical_settings.physics_profile} | Initial condition: {s.pedagogical_settings.initial_condition}")
        self.reactivity_text.setText(f"{balance}\n{'-'*39}\n{'TOTAL':<24} {s.reactivity_pcm:+9.1f} pcm\n\nRod insertion            {insertion:9.2f} %\nDifferential worth       {differential:9.2f} pcm/% inserted")
        recommended=1000.0*max(0.0,1.0-s.exposure_efpd/s.cycle_length_efpd) if s.cycle_length_efpd else 0.0
        self.poisons_text.setText(f"I-135 index              {s.I:12.5f}\nXe-135 index             {s.Xe:12.5f}   ({1e5*s.rho_xe:+.1f} pcm)\nPm-149 index             {s.Pm:12.5f}\nSm-149 index             {s.Sm:12.5f}   ({1e5*s.rho_sm:+.1f} pcm)\n\nModerator density        {s.moderator_density:12.5f} relative\nVoid fraction            {100*s.void_fraction:12.3f} %\n\nExposure preset           {s.pedagogical_settings.cycle_preset}\nTeaching exposure         {s.exposure_efpd:9.2f} / {s.cycle_length_efpd:.0f} EFPD\nCycle excess reactivity   {1e5*s.rho_depletion:+9.1f} pcm\nIllustrative boron target {recommended:9.0f} ppm\nActual boron              {s.boron_ppm:9.0f} ppm")
        self.startup_text.setText(f"Active detector range      {s.instrument_range}\nTrue neutron power         {s.P:12.5e} fraction\nLog neutron level          {s.log_neutron_level:12.3f} decades\nExternal source            {s.source_strength:12.5e} model units\nSubcritical multiplication {mult}\n\nRange transitions: source < 1e-4, intermediate < 10%, power >= 10%.\n\nExternal-source adjustment is available only in Advanced core physics.")
        self.source.slider.setEnabled(advanced); self.source.value_label.setEnabled(advanced)
        if advanced: self.source.set_value(math.log10(max(s.source_strength,1e-8)))
        positions=np.arange(101); withdrawn=100.0-positions
        self.integral.setData(positions,[1e5*self.owner.canonical.rod_reactivity(v,advanced) for v in withdrawn]); self.differential.setData(positions,[-self.owner.canonical.differential_rod_worth_pcm_per_pct(v,advanced) for v in withdrawn])


class ReactorWindow(QMainWindow):
    def __init__(self, backend_cls, canonical):
        super().__init__(); self.backend=backend_cls(); self.canonical=canonical; self.speed=1.0; self.syncing=False; self.user_y_scale=False
        self.last_tick=time.perf_counter(); self.last_perf=self.last_tick; self.frames=self.steps=0; self.fps=self.sps=self.ui_ms=0.0
        self.kinetics_labels={canonical.kinetics_preset_label(n):n for n in canonical.KINETICS_PRESETS}; self.xenon_labels={canonical.xenon_preset_label(n):n for n in canonical.XENON_PRESETS}
        self.setWindowTitle("Reactor Physics and Kinetics Simulator - PyQtGraph"); self.resize(1500,920); self.setStyleSheet(STYLE); self._build()
        self.settings=SettingsDialog(self); self.diagnostics=DiagnosticsDialog(self)
        self.physics_timer=QTimer(self); self.physics_timer.setInterval(16); self.physics_timer.timeout.connect(self.tick); self.physics_timer.start()
        self.ui_timer=QTimer(self); self.ui_timer.setInterval(100); self.ui_timer.timeout.connect(self.refresh); self.ui_timer.start(); self.sync_controls(); self.refresh()

    @property
    def state(self): return self.backend.state

    def _button(self,text,callback,layout):
        b=QPushButton(text); b.clicked.connect(callback); layout.addWidget(b); return b

    def _build(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root)
        header=QHBoxLayout(); outer.addLayout(header); title=QLabel("NUCLEAR REACTOR CONTROL PANEL - V8\nOpen Nuclear Engineering Teaching Suite"); title.setStyleSheet("font-size:22px;font-weight:bold"); header.addWidget(title); header.addStretch(); self._button("ABOUT",lambda:QMessageBox.about(self,"About - Open Nuclear Engineering Teaching Suite",self.canonical.ABOUT_MESSAGE),header)
        commands=QHBoxLayout(); outer.addLayout(commands)
        self._button("START",self.backend.start,commands); self._button("PAUSE",self.backend.pause,commands); scram=self._button("SCRAM",self.backend.scram,commands); scram.setStyleSheet("background:#7b1820;border-color:#cc3945"); self._button("RESET",self.reset,commands)
        self.status=QLabel(); commands.addWidget(self.status); commands.addStretch(); self.perf=QLabel(); commands.addWidget(self.perf)
        lamps=QHBoxLayout(); outer.addLayout(lamps); self.lamps={}
        for key,label in (("power","HIGH PWR"),("temp","HI TEMP"),("flow","LOW FLOW"),("trip","TRIP")):
            w=QLabel(label); w.setAlignment(Qt.AlignmentFlag.AlignCenter); w.setFrameShape(QFrame.Shape.Box); w.setMinimumWidth(90); lamps.addWidget(w); self.lamps[key]=w
        lamps.addStretch(); splitter=QSplitter(); outer.addWidget(splitter,1)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); panel=QWidget(); scroll.setWidget(panel); controls=QVBoxLayout(panel); splitter.addWidget(scroll)
        modebox=QGroupBox("OPERATOR CONTROLS"); form=QVBoxLayout(modebox); controls.addWidget(modebox)
        self.mode=QComboBox(); self.mode.addItem("Manual","manual"); self.mode.addItem("Auto power hold","auto"); self.mode.addItem("Load-follow demo","load_follow"); self.mode.currentIndexChanged.connect(self.mode_changed); form.addWidget(QLabel("Operating mode")); form.addWidget(self.mode)
        specs=(("rod","Rod insertion",0,100,lambda v:self.backend.set_rod_insertion(v),1," %"),("target","Power target (Auto mode)",30,120,lambda v:self.backend.set_control("setpoint",v/100),1," %"),("flow","Coolant flow",20,120,lambda v:self.backend.set_control("coolantFlow",v),1," %"),("sink","Heat sink",30,120,lambda v:self.backend.set_control("heatSink",v),1," %"),("rho","Manual reactivity",-500,500,lambda v:self.backend.set_control("rho_manual",v*1e-5),0," pcm"),("boron","Boron",0,1000,lambda v:self.backend.set_control("boron_ppm",v),0," ppm"),("noise","Detector noise",0,8,lambda v:self.backend.set_control("noiseAmp",v),1," %"),("speed","Simulation speed",.25,8,self.set_speed,2,"x"))
        self.controls={}
        for key,label,lo,hi,fn,dec,suffix in specs: self.controls[key]=FloatSlider(label,lo,hi,lo,fn,dec,suffix); form.addWidget(self.controls[key])
        row=QHBoxLayout(); form.addLayout(row); self._button("-5 pcm",lambda:self.trim(-5),row); self._button("+5 pcm",lambda:self.trim(5),row); self._button("STEP 1 s",self.step,row)
        self._button("EXPORT CSV",self.export_csv,form); self._button("INSTRUCTOR: PEDAGOGICAL SETTINGS",self.show_settings,form); self._button("OPEN CORE PHYSICS DIAGNOSTICS",self.show_diagnostics,form)
        self.scaling=QLabel(); self.scaling.setWordWrap(True); self.scaling.setStyleSheet("color:#ffe0a0"); form.addWidget(self.scaling)
        faults=QGroupBox("FAULT INJECTION"); fl=QVBoxLayout(faults); controls.addWidget(faults); self.faults={}
        labels=(("Stuck rod","fault_stuck_rod"),("Partial SCRAM","fault_partial_scram"),("Pump trip","fault_pump_trip"),("Heat-sink loss","fault_heat_sink_loss"),("Detector bias","fault_detector_bias"),("Frozen detector","fault_frozen_detector"),("Boron dilution","fault_boron_dilution"),("Auto controller failure","fault_auto_failure"),("Low-flow trip fail","fault_low_flow_trip_fail"))
        for label,key in labels:
            cb=QCheckBox(label); cb.toggled.connect(lambda active,k=key:self.backend.toggle_fault(k,active) if not self.syncing else None); fl.addWidget(cb); self.faults[key]=cb
        self.controls["severity"]=FloatSlider("Fault severity",0,100,60,lambda v:self.backend.set_control("fault_severity",v),0," %"); fl.addWidget(self.controls["severity"])
        live=QGroupBox("LIVE READOUT"); ll=QVBoxLayout(live); self.readout=QLabel(); self.readout.setFont(QFont("Consolas",9)); self.readout.setWordWrap(True); ll.addWidget(self.readout); controls.addWidget(live); controls.addStretch()
        right_scroll=QScrollArea(); right_scroll.setWidgetResizable(True); right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right=QWidget(); right.setMinimumSize(900,700); rl=QVBoxLayout(right); right_scroll.setWidget(right); splitter.addWidget(right_scroll); splitter.setSizes([390,1080])
        top=QHBoxLayout(); rl.addLayout(top); mimicbox=QGroupBox("PRIMARY SYSTEM MIMIC"); ml=QVBoxLayout(mimicbox); self.mimic=PlantMimic(self.canonical); ml.addWidget(self.mimic); top.addWidget(mimicbox,3)
        meters=QGroupBox("INSTRUMENTS"); il=QVBoxLayout(meters); top.addWidget(meters,2); self.bars={}
        for key,label in (("power","NEUTRON POWER"),("heat","TOTAL HEAT"),("flow","COOLANT FLOW"),("temp","FUEL TEMPERATURE")):
            il.addWidget(QLabel(label)); bar=QProgressBar(); bar.setRange(0,1000); il.addWidget(bar); self.bars[key]=bar
        self.reactivity=QLabel(); self.period=QLabel(); il.addWidget(self.reactivity); il.addWidget(self.period); il.addStretch()
        pg.setConfigOptions(antialias=False,useOpenGL=True,background="#0b1117",foreground="#dceaf4")
        plot_tools=QHBoxLayout(); plot_tools.addWidget(QLabel("Scroll over the left axis to rescale Y.")); plot_tools.addStretch(); self._button("RESET Y SCALE (0-120%)",self.reset_y_scale,plot_tools); rl.addLayout(plot_tools)
        self.plot=pg.PlotWidget(title="GPU strip chart - 40-second rolling window"); self.plot.addLegend(); self.plot.showGrid(x=True,y=True,alpha=.25); self.plot.setLabel("bottom","Simulation time",units="s"); self.plot.setLabel("left","Percent / scaled temperature"); self.plot.getViewBox().sigRangeChangedManually.connect(self.plot_range_changed); rl.addWidget(self.plot,1)
        colors=("#55aaff","#eeeeee","#ff9933","#b576d8","#55dd88","#ff6655"); names=("Measured power %","True power %","Total heat %","Decay heat %","Target %","Fuel temp / 10")
        self.curves=[self.plot.plot(pen=pg.mkPen(c,width=2),name=n) for c,n in zip(colors,names)]

    def set_speed(self,value): self.speed=float(value)
    def plot_range_changed(self,axes):
        if len(axes)>1 and axes[1]: self.user_y_scale=True
    def reset_y_scale(self):
        self.user_y_scale=False; self.plot.setYRange(0,120,padding=0)
    def mode_changed(self,_index):
        if self.syncing: return
        mode=self.mode.currentData(); self.backend.set_mode(mode); self.update_mode_controls(mode)
    def update_mode_controls(self,mode):
        target=self.controls.get("target")
        if target is None: return
        target.setEnabled(mode != "load_follow")
        target.setToolTip("The demo generates a 65-105% demand automatically." if mode == "load_follow" else "Demand followed by the automatic rod controller in Auto power hold mode.")
    def trim(self,pcm): self.backend.trim_reactivity(pcm); self.refresh()
    def step(self): self.backend.step(); self.refresh()
    def reset(self): self.backend.reset(); self.sync_controls(); self.refresh()
    def show_settings(self):
        if self.state.running: self.state.add_log("Pause required before changing pedagogical settings."); self.refresh(); return
        self.settings.populate(self.state.pedagogical_settings); self.settings.show(); self.settings.raise_(); self.settings.activateWindow()
    def show_diagnostics(self): self.diagnostics.refresh(); self.diagnostics.show(); self.diagnostics.raise_(); self.diagnostics.activateWindow()

    def export_csv(self):
        default=Path.cwd()/"exports"/f"reactor_sim_run_{datetime.now():%Y%m%d_%H%M%S}.csv"; default.parent.mkdir(exist_ok=True)
        path,_=QFileDialog.getSaveFileName(self,"Export reactor run",str(default),"CSV files (*.csv)")
        if path:
            if not path.lower().endswith(".csv"): path += ".csv"
            rows=self.backend.export_csv(path); self.state.add_log(f"CSV export saved: {rows} rows to {Path(path).name}."); self.refresh()

    def sync_controls(self):
        s=self.state; self.syncing=True
        try:
            index=self.mode.findData(s.mode); self.mode.setCurrentIndex(max(0,index)); self.update_mode_controls(s.mode); values={"rod":self.canonical.rod_insertion_from_withdrawn(s.rod_pos),"target":100*s.setpoint,"flow":s.coolantFlow,"sink":s.heatSink,"rho":1e5*s.rho_manual,"boron":s.boron_ppm,"noise":s.noiseAmp,"speed":self.speed,"severity":s.fault_severity}
            for key,value in values.items(): self.controls[key].set_value(value)
            for key,cb in self.faults.items(): cb.setChecked(bool(getattr(s,key)))
        finally: self.syncing=False

    def tick(self):
        now=time.perf_counter(); elapsed=min(now-self.last_tick,.10); self.last_tick=now; self.frames+=1
        if self.state.running: self.steps += self.backend.advance_elapsed(elapsed,self.speed)
        if now-self.last_perf>=1.0:
            span=now-self.last_perf; self.fps=self.frames/span; self.sps=self.steps/span; self.frames=self.steps=0; self.last_perf=now

    def refresh(self):
        begun=time.perf_counter(); s=self.state; status="SCRAM" if s.scram else ("RUNNING" if s.running else "PAUSED")
        self.status.setText(f"STATUS: {status}  |  SIM TIME {s.time:07.2f} s"); self.perf.setText(f"Render: {self.fps:5.1f} FPS | Physics: {self.sps:6.0f} steps/s | UI update: {self.ui_ms:5.2f} ms")
        active={"power":s.powerPct>.95*100*s.tripHighPower,"temp":s.fuelT>.95*s.tripHighFuelTemp,"flow":s.coolantFlow<1.05*s.tripLowFlow,"trip":s.scram}
        for key,lamp in self.lamps.items(): lamp.setStyleSheet(f"padding:5px;background:{'#e53935' if active[key] else '#262f36'};color:{'#ffffff' if active[key] else '#69747c'}")
        self.readout.setText("\n".join(self.backend.model.compose_readout())); settings=s.pedagogical_settings; self.scaling.setText("PEDAGOGICAL SCALING: VALIDATED CLASSROOM DEFAULTS" if settings.is_baseline else f"ACTIVE: {settings.kinetics_preset} | {settings.xenon_preset} | {settings.physics_profile}")
        period="stable" if not math.isfinite(s.period) else f"{s.period:.2f} s"; self.reactivity.setText(f"Reactivity: {s.reactivity_pcm:+8.1f} pcm"); self.period.setText(f"Reactor period: {period}")
        for key,value,maximum,suffix in (("power",s.measuredPct,150,"%"),("heat",s.heatPct,150,"%"),("flow",s.coolantFlow,120,"%"),("temp",s.fuelT,900," C")):
            bar=self.bars[key]; bar.setValue(round(1000*max(0,min(value/maximum,1)))); bar.setFormat(f"{value:7.2f}{suffix}")
        valid=~np.isnan(s.tHist); idx=np.flatnonzero(valid)[-PLOT_POINTS:]; x=s.tHist[idx]; arrays=(s.pHist,s.truePHist,s.heatHist,s.decayHist,s.targetHist,s.tfHist)
        for curve,data in zip(self.curves,arrays): curve.setData(x,data[idx])
        now=float(x[-1]) if x.size else 0.0; self.plot.setXRange(max(0,now-VISIBLE_WINDOW_S) if now>VISIBLE_WINDOW_S else 0,now if now>VISIBLE_WINDOW_S else VISIBLE_WINDOW_S,padding=0)
        if not self.user_y_scale: self.plot.setYRange(0,max(120,min(320,max(s.powerPct,s.heatPct)*1.15)),padding=0)
        self.mimic.state=s; self.mimic.update(); self.sync_controls()
        if self.diagnostics.isVisible(): self.diagnostics.refresh()
        self.ui_ms=(time.perf_counter()-begun)*1000


def main(model_dir: Path | None = None):
    if model_dir is None:
        parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--model-dir",type=Path,default=DEFAULT_MODEL_DIR); model_dir=parser.parse_args().model_dir
    backend_cls,canonical=load_backend(model_dir); app=QApplication.instance() or QApplication(sys.argv); app.setApplicationName("Open Nuclear Suite Reactor Simulator"); window=ReactorWindow(backend_cls,canonical); window.show(); return app.exec()


if __name__ == "__main__": raise SystemExit(main())
