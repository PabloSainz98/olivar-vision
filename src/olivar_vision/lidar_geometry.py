"""Quality-gated tree geometry derived from an L1 point cloud."""

import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from olivar_vision.lidar_capture import (
    GEOMETRY_FORMAT_ID as L1_GEOMETRY_FORMAT_ID,
    POINT_FORMAT,
    VALIDATION_FORMAT_ID,
    canonical_json,
)


GEOMETRY_OUTPUT_FORMAT_ID = "olivar-tree-geometry-measurement"
GEOMETRY_COMPARISON_FORMAT_ID = "olivar-tree-geometry-comparison"
SCHEMA_VERSION = 1
WORLD_COORDINATE_SYSTEM = "arkit_world_right_handed_y_up"
MIN_POINT_COUNT = 12
MIN_SAMPLE_COVERAGE = 0.50
MIN_VERTICAL_COVERAGE = 0.80
MIN_BASAL_ANGULAR_COVERAGE = 0.75
MAX_BASAL_RADIAL_RMSE_M = 0.02


class LidarGeometryError(ValueError):
    """Raised for invalid geometry inputs or source artifacts."""


def measure_tree_geometry(
    points: Iterable[Sequence[float]],
    *,
    tree_isolated: bool,
    sample_coverage_fraction: float,
    vertical_coverage_fraction: float,
    ground_y_m: Optional[float],
    units: str = "meter",
    coordinate_system: str = WORLD_COORDINATE_SYSTEM,
    basal_measurement_height_m: float = 0.3,
    basal_slice_half_thickness_m: float = 0.025,
) -> Dict[str, Any]:
    """Measure an isolated tree while retaining observed bounds and quality.

    Extents are only promoted to tree measurements when the caller confirms an
    isolated tree, supplies a ground reference, and meets the operational
    coverage thresholds. No volume is inferred from an open surface.
    """

    normalized_points = tuple(_point3(point) for point in points)
    reasons: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    sample_coverage = _fraction(sample_coverage_fraction, "sample_coverage_fraction")
    vertical_coverage = _fraction(vertical_coverage_fraction, "vertical_coverage_fraction")
    ground_y = _optional_finite(ground_y_m, "ground_y_m")
    basal_height = _positive_finite(basal_measurement_height_m, "basal_measurement_height_m")
    slice_half = _positive_finite(basal_slice_half_thickness_m, "basal_slice_half_thickness_m")

    if units != "meter":
        reasons.append(_reason("unsupported_units", "geometry v1 requires meter units"))
    if coordinate_system != WORLD_COORDINATE_SYSTEM:
        reasons.append(
            _reason(
                "unsupported_coordinate_system",
                f"geometry v1 requires {WORLD_COORDINATE_SYSTEM}",
            )
        )
    if not tree_isolated:
        reasons.append(
            _reason(
                "tree_not_isolated",
                "the point set must contain one segmented tree and no surrounding scene",
            )
        )
    if len(normalized_points) < MIN_POINT_COUNT:
        reasons.append(
            _reason(
                "insufficient_points",
                f"at least {MIN_POINT_COUNT} finite points are required",
            )
        )
    if sample_coverage < MIN_SAMPLE_COVERAGE:
        reasons.append(
            _reason(
                "insufficient_sample_coverage",
                f"sample coverage must be at least {MIN_SAMPLE_COVERAGE:.2f}",
            )
        )
    if vertical_coverage < MIN_VERTICAL_COVERAGE:
        reasons.append(
            _reason(
                "insufficient_vertical_coverage",
                f"vertical coverage must be at least {MIN_VERTICAL_COVERAGE:.2f}",
            )
        )
    if ground_y is None:
        reasons.append(
            _reason(
                "missing_ground_reference",
                "ground_y_m is required to distinguish tree height from an observed Y extent",
            )
        )

    observed_bounds = _bounds(normalized_points) if normalized_points else None
    if observed_bounds is not None and ground_y is not None:
        minimum_y = observed_bounds["minimum_m"][1]
        if abs(minimum_y - ground_y) > 0.10:
            reasons.append(
                _reason(
                    "ground_reference_not_observed",
                    "ground_y_m must be within 0.10 m of the lowest observed tree point",
                )
            )

    measurements: Optional[Dict[str, Any]] = None
    basal_result: Dict[str, Any] = {
        "status": "ESTIMATION_NOT_AVAILABLE",
        "reasons": [],
    }
    if not reasons and observed_bounds is not None and ground_y is not None:
        minimum = observed_bounds["minimum_m"]
        maximum = observed_bounds["maximum_m"]
        basal_result = _estimate_basal_diameter(
            normalized_points,
            ground_y + basal_height,
            slice_half,
            basal_height,
        )
        measurements = {
            "height_m": _rounded(maximum[1] - ground_y),
            "crown_span_x_m": _rounded(maximum[0] - minimum[0]),
            "crown_span_z_m": _rounded(maximum[2] - minimum[2]),
            "basal_diameter": basal_result,
            "volume": {
                "status": "ESTIMATION_NOT_AVAILABLE",
                "reason": "an open observed surface is not a complete tree volume",
            },
        }
        if basal_result["status"] != "AVAILABLE":
            warnings.append(
                _reason(
                    "basal_diameter_unavailable",
                    "height and observed crown spans are available, but basal diameter failed its quality gate",
                )
            )

    if reasons:
        status = "ESTIMATION_NOT_AVAILABLE"
    elif basal_result["status"] == "AVAILABLE":
        status = "AVAILABLE"
    else:
        status = "PARTIAL"

    return {
        "format_id": GEOMETRY_OUTPUT_FORMAT_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "units": units,
        "coordinate_system": coordinate_system,
        "quality": {
            "tree_isolated": tree_isolated,
            "point_count": len(normalized_points),
            "sample_coverage_fraction": _rounded(sample_coverage),
            "vertical_coverage_fraction": _rounded(vertical_coverage),
            "operational_thresholds": {
                "minimum_point_count": MIN_POINT_COUNT,
                "minimum_sample_coverage_fraction": MIN_SAMPLE_COVERAGE,
                "minimum_vertical_coverage_fraction": MIN_VERTICAL_COVERAGE,
                "minimum_basal_angular_coverage_fraction": MIN_BASAL_ANGULAR_COVERAGE,
                "maximum_basal_radial_rmse_m": MAX_BASAL_RADIAL_RMSE_M,
            },
        },
        "availability": {"available": not reasons, "reasons": reasons},
        "warnings": warnings,
        "observed_bounds": observed_bounds,
        "measurements": measurements,
        "l2_gate": {
            "status": "PENDING_FIELD_VALIDATION",
            "validated": False,
        },
        "surface_completeness": "open_observed_surface",
        "represents_complete_tree_volume": False,
        "limitations": [
            "Crown spans are axis-aligned extents in the ARKit world frame.",
            "Measurements require a separately isolated tree and explicit ground reference.",
            "No complete volume, woody volume, biomass, or carbon is inferred here.",
        ],
    }


