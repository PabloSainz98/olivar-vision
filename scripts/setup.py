#!/usr/bin/env python3
"""Verify the local project environment without network or downloads."""

import platform
import shutil
import subprocess
import sys


MIN_VERSION = (3, 9)


def tool_version(command):
    executable = shutil.which(command[0])
    if executable is None:
        return None
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else executable


def main():
    if sys.version_info < MIN_VERSION:
        print(
            "ERROR: Python 3.9 or newer is required for the project checks.",
            file=sys.stderr,
        )
        return 2

    print("Olivar Vision local setup")
    print(f"Python: {platform.python_version()} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    print(f"git: {tool_version(['git', '--version']) or 'NOT FOUND'}")
    print(f"make: {tool_version(['make', '--version']) or 'NOT FOUND'}")
    print("External Python dependencies: none")
    print("Network access: not required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
