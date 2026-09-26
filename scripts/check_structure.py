#!/usr/bin/env python3
"""Validate repository structure and privacy guardrails."""

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
    "src/olivar_vision/data_audit.py",
    "src/olivar_vision/image_fingerprint.py",
    "src/olivar_vision/lidar_capture.py",
    "src/olivar_vision/lidar_geometry.py",
    "src/olivar_vision/biomass_carbon.py",
    "scripts/data_audit.py",
    "scripts/check_apple_toolchain.py",
    "scripts/lidar_session.py",
    "scripts/olive_metrics.py",
    "scripts/validate_dataset_manifest.py",
    "tests/test_status.py",
    "tests/test_dataset_manifest.py",
    "tests/test_data_audit.py",
    "tests/test_lidar_capture.py",
    "tests/test_lidar_geometry.py",
    "tests/test_biomass_carbon.py",
    "tests/test_apple_toolchain.py",
    "configs/README.md",
    "configs/datasets.json",
    "configs/data_audit.json",
    "configs/biomass-carbon.example.json",
    "docs/README.md",
    "docs/data-audit.md",
    "docs/lidar-carbon.md",
    "ios/OlivarLidarCapture/Package.swift",
    "ios/OlivarLidarCapture/README.md",
    "ios/OlivarLidarCapture/Sources/OlivarLidarCapture/ARKitCaptureController.swift",
    "ios/OlivarLidarCapture/Sources/OlivarLidarCapture/CaptureContract.swift",
    "ios/OlivarLidarCapture/Sources/OlivarLidarCapture/OfflineSessionWriter.swift",
    "ios/OlivarLidarCapture/Sources/OlivarLidarCapture/SystemCapabilityDetector.swift",
    "ios/OlivarLidarCapture/Sources/OlivarLidarCapture/LidarCaptureView.swift",
    "ios/OlivarLidarCapture/Sources/OlivarLidarCapture/BiomassCarbonEstimator.swift",
    "ios/OlivarLidarCapture/Sources/OlivarLidarCapture/BiomassCarbonView.swift",
    "ios/OlivarLidarCapture/Tests/OlivarLidarCaptureTests/CaptureContractTests.swift",
    "ios/OlivarLidarCapture/Tests/OlivarLidarCaptureTests/BiomassCarbonEstimatorTests.swift",
    "ios/OlivarVisionLidarApp/OlivarVisionLidarApp.xcodeproj/project.pbxproj",
    "ios/OlivarVisionLidarApp/OlivarVisionLidarApp.xcodeproj/xcshareddata/xcschemes/OlivarVisionLidarApp.xcscheme",
    "ios/OlivarVisionLidarApp/OlivarVisionLidarApp/OlivarVisionLidarApp.swift",
    "ios/OlivarVisionLidarApp/OlivarVisionLidarApp/ContentView.swift",
    "ios/OlivarVisionLidarApp/OlivarVisionLidarApp/Info.plist",
    "ios/OlivarVisionLidarApp/README.md",
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
    "data/field/",
    "datasets/",
    "photos/",
    "field_photos/",
    "models/*",
    "*.mlpackage/",
    "*.mlmodel",
    "*.pt",
    "*.pth",
    "reports/dataset_audit.json",
    "reports/dataset_audit.md",
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
    for target in (
        "setup:\n",
        "check:\n",
        "status:\n",
        "data-audit:\n",
        "lidar-process:\n",
        "lidar-compare:\n",
        "lidar-geometry:\n",
        "lidar-geometry-compare:\n",
        "biomass-estimate:\n",
        "check-apple-toolchain:\n",
        "check-lidar-swift:",
        "check-ios:",
        "train evaluate export-coreml",
    ):
        require(target in makefile, f"Makefile missing target marker: {target}")

    print("Structure check passed: required files and privacy guardrails are present.")


if __name__ == "__main__":
    main()
