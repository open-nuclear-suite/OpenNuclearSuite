"""Launcher for the Core Loading Simulator front ends."""

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-tk", action="store_true", help="launch the former Tkinter interface")
    args = parser.parse_args()
    if args.legacy_tk:
        from core_loading_thorium_poc_fixed import main as launch
    else:
        from core_loading_pyqtgraph import main as launch
    return launch() or 0


if __name__ == "__main__":
    raise SystemExit(main())