def measure_session_geometry(
    session_root: Path,
    output_path: Path,
    *,
    tree_isolated: bool,
    vertical_coverage_fraction: float,
    ground_y_m: Optional[float],
) -> Dict[str, Any]:
    """Measure a processed L1 session and write a non-overwriting report."""

    root = session_root.expanduser().resolve()
    geometry_path = root / "derived" / "geometry.json"
    validation_path = root / "validation" / "report.json"
    geometry = _read_json(geometry_path)
    validation = _read_json(validation_path)
    if geometry.get("format_id") != L1_GEOMETRY_FORMAT_ID or geometry.get("schema_version") != 1:
        raise LidarGeometryError("unsupported L1 geometry format")
    if validation.get("format_id") != VALIDATION_FORMAT_ID or validation.get("schema_version") != 1:
        raise LidarGeometryError("unsupported L1 validation format")
    point_record = geometry.get("point_cloud")
    if not isinstance(point_record, Mapping):
        raise LidarGeometryError("derived geometry has no point_cloud record")
    if point_record.get("format") != POINT_FORMAT:
        raise LidarGeometryError("unsupported point cloud format")
    point_path = _source_path(root, point_record.get("path"))
    point_bytes = point_path.read_bytes()
    if hashlib.sha256(point_bytes).hexdigest() != point_record.get("sha256"):
        raise LidarGeometryError("point cloud SHA-256 does not match its derived record")
    point_count = point_record.get("point_count")
    if isinstance(point_count, bool) or not isinstance(point_count, int) or point_count < 0:
        raise LidarGeometryError("point cloud count must be a non-negative integer")
    expected_size = point_count * 12
    if len(point_bytes) != expected_size:
        raise LidarGeometryError("point cloud size does not match its derived record")
    points = tuple(struct.iter_unpack("<fff", point_bytes))
    coverage = validation.get("coverage")
    if not isinstance(coverage, Mapping):
        raise LidarGeometryError("validation report has no coverage object")

    report = measure_tree_geometry(
        points,
        tree_isolated=tree_isolated,
        sample_coverage_fraction=coverage.get("sample_coverage_fraction"),
        vertical_coverage_fraction=vertical_coverage_fraction,
        ground_y_m=ground_y_m,
        units=str(point_record.get("units")),
        coordinate_system=str(point_record.get("coordinate_system")),
    )
    if validation.get("status") != "PASS":
        report["availability"]["available"] = False
        report["availability"]["reasons"].append(
            _reason(
                "source_l1_validation_not_passed",
                "tree measurements require a PASS source validation report",
            )
        )
        report["status"] = "ESTIMATION_NOT_AVAILABLE"
        report["measurements"] = None
    report["source"] = {
        "session_id": validation.get("session_id"),
        "repeat_group_id": validation.get("repeat_group_id"),
        "l1_validation_status": validation.get("status"),
        "source_geometry_path": str(geometry_path),
        "source_geometry_sha256": _sha256_file(geometry_path),
        "point_cloud_path": str(point_path),
        "point_cloud_sha256": point_record.get("sha256"),
        "l1_gate": validation.get("l1_gate"),
    }
    _write_json_exclusive(output_path, report)
    return report


