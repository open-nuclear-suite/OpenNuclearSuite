"""Canonical Dear PyGui handler for the Thermal-Hydraulics Simulator."""

import argparse
from pathlib import Path

from thermal_hydraulics_dearpygui_ui import DEFAULT_MODEL_DIR, ThermalHydraulicsDPG


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    args = parser.parse_args()
    ThermalHydraulicsDPG(args.model_dir).run()


if __name__ == "__main__": main()
