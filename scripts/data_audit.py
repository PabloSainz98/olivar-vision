#!/usr/bin/env python3
"""Run the read-only phase-2 image audit against authorized local data."""

import argparse
import os
import sys
from pathlib import Path

from olivar_vision.data_audit import (
    AuditError,
    NoDataError,
    audit_dataset_roots,
    load_audit_config,
    roots_from_environment,
    sha256_file,
    write_reports,
)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/data_audit.json"))
    parser.add_argument("--manifest", type=Path, default=Path("configs/datasets.json"))
    parser.add_argument("--output-json", type=Path, default=Path("reports/dataset_audit.json"))
    parser.add_argument("--output-markdown", type=Path, default=Path("reports/dataset_audit.md"))
    parser.add_argument(
        "--replace-report",
        action="store_true",
        help="Replace a different historical report only after explicit review.",
    )
    return parser


def main(argv=None, environ=None):
    args = build_parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    try:
        config, manifest = load_audit_config(args.config, args.manifest)
        roots = roots_from_environment(config, environment)
        report = audit_dataset_roots(
            config,
            manifest,
            roots,
            config_sha256=sha256_file(args.config),
            manifest_sha256=sha256_file(args.manifest),
        )
        write_reports(
            report,
            args.output_json,
            args.output_markdown,
            replace=args.replace_report,
        )
    except NoDataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (AuditError, OSError) as exc:
        print(f"ERROR: data audit failed: {exc}", file=sys.stderr)
        return 2

    summary = report["summary"]
    print(
        "Data audit completed: "
        f"{summary['file_count']} files, "
        f"{summary['valid_image_count']} valid images, "
        f"{summary['issue_error_count']} blocking issue(s)."
    )
    print(f"JSON report: {args.output_json}")
    print(f"Markdown report: {args.output_markdown}")
    if report["result"]["audit_status"] != "PASS":
        print("ERROR: audit findings block split freezing.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