def compare_tree_geometry_reports(
    left_path: Path,
    right_path: Path,
    output_path: Path,
) -> Dict[str, Any]:
    """Compare two preserved geometry reports from the same repeat group."""

    left = _read_geometry_measurement(left_path)
    right = _read_geometry_measurement(right_path)
    if left.get("units") != "meter" or right.get("units") != "meter":
        raise LidarGeometryError("geometry comparison requires meter units")
    if left.get("coordinate_system") != right.get("coordinate_system"):
        raise LidarGeometryError("geometry reports use different coordinate systems")
    left_source = _mapping(left.get("source"), "left source")
    right_source = _mapping(right.get("source"), "right source")
    left_session = left_source.get("session_id")
    right_session = right_source.get("session_id")
    if not isinstance(left_session, str) or not isinstance(right_session, str):
        raise LidarGeometryError("both geometry reports require source session IDs")
    if left_session == right_session:
        raise LidarGeometryError("geometry comparison requires different session IDs")
    repeat_group = left_source.get("repeat_group_id")
    if not isinstance(repeat_group, str) or not repeat_group:
        raise LidarGeometryError("left geometry report has no repeat_group_id")
    if repeat_group != right_source.get("repeat_group_id"):
        raise LidarGeometryError("geometry reports do not belong to the same repeat group")

    comparisons: Dict[str, Any] = {}
    for name, path in (
        ("height_m", ("measurements", "height_m")),
        ("crown_span_x_m", ("measurements", "crown_span_x_m")),
        ("crown_span_z_m", ("measurements", "crown_span_z_m")),
        ("basal_diameter_m", ("measurements", "basal_diameter", "diameter_m")),
    ):
        left_value = _nested_number(left, path)
        right_value = _nested_number(right, path)
        if left_value is None or right_value is None:
            comparisons[name] = {
                "status": "ESTIMATION_NOT_AVAILABLE",
                "left": left_value,
                "right": right_value,
                "reason": "measurement is unavailable in one or both reports",
            }
            continue
        difference = right_value - left_value
        comparisons[name] = {
            "status": "AVAILABLE",
            "left": _rounded(left_value),
            "right": _rounded(right_value),
            "difference": _rounded(difference),
            "absolute_difference": _rounded(abs(difference)),
            "relative_difference_fraction": (
                _rounded(difference / left_value) if abs(left_value) > 1e-12 else None
            ),
        }

    available_count = sum(item["status"] == "AVAILABLE" for item in comparisons.values())
    report = {
        "format_id": GEOMETRY_COMPARISON_FORMAT_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "COMPARISON_AVAILABLE" if available_count else "ESTIMATION_NOT_AVAILABLE",
        "repeat_group_id": repeat_group,
        "sessions": [
            _geometry_summary(left, left_path),
            _geometry_summary(right, right_path),
        ],
        "measurements": comparisons,
        "available_measurement_count": available_count,
        "l2_gate": {
            "status": "PENDING_FIELD_VALIDATION",
            "validated": False,
        },
        "limitations": [
            "A pairwise difference is not a repeatability statistic or field validation.",
            "Coverage and quality must be reviewed for both sessions before interpreting deltas.",
            "No volume, biomass, carbon, or annual CO2 value is compared here.",
        ],
    }
    _write_json_exclusive(output_path, report)
    return report


