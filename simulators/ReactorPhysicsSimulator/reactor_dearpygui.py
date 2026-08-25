"""Canonical Dear PyGui handler for the Reactor Physics and Kinetics Simulator."""

import argparse
from pathlib import Path

from reactor_dearpygui_prototype import DEFAULT_MODEL_DIR, ReactorDPG, load_backend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    args = parser.parse_args()
    backend_cls, canonical = load_backend(args.model_dir)
    ReactorDPG(backend_cls, canonical).run()


if __name__ == "__main__":
    main()
