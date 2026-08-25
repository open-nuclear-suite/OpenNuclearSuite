"""Launcher for the responsive Reactor Physics and Kinetics Simulator."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-tk", action="store_true", help="launch the former Tkinter interface")
    parser.add_argument("--dearpygui", action="store_true", help="launch the Dear PyGui interface")
    parser.add_argument("--model-dir", type=Path, help="directory containing the canonical reactor model")
    args = parser.parse_args()
    if args.legacy_tk:
        from reactor_teaching_simulator import main as launch
        launch()
    elif args.dearpygui:
        from reactor_dearpygui_prototype import ReactorDPG, load_backend
        backend_cls, canonical = load_backend(args.model_dir or Path(__file__).resolve().parent)
        ReactorDPG(backend_cls, canonical).run()
    else:
        from reactor_pyqtgraph import main as launch
        launch(args.model_dir or Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