def _estimate_basal_diameter(
    points: Sequence[Tuple[float, float, float]],
    target_y_m: float,
    half_thickness_m: float,
    height_above_ground_m: float,
) -> Dict[str, Any]:
    slice_points = [
        (point[0], point[2])
        for point in points
        if abs(point[1] - target_y_m) <= half_thickness_m
    ]
    reasons: List[Dict[str, str]] = []
    if len(slice_points) < MIN_POINT_COUNT:
        reasons.append(
            _reason(
                "insufficient_basal_slice_points",
                f"basal slice requires at least {MIN_POINT_COUNT} points",
            )
        )
        return {"status": "ESTIMATION_NOT_AVAILABLE", "reasons": reasons}
    try:
        center_x, center_z, radius = _fit_circle(slice_points)
    except LidarGeometryError as exc:
        reasons.append(_reason("circle_fit_failed", str(exc)))
        return {"status": "ESTIMATION_NOT_AVAILABLE", "reasons": reasons}

    residuals = [math.hypot(x - center_x, z - center_z) - radius for x, z in slice_points]
    rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    angles = sorted(math.atan2(z - center_z, x - center_x) % (2.0 * math.pi) for x, z in slice_points)
    gaps = [right - left for left, right in zip(angles, angles[1:])]
    gaps.append((angles[0] + 2.0 * math.pi) - angles[-1])
    angular_coverage = 1.0 - max(gaps) / (2.0 * math.pi)
    if angular_coverage < MIN_BASAL_ANGULAR_COVERAGE:
        reasons.append(
            _reason(
                "insufficient_basal_angular_coverage",
                f"basal angular coverage must be at least {MIN_BASAL_ANGULAR_COVERAGE:.2f}",
            )
        )
    if rmse > MAX_BASAL_RADIAL_RMSE_M:
        reasons.append(
            _reason(
                "basal_circle_fit_low_quality",
                f"basal radial RMSE must be at most {MAX_BASAL_RADIAL_RMSE_M:.3f} m",
            )
        )
    return {
        "status": "AVAILABLE" if not reasons else "ESTIMATION_NOT_AVAILABLE",
        "method": "least_squares_circle_xz",
        "measurement_height_above_ground_m": _rounded(height_above_ground_m),
        "slice_center_world_y_m": _rounded(target_y_m),
        "slice_half_thickness_m": _rounded(half_thickness_m),
        "point_count": len(slice_points),
        "diameter_m": _rounded(2.0 * radius) if not reasons else None,
        "diameter_cm": _rounded(200.0 * radius) if not reasons else None,
        "center_xz_m": [_rounded(center_x), _rounded(center_z)],
        "angular_coverage_fraction": _rounded(angular_coverage),
        "radial_rmse_m": _rounded(rmse),
        "reasons": reasons,
    }


def _fit_circle(points: Sequence[Tuple[float, float]]) -> Tuple[float, float, float]:
    # Kasa algebraic circle fit: x^2 + z^2 + A*x + B*z + C = 0.
    n = float(len(points))
    sx = sum(point[0] for point in points)
    sz = sum(point[1] for point in points)
    sxx = sum(point[0] * point[0] for point in points)
    szz = sum(point[1] * point[1] for point in points)
    sxz = sum(point[0] * point[1] for point in points)
    rhs = [
        -sum(point[0] * (point[0] ** 2 + point[1] ** 2) for point in points),
        -sum(point[1] * (point[0] ** 2 + point[1] ** 2) for point in points),
        -sum(point[0] ** 2 + point[1] ** 2 for point in points),
    ]
    a, b, c = _solve_3x3(
        [[sxx, sxz, sx], [sxz, szz, sz], [sx, sz, n]],
        rhs,
    )
    center_x = -a / 2.0
    center_z = -b / 2.0
    radius_squared = center_x * center_x + center_z * center_z - c
    if not math.isfinite(radius_squared) or radius_squared <= 0:
        raise LidarGeometryError("circle fit produced a non-positive radius")
    return center_x, center_z, math.sqrt(radius_squared)


