"""Versioned, offline processing for traceable LiDAR capture sessions."""

import hashlib
import json
import math
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


CAPTURE_FORMAT_ID = "olivar-lidar-capture"
CAPTURE_SCHEMA_VERSION = 1
GEOMETRY_FORMAT_ID = "olivar-lidar-geometry"
VALIDATION_FORMAT_ID = "olivar-lidar-validation"
COMPARISON_FORMAT_ID = "olivar-lidar-comparison"
WORLD_COORDINATE_SYSTEM = "arkit_world_right_handed_y_up"
CAMERA_COORDINATE_SYSTEM = "depth_camera_optical_x_right_y_down_z_forward"
POINT_FORMAT = "float32_le_xyz"


class LidarCaptureError(ValueError):
    """Raised when a capture package is unsafe, invalid, or would be overwritten."""


class FrameValidationError(LidarCaptureError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FrameResult:
    frame_id: str
    timestamp_s: float
    points: Tuple[Tuple[float, float, float], ...]
    total_samples: int
    finite_positive_samples: int
    confidence_accepted_samples: int
    confidence_counts: Tuple[int, int, int]
    quality_flags: Tuple[str, ...]


def project_depth_pixel(
    u: int,
    v: int,
    depth_m: float,
    intrinsics: Mapping[str, float],
) -> Tuple[float, float, float]:
    """Project one depth pixel into the documented optical camera coordinates."""

    fx = _finite_positive(intrinsics.get("fx"), "intrinsics.fx")
    fy = _finite_positive(intrinsics.get("fy"), "intrinsics.fy")
    cx = _finite_number(intrinsics.get("cx"), "intrinsics.cx")
    cy = _finite_number(intrinsics.get("cy"), "intrinsics.cy")
    depth = _finite_positive(depth_m, "depth_m")
    return ((u - cx) * depth / fx, (v - cy) * depth / fy, depth)


def transform_point(
    point: Sequence[float], matrix_row_major: Sequence[float]
) -> Tuple[float, float, float]:
    """Apply a row-major homogeneous camera-to-world transform."""

    if len(point) != 3:
        raise LidarCaptureError("point must have three coordinates")
    matrix = _matrix4(matrix_row_major, "pose.matrix_row_major")
    x, y, z = (_finite_number(value, "point coordinate") for value in point)
    output = []
    for row in range(3):
        base = row * 4
        output.append(
            matrix[base] * x
            + matrix[base + 1] * y
            + matrix[base + 2] * z
            + matrix[base + 3]
        )
    denominator = matrix[12] * x + matrix[13] * y + matrix[14] * z + matrix[15]
    if not math.isfinite(denominator) or abs(denominator) < 1e-12:
        raise LidarCaptureError("pose produces an invalid homogeneous coordinate")
    return tuple(value / denominator for value in output)  # type: ignore[return-value]


def process_session(session_root: Path, min_confidence: int = 1) -> Dict[str, Any]:
    """Validate a capture session and write separate derived/validation artifacts.

    Existing derived results are never replaced. The source manifest and everything
    under ``captured/`` are fingerprinted before and after processing.
    """

    if min_confidence not in {0, 1, 2}:
        raise LidarCaptureError("min_confidence must be 0 (low), 1 (medium), or 2 (high)")
    root = _resolve_session_root(session_root)
    manifest_path = root / "session.json"
    manifest = _read_json(manifest_path, "session manifest")
    _validate_manifest_identity(manifest)
    _ensure_output_absent(root / "derived" / "geometry.json")
    _ensure_output_absent(root / "derived" / "points.f32le")
    _ensure_output_absent(root / "validation" / "report.json")

    source_manifest_sha256 = sha256_file(manifest_path)
    before = _originals_snapshot(root)
    capabilities = _mapping(manifest.get("capabilities"), "capabilities")
    capability_status = capabilities.get("status")
    if capability_status not in {"supported", "unsupported"}:
        raise LidarCaptureError("capabilities.status must be supported or unsupported")

    session_reasons = _session_rejection_reasons(manifest)
    frame_reports: List[Dict[str, Any]] = []
    all_points: List[Tuple[float, float, float]] = []
    listed_frames = manifest.get("frames")
    if not isinstance(listed_frames, list):
        raise LidarCaptureError("frames must be a list")

    if capability_status == "supported":
        previous_timestamp: Optional[float] = None
        for index, entry in enumerate(listed_frames):
            frame_id = _entry_frame_id(entry, index)
            try:
                timestamp = _finite_number(
                    _mapping(entry, f"frames[{index}]").get("timestamp_s"),
                    f"frames[{index}].timestamp_s",
                )
                if previous_timestamp is not None and timestamp <= previous_timestamp:
                    raise FrameValidationError(
                        "non_monotonic_timestamp",
                        "frame timestamps must increase strictly",
                    )
                previous_timestamp = timestamp
                result = _process_frame(root, entry, min_confidence)
            except LidarCaptureError as exc:
                code = exc.code if isinstance(exc, FrameValidationError) else "invalid_frame"
                frame_reports.append(
                    {
                        "frame_id": frame_id,
                        "status": "REJECTED",
                        "rejection_reasons": [{"code": code, "detail": str(exc)}],
                        "coverage": _empty_coverage(),
                        "quality_flags": [],
                    }
                )
                continue

            coverage = _coverage(
                result.total_samples,
                result.finite_positive_samples,
                result.confidence_accepted_samples,
                result.confidence_counts,
            )
            if not result.points:
                frame_reports.append(
                    {
                        "frame_id": result.frame_id,
                        "status": "REJECTED",
                        "rejection_reasons": [
                            {
                                "code": "insufficient_confidence",
                                "detail": "no finite positive depth sample met the confidence threshold",
                            }
                        ],
                        "coverage": coverage,
                        "quality_flags": list(result.quality_flags),
                    }
                )
                continue
            all_points.extend(result.points)
            frame_reports.append(
                {
                    "frame_id": result.frame_id,
                    "status": "ACCEPTED",
                    "timestamp_s": result.timestamp_s,
                    "point_count": len(result.points),
                    "rejection_reasons": [],
                    "coverage": coverage,
                    "quality_flags": list(result.quality_flags),
                }
            )

    accepted_frames = sum(item["status"] == "ACCEPTED" for item in frame_reports)
    rejected_frames = len(frame_reports) - accepted_frames
    total_samples = sum(item["coverage"]["depth_samples_total"] for item in frame_reports)
    finite_samples = sum(
        item["coverage"]["finite_positive_depth_samples"] for item in frame_reports
    )
    accepted_samples = sum(
        item["coverage"]["confidence_accepted_samples"] for item in frame_reports
    )
    confidence_counts = tuple(
        sum(item["coverage"]["confidence_counts"][name] for item in frame_reports)
        for name in ("low", "medium", "high")
    )
    aggregate_coverage = {
        **_coverage(total_samples, finite_samples, accepted_samples, confidence_counts),
        "frames_listed": len(listed_frames),
        "frames_accepted": accepted_frames,
        "frames_rejected": rejected_frames,
        "frame_coverage_fraction": _fraction(accepted_frames, len(listed_frames)),
        "tree_surface_coverage_status": "unknown",
    }

    frame_reasons = [
        {
            "frame_id": item["frame_id"],
            **reason,
        }
        for item in frame_reports
        for reason in item["rejection_reasons"]
    ]
    if not listed_frames and capability_status == "supported":
        session_reasons.append(
            {"code": "no_frames", "detail": "the session contains no captured frames"}
        )
    try:
        scale_validation = _validate_scale_references(manifest.get("scale_references", []))
    except LidarCaptureError as exc:
        session_reasons.append({"code": "invalid_scale_reference", "detail": str(exc)})
        scale_validation = {
            "count": 0,
            "passed_count": 0,
            "all_passed": False,
            "references": [],
        }
    discarded_frames = manifest.get("discarded_frames", [])
    if not isinstance(discarded_frames, list):
        discarded_frames = []
        session_reasons.append(
            {"code": "invalid_discard_log", "detail": "discarded_frames must be a list"}
        )

    if capability_status == "unsupported":
        validation_status = "BLOCKED_UNSUPPORTED_DEVICE"
        reason = capabilities.get("reason") or "required scene depth is unavailable"
        session_reasons.append({"code": "unsupported_device", "detail": str(reason)})
    elif session_reasons or frame_reasons:
        validation_status = "REJECTED"
    else:
        validation_status = "PASS"

    geometry: Optional[Dict[str, Any]] = None
    if all_points:
        point_bytes = b"".join(struct.pack("<fff", *point) for point in all_points)
        point_path = root / "derived" / "points.f32le"
        _write_bytes_exclusive(point_path, point_bytes)
        point_artifact = {
            "path": "derived/points.f32le",
            "format": POINT_FORMAT,
            "coordinate_system": WORLD_COORDINATE_SYSTEM,
            "units": "meter",
            "point_count": len(all_points),
            "size_bytes": len(point_bytes),
            "sha256": _sha256_bytes(point_bytes),
        }
        quality_status = "COMPLETE_INPUT" if validation_status == "PASS" else "PARTIAL_REJECTED_INPUT"
        geometry = {
            "format_id": GEOMETRY_FORMAT_ID,
            "schema_version": 1,
            "source_session_id": manifest["session_id"],
            "source_manifest_sha256": source_manifest_sha256,
            "point_cloud": point_artifact,
            "coverage": aggregate_coverage,
            "quality": {
                "status": quality_status,
                "min_confidence": min_confidence,
                "accepted_frame_count": accepted_frames,
                "rejected_frame_count": rejected_frames,
            },
            "surface_completeness": "unknown",
            "represents_complete_tree_volume": False,
            "limitations": [
                "The point cloud contains only observed, confidence-filtered surfaces.",
                "No closed surface, tree volume, biomass, carbon, or annual CO2 value is produced.",
            ],
        }
        _write_json_exclusive(root / "derived" / "geometry.json", geometry)

    after = _originals_snapshot(root)
    originals_unchanged = before == after
    if not originals_unchanged:
        session_reasons.append(
            {
                "code": "originals_changed_during_processing",
                "detail": "session.json or captured artifacts changed during processing",
            }
        )
        validation_status = "REJECTED"

    gate = _l1_gate_assessment(manifest, validation_status, scale_validation)
    report = {
        "format_id": VALIDATION_FORMAT_ID,
        "schema_version": 1,
        "session_id": manifest["session_id"],
        "repeat_group_id": manifest["repeat_group_id"],
        "source_manifest_sha256": source_manifest_sha256,
        "status": validation_status,
        "capabilities": capabilities,
        "units": manifest.get("units"),
        "coordinate_system": manifest.get("coordinate_system"),
        "coverage": aggregate_coverage,
        "quality": {
            "min_confidence": min_confidence,
            "surface_completeness": "unknown",
            "represents_complete_tree_volume": False,
            "discarded_frame_count": len(discarded_frames),
        },
        "session_rejection_reasons": session_reasons,
        "frames": frame_reports,
        "frame_rejection_reasons": frame_reasons,
        "discarded_frames": discarded_frames,
        "scale_references": scale_validation,
        "originals": {
            "before_sha256": before,
            "after_sha256": after,
            "unchanged": originals_unchanged,
        },
        "derived_geometry_path": "derived/geometry.json" if geometry is not None else None,
        "l1_gate": gate,
    }
    _write_json_exclusive(root / "validation" / "report.json", report)
    return report


def compare_sessions(left_root: Path, right_root: Path, output_path: Path) -> Dict[str, Any]:
    """Compare two separately preserved repetitions and write a new report."""

    _ensure_output_absent(output_path)
    left = _load_validation(left_root)
    right = _load_validation(right_root)
    if left["session_id"] == right["session_id"]:
        raise LidarCaptureError("comparison requires two different session IDs")
    if left["repeat_group_id"] != right["repeat_group_id"]:
        raise LidarCaptureError("sessions do not belong to the same repeat_group_id")

    left_coverage = left["coverage"]
    right_coverage = right["coverage"]
    report = {
        "format_id": COMPARISON_FORMAT_ID,
        "schema_version": 1,
        "repeat_group_id": left["repeat_group_id"],
        "sessions": [
            _comparison_summary(left),
            _comparison_summary(right),
        ],
        "deltas": {
            "confidence_accepted_samples": (
                right_coverage["confidence_accepted_samples"]
                - left_coverage["confidence_accepted_samples"]
            ),
            "sample_coverage_fraction": _rounded(
                right_coverage["sample_coverage_fraction"]
                - left_coverage["sample_coverage_fraction"]
            ),
            "frame_coverage_fraction": _rounded(
                right_coverage["frame_coverage_fraction"]
                - left_coverage["frame_coverage_fraction"]
            ),
        },
        "limitations": [
            "Coverage deltas compare recorded samples, not full-tree surface completeness.",
            "This comparison does not estimate volume, biomass, carbon, or annual CO2.",
        ],
    }
    _write_json_exclusive(output_path, report)
    return report


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def _process_frame(root: Path, entry: Any, min_confidence: int) -> FrameResult:
    item = _mapping(entry, "frame entry")
    frame_id = _required_string(item.get("frame_id"), "frame_id")
    timestamp = _finite_number(item.get("timestamp_s"), "timestamp_s")
    metadata_path = _captured_path(root, item.get("metadata_path"), "metadata_path")
    _verify_file_record(
        metadata_path,
        item.get("metadata_size_bytes"),
        item.get("metadata_sha256"),
        "frame metadata",
    )
    metadata = _read_json(metadata_path, f"metadata for {frame_id}")
    if metadata.get("frame_id") != frame_id:
        raise FrameValidationError("frame_id_mismatch", "frame metadata ID does not match session")
    metadata_timestamp = _finite_number(metadata.get("timestamp_s"), "frame timestamp")
    if abs(metadata_timestamp - timestamp) > 1e-9:
        raise FrameValidationError(
            "timestamp_mismatch", "frame metadata timestamp does not match session"
        )

    color = _mapping_or_frame_error(metadata.get("color"), "missing_color", "color")
    planes = color.get("planes")
    if not isinstance(planes, list) or not planes:
        raise FrameValidationError("missing_color", "color.planes must be a non-empty list")
    _positive_integer(color.get("width"), "color.width")
    _positive_integer(color.get("height"), "color.height")
    _required_string(color.get("pixel_format"), "color.pixel_format")
    for plane_index, plane in enumerate(planes):
        plane_item = _mapping_or_frame_error(
            plane, "invalid_color_artifact", f"color.planes[{plane_index}]"
        )
        plane_path = _captured_path(
            root, plane_item.get("path"), f"color.planes[{plane_index}].path"
        )
        _verify_file_record(
            plane_path,
            plane_item.get("size_bytes"),
            plane_item.get("sha256"),
            f"color plane {plane_index}",
        )

    depth = _mapping_or_frame_error(metadata.get("depth"), "missing_depth", "depth")
    confidence = _mapping_or_frame_error(
        metadata.get("confidence"), "missing_confidence", "confidence"
    )
    width = _positive_integer(depth.get("width"), "depth.width")
    height = _positive_integer(depth.get("height"), "depth.height")
    if depth.get("format") != "float32_le" or depth.get("units") != "meter":
        raise FrameValidationError(
            "invalid_depth_contract", "depth must use float32_le values in meters"
        )
    if (
        confidence.get("format") != "uint8"
        or confidence.get("width") != width
        or confidence.get("height") != height
    ):
        raise FrameValidationError(
            "invalid_confidence_contract",
            "confidence must be uint8 and match the depth resolution",
        )
    depth_path = _captured_path(root, depth.get("path"), "depth.path")
    confidence_path = _captured_path(root, confidence.get("path"), "confidence.path")
    _verify_file_record(depth_path, depth.get("size_bytes"), depth.get("sha256"), "depth")
    _verify_file_record(
        confidence_path,
        confidence.get("size_bytes"),
        confidence.get("sha256"),
        "confidence",
    )
    expected_samples = width * height
    depth_bytes = depth_path.read_bytes()
    confidence_bytes = confidence_path.read_bytes()
    if len(depth_bytes) != expected_samples * 4:
        raise FrameValidationError(
            "depth_size_mismatch", "depth byte count does not match its resolution"
        )
    if len(confidence_bytes) != expected_samples:
        raise FrameValidationError(
            "confidence_size_mismatch", "confidence byte count does not match its resolution"
        )
    if any(value > 2 for value in confidence_bytes):
        raise FrameValidationError(
            "invalid_confidence_value", "confidence values must use ARKit levels 0, 1, or 2"
        )

    intrinsics = _mapping_or_frame_error(
        metadata.get("intrinsics"), "missing_intrinsics", "intrinsics"
    )
    if intrinsics.get("model") != "pinhole" or intrinsics.get("reference") != "depth_resolution":
        raise FrameValidationError(
            "invalid_intrinsics_contract",
            "intrinsics must be a pinhole model scaled to depth resolution",
        )
    if intrinsics.get("width") != width or intrinsics.get("height") != height:
        raise FrameValidationError(
            "intrinsics_resolution_mismatch", "intrinsics resolution must match depth"
        )
    pose = _mapping_or_frame_error(metadata.get("pose"), "missing_pose", "pose")
    if (
        pose.get("layout") != "row_major"
        or pose.get("from") != CAMERA_COORDINATE_SYSTEM
        or pose.get("to") != WORLD_COORDINATE_SYSTEM
    ):
        raise FrameValidationError(
            "invalid_pose_contract", "pose coordinate systems or matrix layout are invalid"
        )
    matrix = _matrix4_or_frame_error(pose.get("matrix"))

    depth_values = struct.unpack(f"<{expected_samples}f", depth_bytes)
    points = []
    finite_positive = 0
    confidence_accepted = 0
    confidence_counts = [0, 0, 0]
    for index, depth_m in enumerate(depth_values):
        if not math.isfinite(depth_m) or depth_m <= 0:
            continue
        finite_positive += 1
        confidence_value = confidence_bytes[index]
        confidence_counts[confidence_value] += 1
        if confidence_value < min_confidence:
            continue
        confidence_accepted += 1
        u = index % width
        v = index // width
        camera_point = project_depth_pixel(u, v, depth_m, intrinsics)
        points.append(transform_point(camera_point, matrix))

    flags = []
    if finite_positive < expected_samples:
        flags.append("incomplete_depth_coverage")
    if confidence_accepted < finite_positive:
        flags.append("confidence_filtered_samples")
    return FrameResult(
        frame_id=frame_id,
        timestamp_s=timestamp,
        points=tuple(points),
        total_samples=expected_samples,
        finite_positive_samples=finite_positive,
        confidence_accepted_samples=confidence_accepted,
        confidence_counts=tuple(confidence_counts),
        quality_flags=tuple(flags),
    )


def _session_rejection_reasons(manifest: Mapping[str, Any]) -> List[Dict[str, str]]:
    reasons = []
    if manifest.get("status") != "complete":
        reasons.append(
            {"code": "session_not_complete", "detail": "capture status is not complete"}
        )
    units = manifest.get("units")
    if units != {"depth": "meter", "translation": "meter"}:
        reasons.append(
            {
                "code": "invalid_units",
                "detail": "depth and translation units must both be meter",
            }
        )
    coordinates = manifest.get("coordinate_system")
    if coordinates != {
        "camera": CAMERA_COORDINATE_SYSTEM,
        "world": WORLD_COORDINATE_SYSTEM,
    }:
        reasons.append(
            {
                "code": "invalid_coordinate_system",
                "detail": "camera/world coordinate systems do not match the v1 contract",
            }
        )
    capabilities = manifest.get("capabilities", {})
    if capabilities.get("status") == "supported" and not (
        capabilities.get("scene_depth") is True
        and capabilities.get("lidar_depth_camera") is True
    ):
        reasons.append(
            {
                "code": "inconsistent_capability_report",
                "detail": "supported requires real scene depth and LiDAR camera capability",
            }
        )
    return reasons


def _validate_scale_references(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, list):
        raise LidarCaptureError("scale_references must be a list")
    results = []
    for index, reference in enumerate(raw):
        item = _mapping(reference, f"scale_references[{index}]")
        reference_id = _required_string(item.get("reference_id"), "reference_id")
        expected = _finite_positive(item.get("expected_distance_m"), "expected_distance_m")
        tolerance = _finite_positive(item.get("tolerance_m"), "tolerance_m")
        left = _point3(item.get("point_a_world_m"), "point_a_world_m")
        right = _point3(item.get("point_b_world_m"), "point_b_world_m")
        observed = math.dist(left, right)
        error = abs(observed - expected)
        results.append(
            {
                "reference_id": reference_id,
                "expected_distance_m": expected,
                "observed_distance_m": _rounded(observed),
                "absolute_error_m": _rounded(error),
                "tolerance_m": tolerance,
                "passed": error <= tolerance,
            }
        )
    return {
        "count": len(results),
        "passed_count": sum(item["passed"] for item in results),
        "all_passed": bool(results) and all(item["passed"] for item in results),
        "references": results,
    }


def _l1_gate_assessment(
    manifest: Mapping[str, Any], validation_status: str, scale: Mapping[str, Any]
) -> Dict[str, Any]:
    blockers = []
    if manifest.get("source_type") != "real_device":
        blockers.append("real_device_session_required")
    if validation_status != "PASS":
        blockers.append("complete_capture_package_required")
    if not scale["all_passed"]:
        blockers.append("metric_scale_reference_required")
    if blockers:
        return {
            "status": "PENDING",
            "blockers": blockers,
            "note": "Synthetic or host-only checks cannot validate the L1 field gate.",
        }
    return {
        "status": "EVIDENCE_READY_FOR_MANUAL_REVIEW",
        "blockers": [],
        "note": "The itinerary remains open until device and field evidence are reviewed.",
    }


def _load_validation(root: Path) -> Dict[str, Any]:
    resolved = _resolve_session_root(root)
    report = _read_json(resolved / "validation" / "report.json", "validation report")
    if report.get("format_id") != VALIDATION_FORMAT_ID or report.get("schema_version") != 1:
        raise LidarCaptureError("unsupported validation report format")
    return report


def _comparison_summary(report: Mapping[str, Any]) -> Dict[str, Any]:
    coverage = report["coverage"]
    return {
        "session_id": report["session_id"],
        "status": report["status"],
        "confidence_accepted_samples": coverage["confidence_accepted_samples"],
        "sample_coverage_fraction": coverage["sample_coverage_fraction"],
        "frame_coverage_fraction": coverage["frame_coverage_fraction"],
        "tree_surface_coverage_status": coverage["tree_surface_coverage_status"],
    }


def _validate_manifest_identity(manifest: Mapping[str, Any]) -> None:
    if manifest.get("format_id") != CAPTURE_FORMAT_ID:
        raise LidarCaptureError(f"format_id must be {CAPTURE_FORMAT_ID}")
    if manifest.get("schema_version") != CAPTURE_SCHEMA_VERSION:
        raise LidarCaptureError("unsupported capture schema_version")
    _required_string(manifest.get("session_id"), "session_id")
    _required_string(manifest.get("repeat_group_id"), "repeat_group_id")
    if manifest.get("source_type") not in {"real_device", "recorded_fixture", "synthetic"}:
        raise LidarCaptureError("source_type must be real_device, recorded_fixture, or synthetic")


def _entry_frame_id(entry: Any, index: int) -> str:
    if isinstance(entry, dict) and isinstance(entry.get("frame_id"), str):
        return entry["frame_id"]
    return f"frames[{index}]"


def _coverage(
    total: int,
    finite: int,
    accepted: int,
    confidence_counts: Sequence[int] = (0, 0, 0),
) -> Dict[str, Any]:
    low, medium, high = confidence_counts
    return {
        "depth_samples_total": total,
        "finite_positive_depth_samples": finite,
        "confidence_accepted_samples": accepted,
        "finite_depth_fraction": _fraction(finite, total),
        "sample_coverage_fraction": _fraction(accepted, total),
        "confidence_counts": {"low": low, "medium": medium, "high": high},
        "confidence_fractions_of_finite_depth": {
            "low": _fraction(low, finite),
            "medium": _fraction(medium, finite),
            "high": _fraction(high, finite),
        },
    }


def _empty_coverage() -> Dict[str, Any]:
    return _coverage(0, 0, 0)


def _fraction(numerator: int, denominator: int) -> float:
    return _rounded(numerator / denominator) if denominator else 0.0


def _rounded(value: float) -> float:
    return round(value, 9)


def _originals_snapshot(root: Path) -> str:
    paths = [root / "session.json"]
    captured = root / "captured"
    if captured.exists():
        for path in sorted(captured.rglob("*")):
            if path.is_symlink():
                raise LidarCaptureError("captured artifacts must not contain symlinks")
            if path.is_file():
                paths.append(path)
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(root).as_posix()
        digest.update(f"{relative}\0{path.stat().st_size}\0{sha256_file(path)}\n".encode("utf-8"))
    return digest.hexdigest()


def _resolve_session_root(path: Path) -> Path:
    try:
        root = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise LidarCaptureError(f"session root is unavailable: {exc}") from exc
    if not root.is_dir():
        raise LidarCaptureError("session root must be a directory")
    return root


def _captured_path(root: Path, value: Any, field: str) -> Path:
    relative = _required_string(value, field)
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "captured":
        raise FrameValidationError("unsafe_artifact_path", f"{field} must be under captured/")
    candidate = root / path
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root / "captured")
    except (OSError, ValueError) as exc:
        raise FrameValidationError("missing_artifact", f"{field} is unavailable") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise FrameValidationError("unsafe_artifact_path", f"{field} is not a regular file")
    return resolved


