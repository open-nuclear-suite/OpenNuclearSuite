"""Command-line integrity check for the bundled Groeneveld 2006 CHF table."""

from __future__ import annotations

from .groeneveld_lut import validate_groeneveld_data


def main() -> int:
    result = validate_groeneveld_data()
    print(f"shape: {result.shape}")
    print(f"SHA-256: {result.sha256}")
    print(f"checksum: {'PASS' if result.checksum_matches else 'FAIL'}")
    print(f"published anchors: {'PASS' if result.anchors_match else 'FAIL'}")
    print(f"overall: {'PASS' if result.valid else 'FAIL'}")
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