def _solve_3x3(matrix: List[List[float]], values: List[float]) -> Tuple[float, float, float]:
    rows = [matrix[index][:] + [values[index]] for index in range(3)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(rows[row][column]))
        if abs(rows[pivot][column]) < 1e-12:
            raise LidarGeometryError("basal points do not define a stable circle")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        scale = rows[column][column]
        rows[column] = [value / scale for value in rows[column]]
        for row in range(3):
            if row == column:
                continue
            factor = rows[row][column]
            rows[row] = [
                rows[row][index] - factor * rows[column][index]
                for index in range(4)
            ]
    return rows[0][3], rows[1][3], rows[2][3]


def _bounds(points: Sequence[Tuple[float, float, float]]) -> Dict[str, Any]:
    minimum = [min(point[index] for point in points) for index in range(3)]
    maximum = [max(point[index] for point in points) for index in range(3)]
    return {
        "minimum_m": [_rounded(value) for value in minimum],
        "maximum_m": [_rounded(value) for value in maximum],
        "extent_m": [_rounded(maximum[index] - minimum[index]) for index in range(3)],
    }


def _point3(value: Sequence[float]) -> Tuple[float, float, float]:
    if isinstance(value, (str, bytes)) or len(value) != 3:
        raise LidarGeometryError("each point must contain three coordinates")
    coordinates = tuple(_finite(item, "point coordinate") for item in value)
    return coordinates  # type: ignore[return-value]


def _fraction(value: Any, field: str) -> float:
    number = _finite(value, field)
    if not 0.0 <= number <= 1.0:
        raise LidarGeometryError(f"{field} must be between 0 and 1")
    return number


def _positive_finite(value: Any, field: str) -> float:
    number = _finite(value, field)
    if number <= 0:
        raise LidarGeometryError(f"{field} must be positive")
    return number


def _optional_finite(value: Any, field: str) -> Optional[float]:
    return None if value is None else _finite(value, field)


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LidarGeometryError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise LidarGeometryError(f"{field} must be a finite number")
    return number


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LidarGeometryError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LidarGeometryError(f"{path} must contain a JSON object")
    return value


def _read_geometry_measurement(path: Path) -> Dict[str, Any]:
    value = _read_json(path.expanduser().resolve())
    if value.get("format_id") != GEOMETRY_OUTPUT_FORMAT_ID or value.get("schema_version") != SCHEMA_VERSION:
        raise LidarGeometryError(f"unsupported geometry measurement format: {path}")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LidarGeometryError(f"{field} must be an object")
    return value


def _nested_number(value: Mapping[str, Any], path: Sequence[str]) -> Optional[float]:
    current: Any = value
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        return None
    number = float(current)
    return number if math.isfinite(number) else None


def _geometry_summary(report: Mapping[str, Any], path: Path) -> Dict[str, Any]:
    source = _mapping(report.get("source"), "geometry source")
    quality = report.get("quality")
    return {
        "session_id": source.get("session_id"),
        "file_name": path.name,
        "sha256": _sha256_file(path.expanduser().resolve()),
        "status": report.get("status"),
        "quality": dict(quality) if isinstance(quality, Mapping) else None,
    }


def _source_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise LidarGeometryError("point cloud path must be a non-empty relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise LidarGeometryError("point cloud path must stay inside the session root")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise LidarGeometryError("point cloud path must stay inside the session root") from exc
    return resolved


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    try:
        with resolved.open("x", encoding="utf-8") as handle:
            handle.write(canonical_json(value))
    except FileExistsError as exc:
        raise LidarGeometryError(f"refusing to overwrite historical output: {resolved}") from exc


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reason(code: str, detail: str) -> Dict[str, str]:
    return {"code": code, "detail": detail}


def _rounded(value: float) -> float:
    return round(value, 6)
