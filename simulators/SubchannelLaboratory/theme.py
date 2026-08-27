"""Shared dark engineering-console theme for the Subchannel Laboratory."""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets


SUITE_STYLESHEET = """
QWidget {
    background-color: #0b1117;
    color: #f2f6fa;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: #0b1117;
}
QLabel#suiteTitle {
    color: #ffffff;
    font-size: 17pt;
    font-weight: 700;
    padding: 2px 0;
}
QLabel#suiteSubtitle {
    color: #c8d3dc;
    font-size: 10pt;
    padding-bottom: 6px;
}
QLabel#sectionTitle {
    color: #55c7ff;
    font-size: 10pt;
    font-weight: 700;
    padding: 8px 0 3px 0;
    border-bottom: 1px solid #435461;
}
QLabel#statusPanel {
    background-color: #101820;
    border: 1px solid #435461;
    border-radius: 4px;
    padding: 8px;
}
QPushButton {
    background-color: #205b7d;
    color: #ffffff;
    border: 1px solid #3c86ae;
    border-radius: 4px;
    min-height: 27px;
    padding: 4px 12px;
}
QPushButton:hover { background-color: #2b7299; border-color: #62c7ff; }
QPushButton:pressed { background-color: #17445f; }
QPushButton:disabled { background-color: #242d34; color: #70808b; border-color: #394650; }
QPushButton#primaryAction {
    background-color: #277cad;
    border-color: #62c7ff;
    font-weight: 700;
    min-height: 32px;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #17232d;
    color: #ffffff;
    border: 1px solid #526675;
    border-radius: 3px;
    min-height: 25px;
    padding: 2px 6px;
    selection-background-color: #277cad;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #55c7ff; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background-color: #121920;
    color: #697984;
}
QComboBox QAbstractItemView {
    background-color: #17232d;
    color: #ffffff;
    border: 1px solid #526675;
    selection-background-color: #277cad;
}
QTableWidget, QTableView {
    background-color: #0d151c;
    alternate-background-color: #15232d;
    color: #f2f6fa;
    gridline-color: #435461;
    border: 1px solid #435461;
    selection-background-color: #205b7d;
    selection-color: #ffffff;
}
QTableWidget::item, QTableView::item {
    color: #f2f6fa;
    padding: 3px;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #205b7d;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #111c25;
    color: #ffffff;
    border: 0;
    border-right: 1px solid #435461;
    border-bottom: 1px solid #435461;
    padding: 5px;
}
QTableCornerButton::section {
    background-color: #111c25;
    border: 1px solid #435461;
}
QRadioButton { spacing: 7px; padding: 3px; }
QRadioButton::indicator { width: 15px; height: 15px; }
QRadioButton::indicator:unchecked {
    border: 1px solid #6b7e8c; border-radius: 8px; background: #101820;
}
QRadioButton::indicator:checked {
    border: 4px solid #55c7ff; border-radius: 8px; background: #ffffff;
}
QScrollBar:vertical { background: #101820; width: 14px; margin: 0; }
QScrollBar::handle:vertical { background: #526675; min-height: 28px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #55c7ff; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background-color: #3d4d59; width: 2px; height: 2px; }
QGroupBox {
    border: 1px solid #435461;
    border-radius: 5px;
    margin-top: 11px;
    padding-top: 8px;
    font-weight: 700;
    color: #55c7ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    background-color: #0b1117;
}
QTabWidget::pane { border: 1px solid #435461; background: #0f171e; }
QTabBar::tab {
    background: #17232d;
    color: #dce7ee;
    border: 1px solid #435461;
    padding: 7px 12px;
}
QTabBar::tab:selected { background: #205b7d; color: #ffffff; }
QTabBar::tab:hover { background: #29485b; }
QDockWidget { color: #55c7ff; font-weight: 700; }
QDockWidget::title {
    background-color: #111a22;
    border: 1px solid #435461;
    padding: 7px;
    text-align: left;
}
QToolTip {
    background-color: #17232d;
    color: #ffffff;
    border: 1px solid #55c7ff;
    padding: 5px;
}
"""


def apply_suite_theme(application: QtWidgets.QApplication) -> None:
    application.setStyle("Fusion")
    application.setFont(QtGui.QFont("Segoe UI", 10))
    application.setStyleSheet(SUITE_STYLESHEET)
