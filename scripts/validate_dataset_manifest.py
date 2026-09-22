#!/usr/bin/env python3
"""Validate the phase-1 dataset source manifest without network access."""

import sys
from pathlib import Path

from olivar_vision.dataset_manifest import ManifestError, validate_manifest_file


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else Path("configs/datasets.json")
    try:
        result = validate_manifest_file(path)
    except (OSError, ManifestError, ValueError) as exc:
        print(f"ERROR: dataset manifest validation failed: {exc}", file=sys.stderr)
        return 2

    print(
        "Dataset manifest check passed: "
        f"{result.source_count} sources, {result.apt_for_audit_count} apt for audit."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

