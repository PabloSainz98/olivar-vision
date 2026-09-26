#!/usr/bin/env python3
"""Derive quality-gated tree geometry or an experimental biomass estimate."""

import argparse
import json
import sys
from pathlib import Path

from olivar_vision.biomass_carbon import BiomassCarbonError, estimate_biomass_carbon
from olivar_vision.lidar_capture import canonical_json
from olivar_vision.lidar_geometry import (
    LidarGeometryError,
    compare_tree_geometry_reports,
    measure_session_geometry,
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    geometry = subparsers.add_parser("geometry", help="measure a processed L1 session")
    geometry.add_argument("session_root", type=Path)
    geometry.add_argument("--output", type=Path, required=True)
    geometry.add_argument("--tree-isolated", action="store_true")
    geometry.add_argument("--vertical-coverage", type=float, required=True)
    geometry.add_argument("--ground-y-m", type=float)

    geometry_compare = subparsers.add_parser(
        "geometry-compare", help="compare two preserved tree geometry reports"
    )
    geometry_compare.add_argument("left", type=Path)
    geometry_compare.add_argument("right", type=Path)
    geometry_compare.add_argument("--output", type=Path, required=True)

    estimate = subparsers.add_parser("estimate", help="calculate a versioned experimental estimate")
    estimate.add_argument("input", type=Path)
    estimate.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "geometry":
            report = measure_session_geometry(
                args.session_root,
                args.output,
                tree_isolated=args.tree_isolated,
                vertical_coverage_fraction=args.vertical_coverage,
                ground_y_m=args.ground_y_m,
            )
        elif args.command == "geometry-compare":
            report = compare_tree_geometry_reports(args.left, args.right, args.output)
        else:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise BiomassCarbonError("input must contain a JSON object")
            report = estimate_biomass_carbon(payload)
            output = args.output.expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            try:
                with output.open("x", encoding="utf-8") as handle:
                    handle.write(canonical_json(report))
            except FileExistsError as exc:
                raise BiomassCarbonError(
                    f"refusing to overwrite historical output: {output}"
                ) from exc
        print(
            json.dumps(
                {"status": report["status"], "output": str(args.output)},
                sort_keys=True,
            )
        )
        return 0 if report["status"] in {
            "AVAILABLE",
            "PARTIAL",
            "COMPARISON_AVAILABLE",
            "EXPERIMENTAL_ESTIMATE",
        } else 3
    except (BiomassCarbonError, LidarGeometryError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
