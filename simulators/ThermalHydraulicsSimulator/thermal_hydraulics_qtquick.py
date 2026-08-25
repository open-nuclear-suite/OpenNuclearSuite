"""Qt Quick + Qt Graphs responsiveness comparison for Thermal Hydraulics."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, Property, QPointF, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from thermal_hydraulics_gui_backend import SCENARIOS, ThermalHydraulicsGUIBackend


QML = r'''
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtGraphs

ApplicationWindow {
    id: root; visible: true; width: 1500; height: 900
    title: "Thermal Hydraulics — Qt Quick + Qt Graphs"
    color: "#0d1218"
    Material.theme: Material.Dark
    Material.primary: "#1d4e70"
    Material.accent: "#67c7ff"
    palette { window: "#0d1218"; windowText: "#eef5fb"; base: "#111820"; text: "#eef5fb"; button: "#1d4e70"; buttonText: "white" }
    property color accent: "#67c7ff"
    Connections { target: controller; function onUpdated() {} }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 12; spacing: 8
        RowLayout {
            Layout.fillWidth: true; Layout.preferredHeight: 78; Layout.minimumHeight: 78; Layout.maximumHeight: 78
            ColumnLayout { Layout.fillWidth: true
                Label { text: "LIGHT WATER REACTOR THERMAL-HYDRAULICS TRAINING PANEL"; font.pixelSize: 22; font.bold: true }
                Label { text: "Qt Quick + Qt Graphs comparison • GPU scene graph • native secondary windows"; color: "#aebdca" }
            }
            Image { source: controller.bannerUrl; fillMode: Image.PreserveAspectFit; Layout.preferredWidth: 650; Layout.preferredHeight: 72; Layout.maximumHeight: 72 }
        }
        Frame {
            Layout.fillWidth: true; Layout.preferredHeight: 86; Layout.minimumHeight: 86; Layout.maximumHeight: 86
            RowLayout {
                anchors.fill: parent
                ColumnLayout { Label { text: "SIMULATION"; color: root.accent; font.bold: true }
                    RowLayout {
                        Button { text: "START"; onClicked: controller.start() }
                        Button { text: "PAUSE"; onClicked: controller.pause() }
                        Button { text: "SCRAM"; onClicked: controller.scram() }
                        Button { text: "RESET"; onClicked: controller.reset() }
                    }
                }
                Rectangle { width: 1; Layout.fillHeight: true; color: "#42505c" }
                ColumnLayout { Label { text: "SCENARIOS"; color: root.accent; font.bold: true }
                    RowLayout { Repeater { model: ["NORMAL","SBLOCA","LBLOCA","LOFA","LOHS","SBO"]
                        Button { text: modelData; onClicked: controller.scenario(modelData) }
                    } }
                }
                Item { Layout.fillWidth: true }
                Button { text: "HOT CHANNEL — NATIVE WINDOW"; onClicked: hotWindow.show() }
            }
        }
        Label { Layout.preferredHeight: 24; Layout.maximumHeight: 24; text: controller.status; color: controller.tripped ? "#ff795f" : "#69e09b"; font.bold: true }
        SplitView {
            Layout.fillWidth: true; Layout.fillHeight: true; orientation: Qt.Horizontal
            ScrollView {
                SplitView.preferredWidth: 375; SplitView.minimumWidth: 300
                ColumnLayout { width: 350; spacing: 9
                    Label { text: "PRIMARY AND SAFETY CONTROLS"; color: root.accent; font.bold: true }
                    Repeater { model: [
                        ["rod","Rod insertion %",0,100], ["boron","Soluble boron ppm",0,2500],
                        ["pump","Primary pump %",0,120], ["sg","SG heat removal %",0,140],
                        ["break","LOCA break size %",0,100], ["eccs","Manual ECCS %",0,100],
                        ["afw","Aux feedwater %",0,100], ["rhr","RHR cooldown %",0,100]
                    ]
                        ColumnLayout { Layout.fillWidth: true
                            Label { text: modelData[1] + "  " + control.value.toFixed(1) }
                            Slider { id: control; Layout.fillWidth: true; from: modelData[2]; to: modelData[3]; value: controller.controlValue(modelData[0]); onMoved: controller.setControl(modelData[0], value) }
                        }
                    }
                    Label { text: "LIVE READOUT"; color: root.accent; font.bold: true }
                    Label { text: controller.readout; font.family: "Consolas"; lineHeight: 1.2 }
                }
            }
            ColumnLayout {
                SplitView.fillWidth: true
                RowLayout { Layout.fillWidth: true
                    Repeater { model: controller.metrics
                        Frame { Layout.fillWidth: true; ColumnLayout { anchors.fill: parent
                            Label { text: modelData[0]; color: "#aebdca" }
                            Label { text: modelData[1]; font.pixelSize: 20; font.bold: true }
                        } }
                    }
                }
                GraphsView {
                    Layout.fillWidth: true; Layout.fillHeight: true; theme: GraphsTheme { colorScheme: GraphsTheme.ColorScheme.Dark }
                    axisX: ValueAxis { id: timeAxis; min: controller.xMin; max: controller.xMax; titleText: "Simulation time (s)" }
                    axisY: ValueAxis { min: 0; max: 150; titleText: "Power / inventory (%)" }
                    LineSeries { objectName: "powerSeries"; name: "Power %" }
                    LineSeries { objectName: "inventorySeries"; name: "Inventory %" }
                }
            }
        }
    }
    Window {
        id: hotWindow; width: 1180; height: 820; title: "Representative 1-D Hot Channel — Qt Quick"; color: "#0d1218"
        transientParent: null
        ColumnLayout { anchors.fill: parent; anchors.margins: 12
            Label { text: controller.hotSummary; color: "white"; wrapMode: Text.Wrap; Layout.fillWidth: true }
            GraphsView {
                Layout.fillWidth: true; Layout.fillHeight: true; theme: GraphsTheme { colorScheme: GraphsTheme.ColorScheme.Dark }
                axisX: ValueAxis { min: 0; max: 4; titleText: "Distance from inlet (m)" }
                axisY: ValueAxis { min: 250; max: 1300; titleText: "Temperature (°C)" }
                LineSeries { objectName: "hotFuelSeries"; name: "Fuel centre" }
                LineSeries { objectName: "hotCladSeries"; name: "Clad surface" }
                LineSeries { objectName: "hotCoolantSeries"; name: "Bulk coolant" }
            }
        }
    }
}
'''


class Controller(QObject):
    updated = Signal()

    def __init__(self):
        super().__init__()
        self.backend = ThermalHydraulicsGUIBackend()
        self.last = time.perf_counter()
        self.root = None
        self.timer = QTimer(self, interval=16)
        self.timer.timeout.connect(self.tick)
        self.ui_timer = QTimer(self, interval=100)
        self.ui_timer.timeout.connect(self.refresh)

    @Slot()
    def start(self): self.backend.start(); self.updated.emit()
    @Slot()
    def pause(self): self.backend.pause(); self.updated.emit()
    @Slot()
    def scram(self): self.backend.scram(); self.updated.emit()
    @Slot()
    def reset(self): self.backend.reset(); self.updated.emit()
    @Slot(str)
    def scenario(self, name): self.backend.select_scenario(name); self.updated.emit()
    @Slot(str, float)
    def setControl(self, name, value): self.backend.set_control(name, value)
    @Slot(str, result=float)
    def controlValue(self, name): return float(self.backend.sim.control_vars[name].get())

    def tick(self):
        now = time.perf_counter()
        self.backend.advance_elapsed(min(now-self.last, .1))
        self.last = now

    def bind_root(self, root):
        self.root = root
        self.timer.start(); self.ui_timer.start(); self.refresh()

    def replace(self, name, xs, ys):
        series = self.root.findChild(QObject, name) if self.root else None
        if series is not None:
            series.clear()
            pairs = list(zip(xs, ys))[-500:]
            for x, y in pairs:
                series.append(float(x), float(y))

    def refresh(self):
        s, h = self.backend.state, self.backend.state.hist
        xs = list(h.t)
        self.replace("powerSeries", xs, h.pow)
        self.replace("inventorySeries", xs, h.M)
        result = self.backend.sim.hot_channel_result
        if result is not None:
            self.replace("hotFuelSeries", result.z_m, result.fuel_centerline_temperature_C)
            self.replace("hotCladSeries", result.z_m, result.clad_surface_temperature_C)
            self.replace("hotCoolantSeries", result.z_m, result.bulk_temperature_C)
        self.updated.emit()

    @Property(str, notify=updated)
    def status(self):
        state = "RUNNING" if self.backend.running else "PAUSED"
        return f"{state}  |  {self.backend.state.scenario_name}  |  t = {self.backend.state.t:.2f} s"
    @Property(bool, notify=updated)
    def tripped(self): return bool(self.backend.state.trip)
    @Property(str, constant=True)
    def bannerUrl(self): return QUrl.fromLocalFile(str(Path(__file__).resolve().parents[2] / "utm.fkt.logo.png")).toString()
    @Property(float, notify=updated)
    def xMin(self): return max(0.0, self.backend.state.t-40)
    @Property(float, notify=updated)
    def xMax(self): return max(40.0, self.backend.state.t)
    @Property('QVariantList', notify=updated)
    def metrics(self):
        s = self.backend.state
        return [["POWER", f"{100*s.n:.1f}%"], ["PRESSURE", f"{s.P:.2f} MPa"], ["INVENTORY", f"{100*s.M:.1f}%"], ["CLAD", f"{s.Tcl:.0f} °C"]]
    @Property(str, notify=updated)
    def readout(self):
        s = self.backend.state
        return f"Fuel / clad / coolant  {s.Tf:.0f} / {s.Tcl:.0f} / {s.Tc:.1f} °C\nVoid fraction             {100*s.void_fraction:.1f}%\nCHF ratio                 {s.chf_ratio:.2f}\nAxial MDNBR               {s.hot_min_dnbr:.2f}"
    @Property(str, notify=updated)
    def hotSummary(self):
        s = self.backend.state
        return f"Peak fuel {s.hot_peak_fuel_C:.1f} °C | Peak clad {s.hot_peak_clad_C:.1f} °C | Outlet {s.hot_outlet_C:.1f} °C | MDNBR {s.hot_min_dnbr:.2f}"


def main():
    app = QGuiApplication(sys.argv)
    controller = Controller()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.loadData(QML.encode(), QUrl("qrc:/thermal_hydraulics_qtquick.qml"))
    if not engine.rootObjects(): raise SystemExit("Qt Quick UI failed to load")
    controller.bind_root(engine.rootObjects()[0])
    raise SystemExit(app.exec())


if __name__ == "__main__": main()