def _verify_file_record(path: Path, size: Any, sha256: Any, label: str) -> None:
    if not isinstance(size, int) or size < 0:
        raise FrameValidationError("invalid_artifact_record", f"{label} size is invalid")
    if not isinstance(sha256, str) or len(sha256) != 64:
        raise FrameValidationError("invalid_artifact_record", f"{label} SHA-256 is invalid")
    if path.stat().st_size != size:
        raise FrameValidationError("artifact_size_mismatch", f"{label} size changed")
    if sha256_file(path) != sha256:
        raise FrameValidationError("artifact_hash_mismatch", f"{label} SHA-256 changed")


def _read_json(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LidarCaptureError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise LidarCaptureError(f"{label} must be a JSON object")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise LidarCaptureError(f"{field} must be an object")
    return value


def _mapping_or_frame_error(value: Any, code: str, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise FrameValidationError(code, f"{field} must be an object")
    return value


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LidarCaptureError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise FrameValidationError("invalid_dimension", f"{field} must be a positive integer")
    return value


def _finite_number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise LidarCaptureError(f"{field} must be finite")
    return float(value)


def _finite_positive(value: Any, field: str) -> float:
    number = _finite_number(value, field)
    if number <= 0:
        raise LidarCaptureError(f"{field} must be positive")
    return number


def _matrix4(value: Any, field: str) -> Tuple[float, ...]:
    if not isinstance(value, list) and not isinstance(value, tuple):
        raise LidarCaptureError(f"{field} must be an array")
    if len(value) != 16:
        raise LidarCaptureError(f"{field} must contain 16 values")
    return tuple(_finite_number(item, field) for item in value)


def _matrix4_or_frame_error(value: Any) -> Tuple[float, ...]:
    try:
        return _matrix4(value, "pose.matrix")
    except LidarCaptureError as exc:
        raise FrameValidationError("invalid_pose", str(exc)) from exc


def _point3(value: Any, field: str) -> Tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise LidarCaptureError(f"{field} must contain three coordinates")
    return tuple(_finite_number(item, field) for item in value)  # type: ignore[return-value]


def _ensure_output_absent(path: Path) -> None:
    if path.exists():
        raise LidarCaptureError(f"refusing to overwrite historical output: {path}")


def _write_json_exclusive(path: Path, value: Any) -> None:
    _write_bytes_exclusive(path, canonical_json(value).encode("utf-8"))


def _write_bytes_exclusive(path: Path, content: bytes) -> None:
    _ensure_output_absent(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
