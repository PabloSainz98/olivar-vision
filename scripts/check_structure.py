#!/usr/bin/env python3
"""Validate the phase-0 repository structure and privacy guardrails."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "README.md",
    ".gitignore",
    "Makefile",
    "pyproject.toml",
    "src/olivar_vision/__init__.py",
    "src/olivar_vision/status.py",
    "src/olivar_vision/dataset_manifest.py",
    "scripts/validate_dataset_manifest.py",
    "tests/test_status.py",
    "tests/test_dataset_manifest.py",
    "configs/README.md",
    "configs/datasets.json",
    "docs/README.md",
    "reports/datasets.md",
    "reports/.gitkeep",
    "data/README.md",
    "models/README.md",
]

REQUIRED_README_SECTIONS = [
    "## Estado vivo",
    "## Registro de fases",
    "## Decisiones y bloqueos",
    "## Siguiente accion",
    "## Instalacion y comandos",
]

REQUIRED_IGNORES = [
    "data/raw/",
    "data/private/",
    "datasets/",
    "photos/",
    "field_photos/",
    "models/*",
    "*.mlpackage/",
    "*.mlmodel",
    "*.pt",
    "*.pth",
]


def require(condition, message):
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def main():
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    require(not missing, "missing required paths: " + ", ".join(missing))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing_sections = [section for section in REQUIRED_README_SECTIONS if section not in readme]
    require(not missing_sections, "README missing sections: " + ", ".join(missing_sections))

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    missing_ignores = [pattern for pattern in REQUIRED_IGNORES if pattern not in gitignore]
    require(not missing_ignores, ".gitignore missing safeguards: " + ", ".join(missing_ignores))

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("setup:", "check:", "status:", "data-audit train evaluate export-coreml"):
        require(target in makefile, f"Makefile missing target marker: {target}")

    print("Structure check passed: phase-0 files and privacy guardrails are present.")


if __name__ == "__main__":
    main()
