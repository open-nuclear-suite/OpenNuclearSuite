"""Full PySide6/PyQtGraph front end for the Core Loading Explorer.

The numerical and fuel-management implementation remains in
``core_loading_thorium_poc_fixed.CoreModel``.  This module deliberately owns
only presentation and scheduling so calculations never depend on a paint
event.
"""

from __future__ import annotations

import copy
import math
import sys
import webbrowser
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QMimeData, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QDrag, QFont, QPainter, QPen, QVector3D
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QListWidget, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

try:
    import pyqtgraph.opengl as gl
except ImportError:  # The 2-D UI remains usable before PyOpenGL is installed.
    gl = None

from core_loading_thorium_poc_fixed import (
    ASSEMBLY_TYPES, GRID_SIZE, MAX_BORON_PPM, MODULE_NAME,
    CoreModel,
)


STYLE = """
QWidget { background:#0f1115; color:#e6edf3; font:9pt 'Segoe UI'; }
QGroupBox { border:1px solid #39434d; border-radius:5px; margin-top:10px;
            padding-top:9px; font-weight:bold; }
QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }
QPushButton { background:#29313a; border:1px solid #56616d; border-radius:4px;
              padding:6px; font-weight:600; }
QPushButton:hover { background:#37434e; } QPushButton:pressed { background:#20262d; }
QComboBox,QDoubleSpinBox { background:#171c22; border:1px solid #56616d;
                          border-radius:3px; padding:4px; }
QTabWidget::pane { border:1px solid #39434d; }
QTabBar::tab { background:#20262d; padding:7px 12px; }
QTabBar::tab:selected { background:#39434d; }
QTableWidget,QListWidget,QTextBrowser { background:#11161c; gridline-color:#39434d; }
QHeaderView::section { background:#20262d; padding:5px; border:0; }
QLabel#value { background:#07120b; color:#9cff9c; padding:3px 6px;
               font-family:Consolas; font-weight:bold; }
"""


METRICS = {
    "Flux": ("flux", "Relative neutron flux", "viridis"),
    "Fast flux": ("fast_flux", "Relative fast flux", "plasma"),
    "Thermal flux": ("thermal_flux", "Relative thermal flux", "viridis"),
    "Power": ("power", "Power / core average", "inferno"),
    "Power index": ("power_index", "Fissile-weighted power", "inferno"),
    "Power change: previous": ("_power_previous", "Change in normalized power", "coolwarm"),
    "Power change: BOC": ("_power_boc", "Change in normalized power", "coolwarm"),
    "Burnup": ("burnup", "GWd/tHM", "magma"),
    "Breeding": ("breeding", "Relative U-233 production", "viridis"),
    "Fuel temperature": ("fuel_temperature", "Fuel temperature (K)", "inferno"),
    "Moderator temperature": ("moderator_temperature", "Moderator temperature (K)", "plasma"),
    "Moderator density": ("moderator_density", "Relative density", "viridis"),
    "Xenon-135": ("xenon135_inventory", "Xe-135 inventory", "cividis"),
    "Samarium-149": ("samarium149_inventory", "Sm-149 inventory", "cividis"),
    "Control insertion": ("control_fraction", "Inserted fraction", "grey"),
}


class CoreMap(pg.PlotWidget):
    cellClicked = Signal(int, int, int)
    cellHovered = Signal(int, int)
    hoverCleared = Signal()
    tokenDropped = Signal(str, int, int)

    def __init__(self):
        super().__init__()
        self.setAspectLocked(True); self.invertY(True)
        self.setRange(xRange=(0, GRID_SIZE), yRange=(0, GRID_SIZE), padding=.03)
        self.getPlotItem().hideButtons(); self.setMenuEnabled(False)
        self.getPlotItem().showAxis("top"); self.getPlotItem().hideAxis("bottom")
        self.getPlotItem().getAxis("top").setTicks([[(i + .5, f"C{i+1:02d}") for i in range(GRID_SIZE)]])
        self.getPlotItem().getAxis("left").setTicks([[(i + .5, f"R{i+1:02d}") for i in range(GRID_SIZE)]])
        self.image = pg.ImageItem(axisOrder="row-major"); self.image.setZValue(0); self.addItem(self.image)
        # One batched path gives every active assembly a subtle Tk-like cell
        # boundary without creating 89 individual graphics objects.
        xs, ys = [], []
        for r in range(GRID_SIZE):
          for c in range(GRID_SIZE):
            xs.extend((c,c+1,c+1,c,c,np.nan)); ys.extend((r,r,r+1,r+1,r,np.nan))
        self.grid_lines = pg.PlotDataItem(xs,ys,pen=pg.mkPen(0,0,0,230,width=1.05))
        self.grid_lines.setZValue(20)
        self.addItem(self.grid_lines)
        self.selection = pg.PlotDataItem(pen=pg.mkPen(55,145,255,255,width=2.6)); self.selection.setZValue(40); self.addItem(self.selection)
        self.empty_borders = pg.PlotDataItem(pen=pg.mkPen(235,240,245,230,width=1.2)); self.empty_borders.setZValue(25); self.addItem(self.empty_borders)
        self.labels: list[pg.TextItem] = []
        self._hovered=None; self.scene().sigMouseMoved.connect(self._scene_mouse_moved)
        self.setAcceptDrops(True)

    def _scene_mouse_moved(self,pos):
        if not self.sceneBoundingRect().contains(pos):
            if self._hovered is not None: self._hovered=None; self.hoverCleared.emit()
            return
        point=self.getPlotItem().vb.mapSceneToView(pos); cell=(int(point.y()),int(point.x()))
        if 0<=cell[0]<GRID_SIZE and 0<=cell[1]<GRID_SIZE:
            if cell!=self._hovered: self._hovered=cell; self.cellHovered.emit(*cell)
        elif self._hovered is not None: self._hovered=None; self.hoverCleared.emit()

    def mousePressEvent(self, event):
        point = self.getPlotItem().vb.mapSceneToView(event.position())
        row, col = int(point.y()), int(point.x())
        if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
            self.cellClicked.emit(row, col, int(event.button().value))
        super().mousePressEvent(event)

    def dragEnterEvent(self,event):
        if event.mimeData().hasFormat("application/x-core-assembly"): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self,event):
        if event.mimeData().hasFormat("application/x-core-assembly"): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self,event):
        if not event.mimeData().hasFormat("application/x-core-assembly"): super().dropEvent(event); return
        point=self.getPlotItem().vb.mapSceneToView(self.mapToScene(event.position().toPoint())); row,col=int(point.y()),int(point.x())
        if 0<=row<GRID_SIZE and 0<=col<GRID_SIZE:
            token=bytes(event.mimeData().data("application/x-core-assembly")).decode("utf-8"); self.tokenDropped.emit(token,row,col); event.acceptProposedAction()

    def render_model(self, model: CoreModel, field: np.ndarray, _cmap: str, show_values: bool, selected, show_ids=False, outline_empty=False):
        # This is a loading map, not a result heatmap: preserve the palette's
        # categorical assembly colors regardless of the selected result metric.
        rgba = np.zeros((GRID_SIZE, GRID_SIZE, 4), dtype=np.uint8)
        rgba[..., :3] = (17, 22, 28); rgba[..., 3] = 255
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if model.mask[r, c]:
                    color = QColor(ASSEMBLY_TYPES[str(model.layout[r, c])].color)
                    rgba[r, c] = (color.red(), color.green(), color.blue(), 255)
        self.image.setImage(rgba, autoLevels=False)
        for label in self.labels: self.removeItem(label)
        self.labels.clear()
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if not model.mask[r, c]: continue
                key, aid = str(model.layout[r, c]), str(model.assembly_ids[r, c])
                text = "" if key == "EMPTY" else ASSEMBLY_TYPES[key].short
                if show_ids and key != "EMPTY": text += f"\n{aid[-4:]}\n{field[r,c]:.0f}"
                elif show_values and key != "EMPTY": text += f"\n{field[r,c]:.2f}"
                bg = QColor(ASSEMBLY_TYPES[key].color)
                luminance = .299 * bg.red() + .587 * bg.green() + .114 * bg.blue()
                foreground = "#101419" if luminance > 155 else "white"
                label = pg.TextItem(text, color=foreground, anchor=(.5, .5))
                text_option=label.textItem.document().defaultTextOption(); text_option.setAlignment(Qt.AlignmentFlag.AlignCenter); label.textItem.document().setDefaultTextOption(text_option)
                label.setZValue(30)
                label.setPos(c + .5, r + .5); self.addItem(label); self.labels.append(label)
        if selected is None: self.selection.setData([],[])
        else:
            r,c=selected; self.selection.setData([c,c+1,c+1,c,c],[r,r,r+1,r+1,r])
        ex,ey=[],[]
        if outline_empty:
            for r,c in zip(*np.where(model.mask&(model.assembly_ids==""))): ex.extend((c,c+1,c+1,c,c,np.nan)); ey.extend((r,r,r+1,r+1,r,np.nan))
        self.empty_borders.setData(ex,ey)


