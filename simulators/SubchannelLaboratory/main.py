"""Launcher for the progressive subchannel laboratory."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from simulators.SubchannelLaboratory.gui import SubchannelLaboratoryWindow
from simulators.SubchannelLaboratory.pyqtgraph_handler import ensure_qt_application
from simulators.SubchannelLaboratory.theme import apply_suite_theme
from simulators.SubchannelLaboratory.branding import create_startup_splash


def main() -> int:
    app = ensure_qt_application()
    apply_suite_theme(app)
    splash = create_startup_splash()
    splash.show()
    app.processEvents()
    elapsed = QtCore.QElapsedTimer()
    elapsed.start()
    window = SubchannelLaboratoryWindow()
    while elapsed.elapsed() < 1000:
        app.processEvents()
        QtCore.QThread.msleep(10)
    window.show()
    splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
