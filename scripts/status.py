#!/usr/bin/env python3
"""Print project status extracted from README.md."""

import sys
from pathlib import Path

from olivar_vision.status import load_status


def main(argv):
    readme = Path(argv[1]) if len(argv) > 1 else Path("README.md")
    if not readme.exists():
        print(f"ERROR: {readme} does not exist.", file=sys.stderr)
        return 2

    status = load_status(readme)
    for line in status.as_lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