class ColorScale(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedWidth(92); self.low=0.; self.high=1.; self.label="Value"; self.colors=np.zeros((100,4)); self.colors[:,3]=1
    def set_scale(self,low,high,label,cmap):
        self.low,self.high,self.label=low,high,label; self.colors=pg.colormap.get(cmap,source="matplotlib").map(np.linspace(0,1,100),mode="byte"); self.update()
    def paintEvent(self,_event):
        p=QPainter(self); top,bottom,x,width=18,self.height()-20,8,20; span=max(bottom-top,1)
        for i,color in enumerate(self.colors):
            y=bottom-(i+1)*span/len(self.colors); p.fillRect(x,int(y),width,max(2,int(span/len(self.colors))+1),QColor(*color))
        p.setPen(QColor("#dce6ee")); p.drawRect(x,top,width,span); p.drawText(33,top+5,f"{self.high:.3g}"); p.drawText(33,(top+bottom)//2+4,f"{(self.low+self.high)/2:.3g}"); p.drawText(33,bottom,f"{self.low:.3g}")
        p.save(); p.translate(82,self.height()/2); p.rotate(-90); p.drawText(-self.height()/3,0,self.label); p.restore()


if gl is not None:
    class PannableGLView(gl.GLViewWidget):
        """GL view with reliable explicit middle-button camera-target panning."""
        def __init__(self):
            super().__init__(); self._middle_pan_position=None
        def mousePressEvent(self,event):
            if event.button()==Qt.MouseButton.MiddleButton:
                self._middle_pan_position=event.position(); self.setCursor(Qt.CursorShape.ClosedHandCursor); event.accept(); return
            super().mousePressEvent(event)
        def mouseMoveEvent(self,event):
            if self._middle_pan_position is not None and event.buttons()&Qt.MouseButton.MiddleButton:
                position=event.position(); delta=position-self._middle_pan_position; self._middle_pan_position=position
                self.pan(delta.x(),delta.y(),0,relative="view-upright"); event.accept(); return
            super().mouseMoveEvent(event)
        def mouseReleaseEvent(self,event):
            if event.button()==Qt.MouseButton.MiddleButton:
                self._middle_pan_position=None; self.unsetCursor(); event.accept(); return
            super().mouseReleaseEvent(event)


class SurfaceView(QWidget):
    """Rotatable, zoomable interpolated PyQtGraph OpenGL result surface."""
    def __init__(self):
        super().__init__(); layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(3)
        self.surface = None
        if gl is None:
            note = QLabel("The 3-D surface requires PyOpenGL.\nInstall the updated requirements.txt and restart.")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(note); self.view = None; return
        heading=QHBoxLayout(); title=QLabel("INTERPOLATED SURFACE"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); title.setStyleSheet("font-weight:700; font-size:11pt"); heading.addWidget(title,1); hint=QLabel("Left-drag rotate · middle-drag pan · wheel zoom"); hint.setStyleSheet("color:#aebdca"); heading.addWidget(hint); reset=QPushButton("Reset camera"); reset.clicked.connect(self.reset_camera); heading.addWidget(reset); layout.addLayout(heading)
        body=QHBoxLayout(); self.view = PannableGLView(); self.view.opts["center"]=QVector3D(0,0,1.6); self.view.setCameraPosition(distance=24, elevation=36, azimuth=-55); body.addWidget(self.view,1); self.color_scale=ColorScale(); body.addWidget(self.color_scale); layout.addLayout(body,1)
        grid = gl.GLGridItem(); grid.setSize(10, 10); grid.setSpacing(1, 1); self.view.addItem(grid)
        axes=gl.GLAxisItem(); axes.setSize(6,6,5); axes.translate(-5,-5,0); self.view.addItem(axes)
        self.axis_font=QFont("Segoe UI",8)
        self.view.addItem(gl.GLTextItem(pos=(-1.2,-6.0,0),text="Core column",color=(220,230,238,255),font=self.axis_font))
        self.view.addItem(gl.GLTextItem(pos=(-6.4,-1.0,0),text="Core row",color=(220,230,238,255),font=self.axis_font))
        for value in range(0,11,2):
            self.view.addItem(gl.GLTextItem(pos=(value-5,-5.55,0),text=str(value),color=(205,216,225,255),font=self.axis_font))
            self.view.addItem(gl.GLTextItem(pos=(-5.55,value-5,0),text=str(value),color=(205,216,225,255),font=self.axis_font))
        self.z_labels=[]

    def reset_camera(self):
        if self.view is not None:
            self.view.opts["center"]=QVector3D(0,0,1.6); self.view.setCameraPosition(distance=24,elevation=36,azimuth=-55)

    @staticmethod
    def interpolate(model, field, mode):
        axis = np.linspace(0, GRID_SIZE - 1, 81); x, y = np.meshgrid(axis, axis)
        active = model.mask & (model.layout != "EMPTY"); rows, cols = np.nonzero(active)
        if not rows.size: return axis, np.zeros_like(x)
        distance = (x[..., None] - cols) ** 2 + (y[..., None] - rows) ** 2
        weights = 1.0 / np.maximum(distance, .018)
        z = np.sum(weights * field[rows, cols], axis=2) / np.sum(weights, axis=2)
        return axis, z

    def update_surface(self, model, field, mode, cmap, scale_label=None, levels=None):
        if self.view is None: return
        axis, z = self.interpolate(model, field, mode)
        active=model.mask&(model.layout!="EMPTY"); actual=field[active]
        if levels is None: low=float(np.nanmin(actual)) if actual.size else 0.; high=float(np.nanmax(actual)) if actual.size else 1.
        else: low,high=levels
        scale=max(high-low,1e-12); normalized=np.clip((z-low)/scale,0,1)
        coords=np.linspace(0,GRID_SIZE-1,normalized.shape[0]); xx,yy=np.meshgrid(coords,coords)
        outside=np.maximum(np.hypot(xx-5,yy-5)-5.15,0)
        # Apply the core-edge taper after range normalization. This preserves
        # useful vertical contrast for narrow-range fields such as density,
        # without generating the sharp clipped teeth visible in the old view.
        taper=np.exp(-2.0*outside)
        if low<0.0<high:
            zero_level=(0.0-low)/scale; normalized=zero_level+(normalized-zero_level)*taper
        else:
            normalized*=taper
        # A fixed five-unit visual height makes low-range density/control data
        # legible and prevents temperature/burnup surfaces becoming unzoomably tall.
        display_z=normalized*5.0
        colors = pg.colormap.get(cmap, source="matplotlib").map(normalized, mode="float")
        if colors.shape[-1] == 3: colors = np.dstack((colors, np.ones(z.shape)))
        if self.surface is not None: self.view.removeItem(self.surface)
        self.surface = gl.GLSurfacePlotItem(x=axis-5, y=axis-5, z=display_z, colors=colors, smooth=True, computeNormals=False)
        self.view.addItem(self.surface)
        self.color_scale.set_scale(low,high,scale_label or mode,cmap)
        for item in self.z_labels: self.view.removeItem(item)
        self.z_labels=[]
        for fraction in np.linspace(0,1,6):
            value=low+fraction*(high-low); item=gl.GLTextItem(pos=(-5.7,-5.25,float(fraction*5)),text=f"{value:.3g}",color=(225,232,238,255),font=self.axis_font); self.view.addItem(item); self.z_labels.append(item)


class InventoryDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner); self.owner = owner
        self.setWindowTitle("Assembly inventory"); self.resize(950, 560)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 8); self.table.setHorizontalHeaderLabels(
            ["Assembly", "Type", "Status", "Position", "Cycles", "Burnup", "U-235", "Pu-239"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True); self.table.cellDoubleClicked.connect(self.history)
        layout.addWidget(self.table)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(self.reject); layout.addWidget(close)
        self.refresh()

    def refresh(self):
        records = list(self.owner.model.assembly_registry.values()); self.table.setSortingEnabled(False)
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            vals = [rec.assembly_id, ASSEMBLY_TYPES[rec.assembly_type].name, rec.status, rec.position or "—",
                    str(rec.cycles_completed), f"{rec.state.get('burnup',0):.2f}",
                    f"{rec.state.get('u235_inventory',0):.4f}", f"{rec.state.get('pu239_inventory',0):.4f}"]
            for col, value in enumerate(vals): self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.setSortingEnabled(True)

    def history(self, row, _col):
        aid = self.table.item(row, 0).text(); rec = self.owner.model.assembly_registry.get(aid)
        if not rec: return
        dlg = QDialog(self); dlg.setWindowTitle(f"History — {aid}"); dlg.resize(850,420); box=QVBoxLayout(dlg)
        table=QTableWidget(len(rec.history), 7); table.setHorizontalHeaderLabels(["Event","Cycle","FPD","Position","Burnup","Flux","Power"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, entry in enumerate(rec.history):
            vals=[entry.get("event",""),entry.get("cycle_number",""),f'{entry.get("total_fpd",0):.1f}',entry.get("position") or "—",f'{entry.get("burnup",0):.2f}',f'{entry.get("flux",0):.3f}',f'{entry.get("power",0):.3f}']
            for c,v in enumerate(vals): table.setItem(r,c,QTableWidgetItem(str(v)))
        box.addWidget(table); dlg.exec()


class RackTable(QTableWidget):
    """Sortable staging table that exports its assembly token by drag."""
    def __init__(self):
        super().__init__(0,4); self.setHorizontalHeaderLabels(["Assembly / supply","Burnup","Cycles","Previous"])
        self.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in range(1,4): self.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.setSortingEnabled(True); self.setDragEnabled(True)
    def token_at(self,row):
        item=self.item(row,0); return item.data(Qt.ItemDataRole.UserRole) if item else None
    def startDrag(self,_actions):
        row=self.currentRow(); token=self.token_at(row)
        if not token: return
        mime=QMimeData(); mime.setData("application/x-core-assembly",str(token).encode("utf-8")); drag=QDrag(self); drag.setMimeData(mime); drag.exec(Qt.DropAction.MoveAction)


class RefuelingDialog(QDialog):
    """Transactional guided refueling workspace with undo/redo and validation."""
    def __init__(self, owner):
        super().__init__(None,Qt.WindowType.Window); self.owner=owner; self.original=copy.deepcopy(owner.model); self.draft=copy.deepcopy(owner.model)
        self.undo_stack=[]; self.redo_stack=[]; self.selected_token=None; self.source=None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose); self.setWindowModality(Qt.WindowModality.NonModal); self.setWindowTitle("Guided Refueling Workspace — Draft Next-Cycle Loading"); self.resize(1450,820); self.setStyleSheet(STYLE)
        root=QVBoxLayout(self); tools=QHBoxLayout()
        for text, fn in (("1  Unload core to staging",self.unload),("Undo",self.undo),("Redo",self.redo),("Validate loading",self.validate_dialog),("Preview EOC → BOC",self.preview)):
            b=QPushButton(text); b.clicked.connect(fn); tools.addWidget(b)
        self.outage=QDoubleSpinBox(); self.outage.setRange(0,3650); self.outage.setValue(owner.outage.value()); self.outage.setSuffix(" days")
        self.outage.setFixedWidth(105); outage_group=QWidget(); outage_layout=QHBoxLayout(outage_group); outage_layout.setContentsMargins(0,0,0,0); outage_layout.setSpacing(4); outage_layout.addWidget(QLabel("Outage:")); outage_layout.addWidget(self.outage); outage_group.setMaximumWidth(175)
        tools.addWidget(outage_group); cancel=QPushButton("Cancel"); cancel.clicked.connect(self.reject); tools.addWidget(cancel); commit=QPushButton("COMMIT LOADING AND BEGIN NEXT CYCLE"); commit.clicked.connect(self.commit); tools.addWidget(commit); root.addLayout(tools)
        split=QSplitter(); root.addWidget(split,1)
        left=QWidget(); lv=QVBoxLayout(left); lv.addWidget(QLabel("STAGING RACKS")); self.racks=QTabWidget(); lv.addWidget(self.racks,1)
        self.tables={}
        for key,label in (("once","Once burn"),("twice","Twice burn"),("special","Special / extended"),("new","New fuel supply"),("spent","Spent pool")):
            table=RackTable(); table.cellClicked.connect(lambda row,_col,k=key:self.select_table_row(k,row)); self.racks.addTab(table,label); self.tables[key]=table
        rack_actions=QHBoxLayout(); mark=QPushButton("Mark selected as spent"); mark.clicked.connect(self.mark_spent); clear=QPushButton("Clear selection"); clear.clicked.connect(self.clear_selection); rack_actions.addWidget(mark); rack_actions.addWidget(clear); lv.addLayout(rack_actions)
        split.addWidget(left); centre=QWidget(); cv=QVBoxLayout(centre); cv.addWidget(QLabel("DRAFT NEXT-CYCLE CORE")); self.map=CoreMap(); self.map.cellClicked.connect(self.core_click); self.map.tokenDropped.connect(self.drop_token); cv.addWidget(self.map,1); cv.addWidget(QLabel("Click a rack row then a position, or drag a row onto the core. Select two in-core assemblies to rearrange.")); split.addWidget(centre)
        right=QWidget(); rv=QVBoxLayout(right); rv.addWidget(QLabel("ASSEMBLY INSPECTOR")); self.details=QTextBrowser(); rv.addWidget(self.details); rv.addWidget(QLabel("VALIDATION / WORKFLOW")); self.summary=QTextBrowser(); rv.addWidget(self.summary,1); split.addWidget(right)
        split.setSizes([390,680,350]); self.refresh()

    def push(self): self.undo_stack.append(copy.deepcopy(self.draft)); self.undo_stack=self.undo_stack[-30:]; self.redo_stack.clear()
    def undo(self):
        if self.undo_stack: self.redo_stack.append(copy.deepcopy(self.draft)); self.draft=self.undo_stack.pop(); self.refresh()
    def redo(self):
        if self.redo_stack: self.undo_stack.append(copy.deepcopy(self.draft)); self.draft=self.redo_stack.pop(); self.refresh()
    def unload(self): self.push(); self.draft.unload_all_to_staging(); self.refresh()
    def select_token(self, token): self.selected_token=token; self.source=None; self.refresh_details()
    def select_table_row(self,category,row):
        token=self.tables[category].token_at(row)
        if token: self.select_token(str(token))

    def records(self, category):
        return sorted((r for r in self.draft.assembly_registry.values() if r.status in ("storage","spent") and self.draft.refueling_category(r.assembly_id)==category), key=lambda r:r.state.get("burnup",0))

    def refresh(self):
        for category,table in self.tables.items():
            table.setSortingEnabled(False); table.setRowCount(0)
            if category=="new":
                for key in ("FRESH","BA","TH","SEED","REFL"):
                    row=table.rowCount(); table.insertRow(row); values=(ASSEMBLY_TYPES[key].name,"0.00","0","NEW"); token=f"NEW:{key}"
                    for col,value in enumerate(values): item=QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole,token); table.setItem(row,col,item)
            else:
                for record in self.records(category):
                    previous="—"
                    for entry in reversed(record.history):
                        if entry.get("position"): previous=str(entry["position"]); break
                    row=table.rowCount(); table.insertRow(row); values=(record.assembly_id,f"{record.state.get('burnup',0):.2f}",str(record.cycles_completed),previous)
                    for col,value in enumerate(values): item=QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole,record.assembly_id); table.setItem(row,col,item)
            table.setSortingEnabled(True)
        self.map.render_model(self.draft,self.draft.burnup,"magma",True,self.source,show_ids=True,outline_empty=True)
        loaded=int(np.sum(self.draft.mask & (self.draft.assembly_ids!="")))
        self.summary.setPlainText(f"Loaded: {loaded}/{int(np.sum(self.draft.mask))}\nOnce-burned rack: {len(self.records('once'))}\nTwice-burned rack: {len(self.records('twice'))}\nSpecial rack: {len(self.records('special'))}\nSpent pool: {len(self.records('spent'))}\n\nSelect a rack card then a core position, or select two core positions to move/swap.")
        self.refresh_details()

    def refresh_details(self):
        token=self.selected_token
        if not token: self.details.setPlainText("Select an assembly card or an in-core assembly."); return
        if token.startswith("NEW:"):
            spec=ASSEMBLY_TYPES[token.split(":",1)[1]]; self.details.setPlainText(f"NEW SUPPLY\n\n{spec.name}\n{spec.notes}"); return
        rec=self.draft.assembly_registry.get(token)
        if rec: self.details.setPlainText(f"{rec.assembly_id}\n{ASSEMBLY_TYPES[rec.assembly_type].name}\nStatus: {rec.status}\nPosition: {rec.position or '—'}\nBurnup: {rec.state.get('burnup',0):.2f}\nCycles: {rec.cycles_completed}\nHistory records: {len(rec.history)}")

    def clear_selection(self):
        self.selected_token=None; self.source=None
        for table in self.tables.values(): table.clearSelection()
        self.refresh_details(); self.map.render_model(self.draft,self.draft.burnup,"magma",True,None,show_ids=True,outline_empty=True)

    def mark_spent(self):
        token=self.selected_token
        if not token or token.startswith("NEW:") or token not in self.draft.assembly_registry: return
        record=self.draft.assembly_registry[token]
        if record.status=="in_core": QMessageBox.information(self,"Mark spent","Remove the assembly from the draft core before marking it spent."); return
        self.push(); record.status="spent"; self.selected_token=None; self.source=None; self.refresh()

    def place_token(self,token,r,c):
        if not self.draft.mask[r,c]: return
        self.push()
        if token.startswith("NEW:"):
            self.draft.set_assembly(r,c,token.split(":",1)[1]); self.selected_token=token
        else:
            record=self.draft.assembly_registry.get(token)
            if record is None or record.status not in ("storage","spent"): self.undo_stack.pop(); return
            if self.draft.refueling_category(token)=="spent": self.undo_stack.pop(); QMessageBox.information(self,"Spent assembly","Spent assemblies are not eligible for reloading."); return
            self.draft.load_stored_assembly(token,r,c,recalculate=False,record_event=False); self.selected_token=None
        self.draft.record_assembly_histories("draft_placement"); self.source=None; self.refresh()

    def drop_token(self,token,r,c): self.selected_token=token; self.place_token(token,r,c)

    def core_click(self,r,c,button):
        if not self.draft.mask[r,c]: return
        if button==Qt.MouseButton.RightButton.value:
            if str(self.draft.assembly_ids[r,c]): self.push(); self.draft.discharge_assembly(r,c,recalculate=False); self.selected_token=None; self.source=None; self.refresh()
            return
        # A selected in-core source takes precedence over rack placement.  Its
        # assembly ID is shown in the details pane but is not a rack token.
        if self.source is not None:
            if self.source!=(r,c):
                self.push(); self.draft.move_or_swap_assemblies(self.source,(r,c),recalculate=False,record_event=False)
                self.draft.record_assembly_histories("draft_core_move")
            self.source=None; self.selected_token=None; self.refresh(); return
        if self.selected_token:
            self.place_token(self.selected_token,r,c); return
        aid=str(self.draft.assembly_ids[r,c])
        self.source=(r,c) if aid else None; self.selected_token=aid or None; self.refresh()

    def validate(self):
        errors=[]; warnings=[]; ids=[str(x) for x in self.draft.assembly_ids[self.draft.mask] if str(x)]
        empty=int(np.sum(self.draft.mask & (self.draft.assembly_ids=="")))
        if empty: errors.append(f"{empty} active positions are empty.")
        if len(ids)!=len(set(ids)): errors.append("Duplicate assembly IDs detected.")
        if not errors:
            self.draft.solve()
            if self.draft.k_eff<.995: warnings.append(f"Unborated k is low ({self.draft.k_eff:.4f}).")
            if self.draft.radial_peaking>2.10: warnings.append(f"Radial peaking is high ({self.draft.radial_peaking:.3f}).")
            if self.draft.shutdown_margin_pcm<=0: errors.append("Shutdown margin is not positive.")
        return errors,warnings
    def validate_dialog(self):
        e,w=self.validate(); text=("VALIDATION PASSED" if not e else "VALIDATION FAILED")+("\n\nErrors:\n• "+"\n• ".join(e) if e else "")+("\n\nWarnings:\n• "+"\n• ".join(w) if w else ""); QMessageBox.information(self,"Refueling validation",text)
    def preview(self):
        e,w=self.validate()
        if e: QMessageBox.warning(self,"Cannot preview","Correct validation errors first."); return
        proposed=copy.deepcopy(self.draft); proposed.begin_next_cycle(self.outage.value())
        QMessageBox.information(self,"Previous EOC vs proposed BOC",f"Previous EOC: k={self.original.k_eff:.4f}, peak={self.original.radial_peaking:.3f}, boron={self.original.required_boron_ppm:.0f} ppm\n\nProposed BOC: k={proposed.k_eff:.4f}, peak={proposed.radial_peaking:.3f}, boron={proposed.required_boron_ppm:.0f} ppm, shutdown margin={proposed.shutdown_margin_pcm:.0f} pcm")
    def commit(self):
        e,w=self.validate()
        if e: QMessageBox.critical(self,"Cannot commit","\n".join(e)); return
        if w and QMessageBox.question(self,"Commit with warnings?","\n".join(w))!=QMessageBox.StandardButton.Yes: return
        self.draft.begin_next_cycle(self.outage.value()); self.owner.model=self.draft; self.owner.outage.setValue(self.outage.value()); self.owner.reset_history(); self.owner.refresh(); self.accept()


class CoreLoadingWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f"{MODULE_NAME} — PyQtGraph"); self.resize(1540,920); self.setStyleSheet(STYLE)
        self.model=CoreModel(); self.selected_type="FRESH"; self.selected=(GRID_SIZE//2,GRID_SIZE//2); self.refuel_source=None; self.refueling_window=None; self.history={}; self.display_scales={}; self.running=False
        self.timer=QTimer(self); self.timer.timeout.connect(self.cycle_tick); self.build(); self.reset_history(); self.refresh()

    def group(self,title,layout): g=QGroupBox(title); g.setLayout(layout); return g
    def button(self,text,fn,layout): b=QPushButton(text); b.clicked.connect(fn); layout.addWidget(b); return b
    def spin(self,value,low,high,suffix=""):
        w=QDoubleSpinBox(); w.setRange(low,high); w.setValue(value); w.setSuffix(suffix); w.setDecimals(2); return w
    def scroll_panel(self,widget): s=QScrollArea(); s.setWidgetResizable(True); s.setWidget(widget); s.setMinimumWidth(285); return s

    def build(self):
        menu=self.menuBar(); file=menu.addMenu("File")
        for text,fn in (("Save state…",self.save_state),("Load state…",self.load_state),("Export CSV…",self.export_csv)):
            a=QAction(text,self); a.triggered.connect(fn); file.addAction(a)
        help_menu=menu.addMenu("Help"); a=QAction("About",self); a.triggered.connect(self.about); help_menu.addAction(a)
        shell=QWidget(); shell_layout=QVBoxLayout(shell); shell_layout.setContentsMargins(12,8,12,12); shell_layout.setSpacing(7); self.setCentralWidget(shell)
        banner=QWidget(); banner.setStyleSheet("background:#151a20; border-bottom:2px solid #56616d;"); banner_layout=QHBoxLayout(banner); banner_layout.setContentsMargins(14,8,14,9)
        title_block=QVBoxLayout(); title=QLabel(MODULE_NAME.upper()); title.setStyleSheet("font-size:17pt; font-weight:700; color:#f4f7fa; border:0;"); subtitle=QLabel("OPEN NUCLEAR ENGINEERING TEACHING SUITE"); subtitle.setStyleSheet("color:#aebdca; font-size:9pt; border:0;"); title_block.addWidget(title); title_block.addWidget(subtitle); banner_layout.addLayout(title_block); banner_layout.addStretch(); shell_layout.addWidget(banner)
        split=QSplitter(); shell_layout.addWidget(split,1)
        left=QWidget(); lv=QVBoxLayout(left)
        palette=QVBoxLayout(); self.palette=QComboBox()
        for index,key in enumerate(("FRESH","ONCE","TWICE","BA","TH","SEED","REFL","EMPTY")):
            self.palette.addItem(f"■  {ASSEMBLY_TYPES[key].short or '×'}  {ASSEMBLY_TYPES[key].name}",key)
            self.palette.setItemData(index,QColor(ASSEMBLY_TYPES[key].color),Qt.ItemDataRole.ForegroundRole)
        self.palette.currentIndexChanged.connect(lambda:self.select_type(self.palette.currentData())); palette.addWidget(self.palette); self.description=QLabel(); self.description.setWordWrap(True); palette.addWidget(self.description); lv.addWidget(self.group("ASSEMBLY PALETTE",palette))
        presets=QVBoxLayout()
        self.button("Conventional 3-batch PWR",lambda:self.preset("pwr"),presets); self.button("Thorium seed-blanket",lambda:self.preset("seed"),presets); self.button("Thorium checkerboard",lambda:self.preset("checker"),presets); self.button("Clear active core",lambda:self.preset("clear"),presets); lv.addWidget(self.group("LOADING PRESETS",presets))
        controls=QFormLayout(); self.control=self.spin(0,0,100," %"); controls.addRow("Bank insertion",self.control); row=QHBoxLayout(); self.button("Apply",self.apply_control,row); self.button("Withdraw",lambda:(self.control.setValue(0),self.apply_control()),row); controls.addRow(row); lv.addWidget(self.group("CONTROL BANKS",controls))
        fuel=QVBoxLayout(); self.button("OPEN GUIDED REFUELING WORKSPACE",self.open_refueling_workspace,fuel)
        self.refuel_mode=QCheckBox("Refueling move/swap mode"); self.refuel_mode.toggled.connect(self.toggle_refueling); fuel.addWidget(self.refuel_mode)
        fuel.addWidget(QLabel("Outage duration before next cycle:")); self.outage=self.spin(30,0,3650," days"); fuel.addWidget(self.outage); self.button("Begin next cycle",self.begin_cycle,fuel)
        self.button("Discharge selected to storage",self.discharge_selected,fuel); fuel.addWidget(QLabel("Stored assembly:")); self.pool=QComboBox(); fuel.addWidget(self.pool); self.button("Load stored assembly at selected position",self.load_stored,fuel); self.button("Open assembly inventory",lambda:InventoryDialog(self).exec(),fuel)
        state_row=QHBoxLayout(); self.button("Save refueling state",self.save_state,state_row); self.button("Load state",self.load_state,state_row); fuel.addLayout(state_row); lv.addWidget(self.group("REFUELING AND ASSEMBLY TRACKING",fuel))
        cycle=QFormLayout(); self.step_days=self.spin(30,.01,1000," FPD"); self.delay=self.spin(.8,.05,30," s"); self.stop_at=self.spin(1000,0,100000," FPD"); self.stop_warning=QCheckBox("Stop on k/peaking warning"); self.stop_warning.setChecked(True); cycle.addRow("Step",self.step_days); cycle.addRow("Delay",self.delay); cycle.addRow("Stop at",self.stop_at); cycle.addRow(self.stop_warning); cr=QHBoxLayout(); self.button("Run",self.run_cycle,cr); self.button("Pause",self.pause,cr); cycle.addRow(cr); self.button("Single step",self.advance,cycle); self.button("Reset depletion",self.reset_depletion,cycle); lv.addWidget(self.group("CYCLE EVOLUTION",cycle)); lv.addStretch(); split.addWidget(self.scroll_panel(left))
        centre=QWidget(); cv=QVBoxLayout(centre); bar=QHBoxLayout(); bar.addWidget(QLabel("CORE LOADING MAP")); bar.addStretch(); self.show_values=QCheckBox("Show values"); self.show_values.setChecked(True); self.show_values.toggled.connect(lambda _:self.refresh_map()); bar.addWidget(self.show_values); cv.addLayout(bar); self.map=CoreMap(); self.map.cellClicked.connect(self.core_click); self.map.cellHovered.connect(self.show_hover); self.map.hoverCleared.connect(self.clear_hover); cv.addWidget(self.map,1); self.hover=QLabel("Left-click places; middle-click selects; right-click clears."); cv.addWidget(self.hover); split.addWidget(centre)
        right=QWidget(); rv=QVBoxLayout(right); metric_bar=QHBoxLayout(); metric_bar.addWidget(QLabel("METRIC:")); self.metric_box=QComboBox(); self.metric_box.addItems(METRICS); self.metric_box.currentTextChanged.connect(lambda _:(self.refresh_plots(),self.refresh_map())); metric_bar.addWidget(self.metric_box,1); self.lock_scale=QCheckBox("Lock scale to BOC"); self.lock_scale.setChecked(True); self.lock_scale.toggled.connect(lambda _:self.refresh_plots()); metric_bar.addWidget(self.lock_scale); rv.addLayout(metric_bar)
        self.tabs=QTabWidget(); self.heat=pg.PlotWidget(); self.heat.setAspectLocked(True); self.heat.invertY(True); self.heat_image=pg.ImageItem(axisOrder="row-major"); self.heat.addItem(self.heat_image); self.surface=SurfaceView(); self.trends=pg.GraphicsLayoutWidget(); self.tabs.addTab(self.heat,"Result heatmap"); self.tabs.addTab(self.surface,"Interpolated 3-D surface"); self.tabs.addTab(self.trends,"Cycle trends"); self.tabs.currentChanged.connect(lambda _:self.refresh_plots()); rv.addWidget(self.tabs,1)
        self.values={}; grid=QGridLayout(); labels=[("k","Uncontrolled k-effective"),("operating_k","Controlled operating k"),("boron","Required soluble boron"),("peak","Radial power peak"),("leak","Leakage index"),("conv","Thorium conversion ratio"),("ce","Centre-to-edge flux ratio"),("ns","North-south flux tilt"),("ew","East-west flux tilt"),("centroid","Flux centroid offset"),("fuel_temp","Peak fuel temperature"),("moderator_temp","Peak moderator temperature"),("density","Minimum moderator density"),("xenon","Average Xe-135 index"),("samarium","Average Sm-149 index"),("control","Control-bank insertion"),("control_worth","Inserted control worth"),("shutdown_k","All-banks-in k"),("shutdown_margin","Shutdown margin"),("avg_burn","Average fuel burnup"),("burn_spread","Fuel burnup spread"),("cycle_number","Current fuel cycle"),("selected_position","Selected core position"),("selected_id","Selected assembly ID"),("storage_count","Assemblies in storage"),("days","Cycle exposure"),("count","Loaded assemblies")]
        for i,(key,label) in enumerate(labels): grid.addWidget(QLabel(label),i,0); value=QLabel("—"); value.setObjectName("value"); grid.addWidget(value,i,1); self.values[key]=value
        indicator_content=QWidget(); indicator_content.setLayout(grid); indicator_scroll=QScrollArea(); indicator_scroll.setWidgetResizable(True); indicator_scroll.setWidget(indicator_content); indicator_scroll.setMinimumHeight(130)
        indicator_box=QVBoxLayout(); indicator_box.addWidget(indicator_scroll); indicator_group=self.group("CORE INDICATORS",indicator_box); indicator_group.setMaximumHeight(230); rv.addWidget(indicator_group,0); self.status=QLabel(); self.status.setWordWrap(True); self.status.setMaximumHeight(42); rv.addWidget(self.status,0); split.addWidget(right); split.setSizes([310,610,620]); self.select_type("FRESH"); self.refresh_pool()

    def select_type(self,key): self.selected_type=key; s=ASSEMBLY_TYPES[key]; self.description.setText(f"{s.notes}\n\nFissile strength: {s.fissile:.2f}\nThorium loading: {s.fertile_th:.2f}\nInitial burnup: {s.initial_burnup:.1f} GWd/tHM")
    def open_refueling_workspace(self):
        if self.refueling_window is not None and self.refueling_window.isVisible(): self.refueling_window.raise_(); self.refueling_window.activateWindow(); return
        window=RefuelingDialog(self); self.refueling_window=window; window.destroyed.connect(lambda _=None:setattr(self,"refueling_window",None)); window.show(); window.raise_(); window.activateWindow()
    def field(self):
        attr,label,cmap=METRICS[self.metric_box.currentText()]
        if attr=="_power_previous": reference=self.history["power"][-2] if len(self.history.get("power",[]))>=2 else self.model.power
        elif attr=="_power_boc": reference=self.history["power"][0] if self.history.get("power") else self.model.power
        else: return getattr(self.model,attr),label,cmap
        return self.model.power-reference,label,cmap
    def show_hover(self,r,c):
        if not self.model.mask[r,c]: self.hover.setText(f"R{r+1:02d}–C{c+1:02d} | outside the active-core mask"); return
        key=str(self.model.layout[r,c]); aid=str(self.model.assembly_ids[r,c]) or "EMPTY"; spec=ASSEMBLY_TYPES[key]
        self.hover.setText(f"{self.model.position_id(r,c)} | {aid} | {spec.name} | burnup {self.model.burnup[r,c]:.1f} GWd/tHM | flux {self.model.flux[r,c]:.3f} | power {self.model.power[r,c]:.3f}")
    def clear_hover(self): self.hover.setText("Left-click places; middle-click selects; right-click clears.")
    def core_click(self,r,c,button):
        if not self.model.mask[r,c]: return
        self.pause(); self.selected=(r,c)
        if self.refuel_mode.isChecked():
            if button==Qt.MouseButton.RightButton.value:
                self.model.discharge_assembly(r,c); self.refuel_source=None; self.refresh_pool(); self.reset_history(); self.refresh(); return
            if self.refuel_source is None:
                self.refuel_source=(r,c) if str(self.model.assembly_ids[r,c]) else None; self.refresh_map(); return
            if self.refuel_source!=(r,c): self.model.move_or_swap_assemblies(self.refuel_source,(r,c))
            self.refuel_source=None; self.refresh_pool(); self.reset_history(); self.refresh(); return
        if button==Qt.MouseButton.RightButton.value: self.model.set_assembly(r,c,"EMPTY")
        elif button==Qt.MouseButton.MiddleButton.value: self.refresh(); return
        else: self.model.set_assembly(r,c,self.selected_type)
        self.model.solve(); self.model.record_assembly_histories("loading_changed"); self.reset_history(); self.refresh()
    def preset(self,kind):
        self.pause(); {"pwr":self.model.load_conventional_pwr,"seed":self.model.load_thorium_seed_blanket,"checker":self.model.load_thorium_checkerboard,"clear":self.model.clear_core}[kind](); self.control.setValue(0); self.reset_history(); self.refresh()
    def apply_control(self): self.model.set_control_insertion(self.control.value()); self.model.solve(); self.record_history(); self.refresh()
    def toggle_refueling(self,enabled): self.refuel_source=None; self.hover.setText("Select an assembly, then its destination; right-click discharges." if enabled else "Left-click places; middle-click selects; right-click clears."); self.refresh_map()
    def refresh_pool(self):
        current=self.pool.currentData() if self.pool.count() else None; self.pool.clear()
        for aid in self.model.storage_ids():
            rec=self.model.assembly_registry[aid]; self.pool.addItem(f"{aid} | {rec.state.get('burnup',0):.2f} GWd/tHM",aid)
        if current:
            index=self.pool.findData(current)
            if index>=0: self.pool.setCurrentIndex(index)
    def discharge_selected(self):
        r,c=self.selected
        if not str(self.model.assembly_ids[r,c]): QMessageBox.information(self,"Discharge assembly","The selected position is empty."); return
        self.pause(); self.model.discharge_assembly(r,c); self.refuel_source=None; self.refresh_pool(); self.reset_history(); self.refresh()
    def load_stored(self):
        aid=self.pool.currentData()
        if not aid: QMessageBox.information(self,"Load stored assembly","No stored assembly is available."); return
        try: self.pause(); self.model.load_stored_assembly(aid,*self.selected); self.refresh_pool(); self.reset_history(); self.refresh()
        except Exception as exc: QMessageBox.critical(self,"Load failed",str(exc))
    def begin_cycle(self): self.model.begin_next_cycle(self.outage.value()); self.control.setValue(100*float(np.max(self.model.control_fraction))); self.refresh_pool(); self.reset_history(); self.refresh()
    def advance(self): self.pause(); self.do_step()
    def do_step(self):
        try: self.model.advance_cycle(self.step_days.value()); self.record_history(); self.refresh()
        except Exception as exc: self.pause(); QMessageBox.critical(self,"Cycle calculation failed",str(exc))
    def run_cycle(self): self.running=True; self.timer.start(max(20,int(self.delay.value()*1000)))
    def pause(self): self.running=False; self.timer.stop()
    def cycle_tick(self):
        self.do_step()
        if self.model.cycle_days>=self.stop_at.value() or (self.stop_warning.isChecked() and (self.model.k_eff<.995 or self.model.radial_peaking>2.1)): self.pause()
    def reset_depletion(self): self.pause(); self.model.reset_depletion(); self.reset_history(); self.refresh()
    def reset_history(self):
        self.history={k:[] for k in ("days","k","operating","peak","boron","burn","conversion","leakage","power","flux","burnup","u235","pu239","pa233","u233","xenon","samarium")}; self.record_history(); active=self.model.mask&(self.model.layout!="EMPTY"); self.display_scales={}
        for mode,(attribute,_label,_cmap) in METRICS.items():
            if mode.startswith("Power change:"): continue
            field=getattr(self.model,attribute); upper=float(np.max(field[active])) if np.any(active) else 1.; self.display_scales[mode]=(0.,max(upper,1e-9))
        power_extent=max(float(np.max(self.model.power[active])) if np.any(active) else 1.,1e-6)
        self.display_scales["Power change: previous"]=(-power_extent,power_extent); self.display_scales["Power change: BOC"]=(-power_extent,power_extent)
    def record_history(self):
        # A control or recalculation at the same exposure updates the current
        # state; it is not a new point in time. Replacing that sample prevents
        # artificial vertical lines at zero or any other unchanged FPD.
        if self.history.get("days") and math.isclose(float(self.history["days"][-1]),float(self.model.cycle_days),abs_tol=1e-12):
            for series in self.history.values(): series.pop()
        fuel=self.model.mask&(self.model.layout!="EMPTY")&(self.model.layout!="REFL"); self.history["days"].append(self.model.cycle_days); self.history["k"].append(self.model.k_eff); self.history["operating"].append(self.model.operating_k_eff); self.history["peak"].append(self.model.radial_peaking); self.history["boron"].append(self.model.required_boron_ppm); self.history["burn"].append(float(np.mean(self.model.burnup[fuel])) if np.any(fuel) else 0); self.history["conversion"].append(self.model.conversion_ratio); self.history["leakage"].append(self.model.leakage_index)
        for key,attr in (("power","power"),("flux","flux"),("burnup","burnup"),("u235","u235_inventory"),("pu239","pu239_inventory"),("pa233","pa233_inventory"),("u233","u233_inventory"),("xenon","xenon135_inventory"),("samarium","samarium149_inventory")): self.history[key].append(getattr(self.model,attr).copy())
    def refresh_map(self): f,_,c=self.field(); selected=self.refuel_source if self.refuel_source is not None else self.selected; self.map.render_model(self.model,f,c,self.show_values.isChecked(),selected)
    def _trend_plot(self,row,col,title,left_label,bottom_label="Full-power days"):
        plot=self.trends.addPlot(row=row,col=col,title=title); plot.setLabel("left",left_label); plot.setLabel("bottom",bottom_label); plot.showGrid(x=True,y=True,alpha=.28); plot.addLegend(offset=(4,4)); return plot
    def _right_axis(self,plot,label,color):
        plot.showAxis("right"); axis=plot.getAxis("right"); axis.setLabel(label,color=color); axis.setPen(pg.mkPen(color)); axis.setTextPen(pg.mkPen(color))
        view=pg.ViewBox(); plot.scene().addItem(view); axis.linkToView(view); view.setXLink(plot); view.setGeometry(plot.vb.sceneBoundingRect()); view.linkedViewChanged(plot.vb,view.XAxis)
        plot.vb.sigResized.connect(lambda _emitted=None,v=view,p=plot: v.setGeometry(p.vb.sceneBoundingRect())); self.trend_secondary.append(view); return view
    def refresh_plots(self):
        f,label,cmap=self.field(); mode=self.metric_box.currentText(); masked=np.asarray(f,float).copy(); masked[~self.model.mask|(self.model.layout=="EMPTY")]=np.nan; finite=masked[np.isfinite(masked)]
        if mode.startswith("Power change:"):
            extent=max(float(np.max(np.abs(finite))) if finite.size else 0.,1e-6); live_levels=(-extent,extent); levels=self.display_scales.get(mode,live_levels) if self.lock_scale.isChecked() else live_levels
        else:
            live_levels=(float(np.min(finite)),float(np.max(finite))) if finite.size else (0,1); levels=self.display_scales.get(mode,live_levels) if self.lock_scale.isChecked() else live_levels
        self.heat_image.setImage(masked,autoLevels=False,levels=levels); self.heat_image.setColorMap(pg.colormap.get(cmap,source="matplotlib")); self.heat.setTitle(label); self.surface.update_surface(self.model,f,mode,cmap,label,levels)
        # GraphicsLayout.clear() owns its PlotItems but not the secondary
        # ViewBoxes attached directly to the scene for right-hand axes.
        for view in getattr(self,"trend_secondary",[]):
            scene=view.scene()
            if scene is not None: scene.removeItem(view)
        self.trends.clear(); self.trend_secondary=[]; days=np.asarray(self.history["days"],float)
        p1=self._trend_plot(0,0,"Core cycle history","Relative indicator"); p1.plot(days,self.history["k"],pen=pg.mkPen("#7ee7ff",width=2),name="uncontrolled k"); p1.plot(days,self.history["operating"],pen=pg.mkPen("#ffffff",width=2,style=Qt.PenStyle.DashLine),name="operating k"); p1.plot(days,self.history["peak"],pen=pg.mkPen("#ff9f55",width=2),name="power peak"); p1.plot(days,self.history["conversion"],pen=pg.mkPen("#77dd88",width=2),name="conversion")
        p2=self._trend_plot(0,1,"Exposure indicators","Burnup / leakage"); p2.plot(days,self.history["burn"],pen=pg.mkPen("#e5c95c",width=2),name="average burnup"); p2.plot(days,self.history["leakage"],pen=pg.mkPen("#9fb7c8",width=1.5,style=Qt.PenStyle.DashLine),name="leakage"); boron_view=self._right_axis(p2,"Illustrative boron (ppm)","#c58cff"); boron_curve=pg.PlotCurveItem(days,self.history["boron"],pen=pg.mkPen("#c58cff",width=2)); boron_view.addItem(boron_curve); p2.legend.addItem(boron_curve,"required boron")
        r,c=self.selected; assembly_id=str(self.model.assembly_ids[r,c]) or "Empty"; p3=self._trend_plot(1,0,f"{assembly_id} at {self.model.position_id(r,c)}","Relative flux / power"); p3.plot(days,[x[r,c] for x in self.history["flux"]],pen=pg.mkPen("#58b7ff",width=2),name="flux"); p3.plot(days,[x[r,c] for x in self.history["power"]],pen=pg.mkPen("#ff665f",width=2),name="power")
        p4=self._trend_plot(1,1,"Selected assembly depletion","Burnup (GWd/tHM)"); p4.getAxis("left").setPen(pg.mkPen("#e5c95c")); p4.getAxis("left").setTextPen(pg.mkPen("#e5c95c")); p4.plot(days,[x[r,c] for x in self.history["burnup"]],pen=pg.mkPen("#e5c95c",width=2),name="burnup"); inventory_view=self._right_axis(p4,"Inventory index","#9fe7b0")
        for key,name,color,style in (("pa233","Pa-233","#c58cff",Qt.PenStyle.DashLine),("u233","U-233","#77dd88",Qt.PenStyle.DotLine),("u235","U-235","#58b7ff",Qt.PenStyle.DashDotLine),("pu239","Pu-239","#ff9f55",Qt.PenStyle.DashLine),("xenon","Xe-135","#f06cff",Qt.PenStyle.DotLine),("samarium","Sm-149","#b8b8b8",Qt.PenStyle.DashDotLine)):
            curve=pg.PlotCurveItem(days,[x[r,c] for x in self.history[key]],pen=pg.mkPen(color,width=1.8,style=style)); inventory_view.addItem(curve); p4.legend.addItem(curve,name)
    def refresh_metrics(self):
        m=self.model; fuel=m.mask&(m.layout!="EMPTY")&(m.layout!="REFL"); active=m.mask&(m.layout!="EMPTY"); r,c=self.selected
        counts=m.assembly_counts(); loaded=sum(value for key,value in counts.items() if key!="EMPTY"); avg_burn=float(np.mean(m.burnup[fuel])) if np.any(fuel) else 0; burn_spread=float(np.std(m.burnup[fuel])) if np.any(fuel) else 0
        vals={"k":f"{m.k_eff:.4f}","operating_k":f"{m.operating_k_eff:.4f}","boron":f"{m.required_boron_ppm:.0f} ppm","peak":f"{m.radial_peaking:.3f}","leak":f"{m.leakage_index:.3f}","conv":f"{m.conversion_ratio:.3f}","ce":f"{m.centre_edge_ratio:.3f}","ns":f"{m.north_south_tilt:+.3f}","ew":f"{m.east_west_tilt:+.3f}","centroid":f"{m.flux_centroid_offset:.3f} cells","fuel_temp":f"{float(np.max(m.fuel_temperature[fuel])) if np.any(fuel) else 0:.0f} K","moderator_temp":f"{float(np.max(m.moderator_temperature[active])) if np.any(active) else 0:.0f} K","density":f"{float(np.min(m.moderator_density[active])) if np.any(active) else 0:.3f}","xenon":f"{float(np.mean(m.xenon135_inventory[fuel])) if np.any(fuel) else 0:.3f}","samarium":f"{float(np.mean(m.samarium149_inventory[fuel])) if np.any(fuel) else 0:.3f}","control":f"{100*float(np.max(m.control_fraction)):.1f}%","control_worth":f"{m.control_worth_pcm:.0f} pcm","shutdown_k":f"{m.shutdown_k_eff:.4f}","shutdown_margin":f"{m.shutdown_margin_pcm:.0f} pcm","avg_burn":f"{avg_burn:.2f} GWd/tHM","burn_spread":f"{burn_spread:.2f} GWd/tHM","cycle_number":str(m.cycle_number),"selected_position":m.position_id(r,c),"selected_id":str(m.assembly_ids[r,c]) or "EMPTY","storage_count":str(len(m.storage_ids())),"days":f"{m.cycle_days:.1f} d","count":str(loaded)}
        for k,v in vals.items(): self.values[k].setText(v)
        notes=[]; notes.append("Uncontrolled k is below the illustrative end-of-cycle range." if m.k_eff<.995 else f"Illustrative boron control requires {m.required_boron_ppm:.0f} ppm." if m.k_eff>=1 else "Uncontrolled k is approaching end of cycle."); notes.append("Power peaking is high." if m.radial_peaking>2.1 else "Radial power peaking is moderate."); self.status.setText(" ".join(notes))
    def refresh(self): self.refresh_map(); self.refresh_plots(); self.refresh_metrics()
    def save_state(self):
        path,_=QFileDialog.getSaveFileName(self,"Save refueling state","core_state.json","JSON (*.json)");
        if path: self.model.save_state(path)
    def load_state(self):
        path,_=QFileDialog.getOpenFileName(self,"Load refueling state","","JSON (*.json)")
        if path:
            try: self.pause(); self.model.load_state(path); self.control.setValue(100*float(np.max(self.model.control_fraction))); self.refresh_pool(); self.reset_history(); self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Load failed",str(exc))
    def export_csv(self):
        path,_=QFileDialog.getSaveFileName(self,"Export current core","core_loading.csv","CSV (*.csv)")
        if path: QMessageBox.information(self,"Export complete",f"Exported {self.model.export_csv(path)} active positions.")
    def about(self):
        QMessageBox.information(self,"About",f"{MODULE_NAME}\n\nAn interactive teaching application for exploring assembly loading, two-group diffusion, fuel depletion, control banks, and multi-cycle refueling.\n\nThis reduced-order classroom model is not a reactor-design, licensing, safety-analysis, depletion, or criticality-safety code.")


def main():
    pg.setConfigOptions(antialias=True, imageAxisOrder="row-major")
    app=QApplication.instance() or QApplication(sys.argv); app.setApplicationName(MODULE_NAME)
    window=CoreLoadingWindow(); window.show(); return app.exec()


if __name__ == "__main__": raise SystemExit(main())
