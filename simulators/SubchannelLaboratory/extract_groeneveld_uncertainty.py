"""Extract the Appendix C cell shading into a coordinate-aligned CSV mask.

The NUREG Appendix C pages are scanned, rotated tables. This utility detects
their grid lines, samples text-free cell corners, clusters the four printed
background tones, and verifies that the resulting rows align with the complete
24 x 21 x 23 CHF cube. It is a build-time provenance tool, not a runtime OCR
dependency.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image

from .groeneveld_lut import MASS_FLUX, PRESSURE_MPA, QUALITY


CLASS_LABELS = (
    "direct_data",
    "calculated_extrapolation",
    "avoid_extrapolation",
    "low_quality_region",
)


def _groups(indices: np.ndarray) -> list[np.ndarray]:
    if indices.size == 0:
        return []
    return [group for group in np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
            if group.size]


def _line_centres(projection: np.ndarray, threshold: float) -> list[int]:
    return [int(round(float(group.mean()))) for group in _groups(np.where(projection > threshold)[0])]


def _quality_grid_lines(gray: np.ndarray) -> list[int]:
    candidates = _line_centres((gray < 80).sum(axis=0), gray.shape[0] * 0.32)
    needed = QUALITY.size + 1
    # Dark shaded cells can create additional long vertical projections. Walk
    # through those false candidates while retaining the regular ~63 px grid.
    for first in range(len(candidates)):
        run = [candidates[first]]
        for candidate in candidates[first + 1:]:
            gap = candidate - run[-1]
            if 45 <= gap <= 80:
                run.append(candidate)
            if len(run) == needed:
                break
        if len(run) == needed:
            return run
    raise RuntimeError(f"could not identify {needed} quality-grid lines: {candidates}")


def _row_grid_lines(gray: np.ndarray) -> list[int]:
    candidates = _line_centres((gray < 80).sum(axis=1), gray.shape[1] * 0.48)
    if len(candidates) < 4:
        raise RuntimeError(f"could not identify row grid: {candidates}")
    return candidates


def _corner_background(gray: np.ndarray, y0: int, y1: int, x0: int, x1: int) -> float:
    # Digits are centered. Four inset corner patches avoid both text and grid
    # antialiasing and remain robust in the narrow x=1.0 column.
    patches = (
        gray[y0 + 4:y0 + 10, x0 + 4:x0 + 12],
        gray[y0 + 4:y0 + 10, x1 - 12:x1 - 4],
        gray[y1 - 10:y1 - 4, x0 + 4:x0 + 12],
        gray[y1 - 10:y1 - 4, x1 - 12:x1 - 4],
    )
    pixels = np.concatenate([patch.ravel() for patch in patches if patch.size])
    return float(np.median(pixels))


def extract_page(path: Path) -> np.ndarray:
    gray = np.asarray(Image.open(path).convert("L").rotate(270, expand=True))
    x_lines = _quality_grid_lines(gray)
    y_lines = _row_grid_lines(gray)
    # The first two grid rows are the P/G/quality heading and units row.
    values = np.empty((len(y_lines) - 3, QUALITY.size), dtype=float)
    for row in range(2, len(y_lines) - 1):
        for column in range(QUALITY.size):
            values[row - 2, column] = _corner_background(
                gray, y_lines[row], y_lines[row + 1],
                x_lines[column], x_lines[column + 1],
            )
    return values


def _cluster_tones(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # Ordered initial tones correspond to black, medium gray, light gray,
    # and unshaded paper. Re-estimation accommodates scanner/render variance.
    centres = np.array((70.0, 150.0, 192.0, 254.0))
    flat = samples.ravel()
    for _ in range(30):
        assignments = np.argmin(abs(flat[:, None] - centres[None, :]), axis=1)
        updated = np.array([
            flat[assignments == index].mean() if np.any(assignments == index) else centres[index]
            for index in range(4)
        ])
        if np.allclose(updated, centres):
            break
        centres = updated
    order = np.argsort(centres)
    rank = np.empty(4, dtype=np.uint8)
    # Dark-to-light cluster ranks map to LQR, avoid, calculated, direct.
    rank[order] = np.array((3, 2, 1, 0), dtype=np.uint8)
    return rank[assignments].reshape(samples.shape), centres[order]


def extract_pages(paths: list[Path]) -> tuple[np.ndarray, np.ndarray, list[int]]:
    page_arrays = [extract_page(path) for path in paths]
    row_counts = [array.shape[0] for array in page_arrays]
    samples = np.concatenate(page_arrays, axis=0)
    expected_rows = PRESSURE_MPA.size * MASS_FLUX.size
    if samples.shape != (expected_rows, QUALITY.size):
        raise RuntimeError(
            f"extracted {samples.shape}; expected ({expected_rows}, {QUALITY.size}); "
            f"page rows={row_counts}"
        )
    classes, centres = _cluster_tones(samples)
    return classes.reshape(PRESSURE_MPA.size, MASS_FLUX.size, QUALITY.size), centres, row_counts


def write_csv(path: Path, classes: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("pressure_MPa", "mass_flux_kg_m2_s", *(f"x={x:g}" for x in QUALITY)))
        for ip, pressure in enumerate(PRESSURE_MPA):
            for ig, mass_flux in enumerate(MASS_FLUX):
                writer.writerow((f"{pressure:g}", f"{mass_flux:g}", *classes[ip, ig]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pages", type=Path, help="directory containing page-*.png")
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    # The requested render range can include following text-only pages. Their
    # much smaller PNGs are excluded before grid extraction.
    paths = [path for path in sorted(arguments.pages.glob("page-*.png"))
             if path.stat().st_size > 100_000]
    classes, centres, row_counts = extract_pages(paths)
    write_csv(arguments.output, classes)
    counts = np.bincount(classes.ravel(), minlength=4)
    print(f"pages: {len(paths)}; rows/page: {row_counts}")
    print(f"tone centres dark-to-light: {centres.tolist()}")
    print("classes: " + ", ".join(
        f"{label}={int(counts[index])}" for index, label in enumerate(CLASS_LABELS)
    ))
    print(f"wrote: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
