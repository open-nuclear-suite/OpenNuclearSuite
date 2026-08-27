"""Release branding, About dialog, and startup splash for the laboratory."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


SUITE_NAME = "Open Nuclear Engineering Teaching Suite"
SUITE_VERSION = "2.1.0"
APPLICATION_NAME = "Subchannel Thermal-Hydraulics Laboratory"


def show_about_dialog(parent: QtWidgets.QWidget) -> None:
    dialog = QtWidgets.QMessageBox(parent)
    dialog.setWindowTitle(f"About — {APPLICATION_NAME}")
    dialog.setIcon(QtWidgets.QMessageBox.Information)
    dialog.setText(
        f"<h2>{APPLICATION_NAME}</h2>"
        f"<p><b>{SUITE_NAME} · Version {SUITE_VERSION}</b></p>"
        "<p>An interactive teaching application for steady single-channel thermal-"
        "hydraulics, boiling, void and pressure-drop models, CHF correlation comparison, "
        "axial power distributions, and hot-channel uncertainty demonstrations.</p>"
    )
    dialog.setInformativeText(
        "Teaching software only. The models are simplified and are not suitable for "
        "reactor design, licensing, safety analysis, operator training, accident "
        "prediction, or real plant operation.\n\n"
        "PySide6 and PyQtGraph interface · Open-source teaching suite"
    )
    dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
    dialog.exec()


def create_startup_splash() -> QtWidgets.QSplashScreen:
    """Create a scalable code-drawn splash with no external asset dependency."""
    pixmap = QtGui.QPixmap(760, 360)
    pixmap.fill(QtGui.QColor("#0b1117"))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)

    painter.fillRect(0, 0, 9, 360, QtGui.QColor("#55c7ff"))
    painter.setPen(QtGui.QPen(QtGui.QColor("#55c7ff"), 2))
    painter.drawLine(42, 255, 718, 255)

    title_font = QtGui.QFont("Segoe UI", 25, QtGui.QFont.Bold)
    painter.setFont(title_font)
    painter.setPen(QtGui.QColor("#ffffff"))
    painter.drawText(QtCore.QRect(48, 62, 664, 92), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                     "SUBCHANNEL THERMAL-HYDRAULICS\nLABORATORY")

    subtitle_font = QtGui.QFont("Segoe UI", 12)
    painter.setFont(subtitle_font)
    painter.setPen(QtGui.QColor("#c8d3dc"))
    painter.drawText(50, 190, "Progressive single-channel and hot-channel teaching environment")
    painter.setPen(QtGui.QColor("#55c7ff"))
    painter.drawText(50, 293, f"{SUITE_NAME.upper()}  ·  VERSION {SUITE_VERSION}")
    painter.setPen(QtGui.QColor("#93a4b0"))
    painter.drawText(50, 326, "Loading properties, correlations, plots, and geometry inspection…")
    painter.end()

    splash = QtWidgets.QSplashScreen(pixmap, QtCore.Qt.WindowStaysOnTopHint)
    splash.setWindowFlag(QtCore.Qt.FramelessWindowHint, True)
    return splash
