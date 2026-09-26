#!/usr/bin/env python3
"""Process or compare private LiDAR capture sessions without network access."""

import argparse
import json
import sys
from pathlib import Path

from olivar_vision.lidar_capture import LidarCaptureError, compare_sessions, process_session


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    process = subparsers.add_parser("process", help="validate and derive one capture session")
    process.add_argument("session_root", type=Path)
    process.add_argument("--min-confidence", type=int, choices=(0, 1, 2), default=1)

    compare = subparsers.add_parser("compare", help="compare two preserved repetitions")
    compare.add_argument("left_session", type=Path)
    compare.add_argument("right_session", type=Path)
    compare.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "process":
            report = process_session(args.session_root, args.min_confidence)
            print(
                json.dumps(
                    {
                        "session_id": report["session_id"],
                        "status": report["status"],
                        "l1_gate": report["l1_gate"]["status"],
                        "validation_report": str(
                            args.session_root / "validation" / "report.json"
                        ),
                    },
                    sort_keys=True,
                )
            )
            if report["status"] == "BLOCKED_UNSUPPORTED_DEVICE":
                return 4
            return 0 if report["status"] == "PASS" else 3

        comparison = compare_sessions(
            args.left_session,
            args.right_session,
            args.output,
        )
        print(
            json.dumps(
                {
                    "repeat_group_id": comparison["repeat_group_id"],
                    "output": str(args.output),
                },
                sort_keys=True,
            )
        )
        return 0
    except LidarCaptureError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
