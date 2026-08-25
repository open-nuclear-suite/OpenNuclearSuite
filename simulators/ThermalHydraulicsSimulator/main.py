"""Launcher for the Thermal-Hydraulics Teaching Simulator."""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    frontends = parser.add_mutually_exclusive_group()
    frontends.add_argument("--dearpygui", action="store_true", help="launch the former Dear PyGui interface")
    frontends.add_argument("--legacy-tk", action="store_true", help="launch the legacy Tkinter interface")
    parser.add_argument("--model-dir", type=Path, help="directory containing the canonical thermal-hydraulics model")
    args = parser.parse_args()
    if args.legacy_tk:
        from thermal_hydraulics_simulator import main as launch
    elif args.dearpygui:
        from thermal_hydraulics_dearpygui import main as launch
    else:
        from thermal_hydraulics_pyqtgraph import main as launch
    # Front-end entry points own their argument parsing. Forward only the
    # shared model location after consuming this launcher's UI selector.
    sys.argv = [sys.argv[0]] + (["--model-dir", str(args.model_dir)] if args.model_dir else [])
    launch()


if __name__ == "__main__":
    main()
