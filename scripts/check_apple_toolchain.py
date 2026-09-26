#!/usr/bin/env python3
"""Diagnose whether the selected Apple toolchain can build the iOS prototype."""

import json
import subprocess
from typing import Any, Dict, Sequence, Tuple


def command_result(command: Sequence[str]) -> Tuple[int, str]:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.returncode, completed.stdout.strip()


def evaluate_toolchain(results: Dict[str, Tuple[int, str]]) -> Dict[str, Any]:
    developer_dir = results["xcode_select"][1]
    xcode_ok = results["xcodebuild"][0] == 0 and "Xcode " in results["xcodebuild"][1]
    full_xcode_selected = xcode_ok and "CommandLineTools" not in developer_dir
    status = "READY" if full_xcode_selected else "BLOCKED_FULL_XCODE_REQUIRED"
    return {
        "status": status,
        "ready": full_xcode_selected,
        "developer_dir": developer_dir or None,
        "xcodebuild": results["xcodebuild"][1] or None,
        "swift": results["swift"][1] or None,
        "sdk_path": results["sdk_path"][1] if results["sdk_path"][0] == 0 else None,
        "remediation": [
            "Install the full Xcode application from Apple.",
            "Run: sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer",
            "Run: sudo xcodebuild -license accept",
            "Run: sudo xcodebuild -runFirstLaunch",
            "Re-run: make check-apple-toolchain check-lidar-swift check-ios",
        ] if not full_xcode_selected else [],
    }


def main() -> int:
    results = {
        "xcode_select": command_result(("xcode-select", "-p")),
        "xcodebuild": command_result(("xcodebuild", "-version")),
        "swift": command_result(("swift", "--version")),
        "sdk_path": command_result(("xcrun", "--show-sdk-path")),
    }
    report = evaluate_toolchain(results)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
