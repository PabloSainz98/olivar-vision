#!/usr/bin/env python3
"""Verify the local project environment without network or downloads."""

import platform
import shutil
import subprocess
import sys


MIN_VERSION = (3, 9)
MIN_NODE_MAJOR = 20


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

    node_version = tool_version(["node", "--version"])
    if node_version is None:
        print("ERROR: Node.js 20 or newer is required for the web checks.", file=sys.stderr)
        return 2
    try:
        node_major = int(node_version.removeprefix("v").split(".", 1)[0])
    except ValueError:
        print(f"ERROR: could not parse Node.js version: {node_version}", file=sys.stderr)
        return 2
    if node_major < MIN_NODE_MAJOR:
        print("ERROR: Node.js 20 or newer is required for the web checks.", file=sys.stderr)
        return 2

    print("Olivar Vision local setup")
    print(f"Python: {platform.python_version()} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    print(f"git: {tool_version(['git', '--version']) or 'NOT FOUND'}")
    print(f"make: {tool_version(['make', '--version']) or 'NOT FOUND'}")
    print(f"Node.js: {node_version}")
    print("External Python dependencies: none")
    print("Network access: not required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
