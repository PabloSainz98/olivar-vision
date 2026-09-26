import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from olivar_vision.lidar_capture import (
    CAMERA_COORDINATE_SYSTEM,
    WORLD_COORDINATE_SYSTEM,
    LidarCaptureError,
    compare_sessions,
    process_session,
    project_depth_pixel,
    transform_point,
)
from olivar_vision.lidar_geometry import measure_session_geometry


IDENTITY = [
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
]
ROOT = Path(__file__).resolve().parents[1]


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def write_bytes(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return {
        "path": relative,
        "size_bytes": len(value),
        "sha256": sha256(value),
    }


def write_json(root, relative, value):
    content = (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()
    return write_bytes(root, relative, content)


def create_session(
    root,
    session_id="session-001",
    repeat_group_id="tree-7-repeat",
    depths=(1.0, 1.0, 1.0, 1.0),
    confidences=(2, 2, 2, 2),
    missing_field=None,
    capability_status="supported",
    source_type="synthetic",
    scale_references=None,
):
    root.mkdir(parents=True)
    frame_id = "frame-000001"
    frame_root = f"captured/{frame_id}"
    color = write_bytes(root, f"{frame_root}/color-plane-0.u8", b"rgb-original")
    depth_data = struct.pack(f"<{len(depths)}f", *depths)
    depth = write_bytes(root, f"{frame_root}/depth.f32le", depth_data)
    confidence = write_bytes(root, f"{frame_root}/confidence.u8", bytes(confidences))
    metadata = {
        "frame_id": frame_id,
        "timestamp_s": 0.25,
        "color": {
            "width": 2,
            "height": 2,
            "pixel_format": "420f",
            "planes": [
                {
                    **color,
                    "format": "raw_bytes",
                    "bytes_per_row": len(b"rgb-original"),
                    "height": 1,
                }
            ],
        },
        "depth": {
            **depth,
            "format": "float32_le",
            "units": "meter",
            "width": 2,
            "height": 2,
        },
        "confidence": {
            **confidence,
            "format": "uint8",
            "levels": {"0": "low", "1": "medium", "2": "high"},
            "width": 2,
            "height": 2,
        },
        "intrinsics": {
            "model": "pinhole",
            "reference": "depth_resolution",
            "width": 2,
            "height": 2,
            "fx": 1.0,
            "fy": 1.0,
            "cx": 0.0,
            "cy": 0.0,
        },
        "pose": {
            "layout": "row_major",
            "from": CAMERA_COORDINATE_SYSTEM,
            "to": WORLD_COORDINATE_SYSTEM,
            "matrix": IDENTITY,
        },
        "tracking_state": "normal",
    }
    if missing_field is not None:
        metadata.pop(missing_field)
    metadata_record = write_json(root, f"{frame_root}/frame.json", metadata)
    supported = capability_status == "supported"
    manifest = {
        "format_id": "olivar-lidar-capture",
        "schema_version": 1,
        "session_id": session_id,
        "repeat_group_id": repeat_group_id,
        "source_type": source_type,
        "status": "complete",
        "created_at": "2026-09-26T10:00:00Z",
        "capture": {
            "tree_id": "tree-7",
            "operator_id": "operator-local",
            "site_id": "plot-a",
            "protocol_id": "lidar-carbon-l1-v1",
        },
        "device": {
            "model_identifier": "synthetic-fixture",
            "os_name": "test",
            "os_version": "1",
        },
        "capabilities": {
            "status": capability_status,
            "scene_depth": supported,
            "smoothed_scene_depth": supported,
            "scene_mesh": supported,
            "lidar_depth_camera": supported,
            "reason": None if supported else "ARKit scene depth is unavailable",
        },
        "units": {"depth": "meter", "translation": "meter"},
        "coordinate_system": {
            "camera": CAMERA_COORDINATE_SYSTEM,
            "world": WORLD_COORDINATE_SYSTEM,
        },
        "frames": [
            {
                "frame_id": frame_id,
                "timestamp_s": 0.25,
                "metadata_path": metadata_record["path"],
                "metadata_size_bytes": metadata_record["size_bytes"],
                "metadata_sha256": metadata_record["sha256"],
            }
        ],
        "discarded_frames": [],
        "scale_references": scale_references or [],
    }
    write_json(root, "session.json", manifest)
    return manifest


class LidarCaptureTests(unittest.TestCase):
    def test_projection_and_transform_use_documented_coordinates_and_meters(self):
        point = project_depth_pixel(
            3,
            4,
            2.0,
            {"fx": 2.0, "fy": 4.0, "cx": 1.0, "cy": 2.0},
        )
        self.assertEqual(point, (2.0, 1.0, 2.0))
        translated = IDENTITY.copy()
        translated[3] = 10.0
        translated[7] = -2.0
        self.assertEqual(transform_point(point, translated), (12.0, -1.0, 2.0))

    def test_valid_session_preserves_originals_and_separates_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(root)
            original_depth = (root / "captured/frame-000001/depth.f32le").read_bytes()

            report = process_session(root, min_confidence=1)

            self.assertEqual(report["status"], "PASS")
            self.assertTrue(report["originals"]["unchanged"])
            self.assertEqual(report["coverage"]["sample_coverage_fraction"], 1.0)
            self.assertEqual(report["coverage"]["confidence_counts"]["high"], 4)
            self.assertEqual(report["coverage"]["tree_surface_coverage_status"], "unknown")
            geometry = json.loads((root / "derived/geometry.json").read_text())
            self.assertEqual(geometry["point_cloud"]["point_count"], 4)
            self.assertFalse(geometry["represents_complete_tree_volume"])
            self.assertTrue((root / "validation/report.json").exists())
            self.assertEqual(
                (root / "captured/frame-000001/depth.f32le").read_bytes(),
                original_depth,
            )

    def test_incomplete_depth_reports_partial_sample_coverage_not_tree_volume(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(root, depths=(1.0, math.nan, 0.0, 2.0))

            report = process_session(root)

            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["coverage"]["finite_depth_fraction"], 0.5)
            self.assertEqual(report["coverage"]["sample_coverage_fraction"], 0.5)
            self.assertIn(
                "incomplete_depth_coverage",
                report["frames"][0]["quality_flags"],
            )
            self.assertFalse(report["quality"]["represents_complete_tree_volume"])

    def test_insufficient_confidence_rejects_frame_and_writes_no_geometry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(root, confidences=(0, 0, 0, 0))

            report = process_session(root, min_confidence=2)

            self.assertEqual(report["status"], "REJECTED")
            self.assertEqual(report["frames"][0]["status"], "REJECTED")
            self.assertEqual(
                report["frames"][0]["rejection_reasons"][0]["code"],
                "insufficient_confidence",
            )
            self.assertFalse((root / "derived/geometry.json").exists())

    def test_missing_intrinsics_and_pose_are_explicit_rejections(self):
        for field, expected_code in (
            ("color", "missing_color"),
            ("intrinsics", "missing_intrinsics"),
            ("pose", "missing_pose"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir) / "capture"
                create_session(root, missing_field=field)

                report = process_session(root)

                self.assertEqual(report["status"], "REJECTED")
                self.assertEqual(
                    report["frame_rejection_reasons"][0]["code"],
                    expected_code,
                )

    def test_unsupported_device_is_blocked_without_simulated_geometry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(root, capability_status="unsupported")

            report = process_session(root)

            self.assertEqual(report["status"], "BLOCKED_UNSUPPORTED_DEVICE")
            self.assertIn(
                "unsupported_device",
                {item["code"] for item in report["session_rejection_reasons"]},
            )
            self.assertFalse((root / "derived/geometry.json").exists())

    def test_invalid_units_and_coordinates_are_rejected(self):
        for mutation, expected_code in (
            (lambda item: item.update(units={"depth": "millimeter", "translation": "meter"}), "invalid_units"),
            (lambda item: item.update(coordinate_system={"camera": "unknown", "world": "unknown"}), "invalid_coordinate_system"),
        ):
            with self.subTest(expected_code=expected_code), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir) / "capture"
                create_session(root)
                manifest = json.loads((root / "session.json").read_text())
                mutation(manifest)
                write_json_content = json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
                (root / "session.json").write_text(write_json_content, encoding="utf-8")

                report = process_session(root)

                self.assertEqual(report["status"], "REJECTED")
                self.assertIn(
                    expected_code,
                    {item["code"] for item in report["session_rejection_reasons"]},
                )

    def test_changed_original_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(root)
            (root / "captured/frame-000001/depth.f32le").write_bytes(struct.pack("<4f", 9, 9, 9, 9))

            report = process_session(root)

            self.assertEqual(report["status"], "REJECTED")
            self.assertEqual(
                report["frame_rejection_reasons"][0]["code"],
                "artifact_hash_mismatch",
            )

    def test_repeated_sessions_compare_without_overwriting_either_capture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            first = base / "capture-a"
            second = base / "capture-b"
            create_session(first, session_id="session-a")
            create_session(
                second,
                session_id="session-b",
                depths=(1.0, 1.0, 0.0, 0.0),
            )
            process_session(first)
            process_session(second)
            first_manifest = (first / "session.json").read_bytes()
            second_manifest = (second / "session.json").read_bytes()
            output = base / "comparisons" / "a-vs-b.json"

            comparison = compare_sessions(first, second, output)

            self.assertEqual(comparison["deltas"]["confidence_accepted_samples"], -2)
            self.assertEqual(comparison["deltas"]["sample_coverage_fraction"], -0.5)
            self.assertEqual((first / "session.json").read_bytes(), first_manifest)
            self.assertEqual((second / "session.json").read_bytes(), second_manifest)
            with self.assertRaisesRegex(LidarCaptureError, "refusing to overwrite"):
                compare_sessions(first, second, output)

    def test_processing_refuses_to_overwrite_historical_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(root)
            process_session(root)

            with self.assertRaisesRegex(LidarCaptureError, "refusing to overwrite"):
                process_session(root)

    def test_l1_output_uses_the_geometry_reader_contract_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(root)
            process_session(root)

            report = measure_session_geometry(
                root,
                root / "derived" / "tree-measurement.json",
                tree_isolated=True,
                vertical_coverage_fraction=1.0,
                ground_y_m=0.0,
            )

            self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
            self.assertIn(
                "insufficient_points",
                {reason["code"] for reason in report["availability"]["reasons"]},
            )
            self.assertEqual(report["source"]["l1_validation_status"], "PASS")

    def test_synthetic_scale_reference_does_not_close_real_device_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(
                root,
                scale_references=[
                    {
                        "reference_id": "bar-1m",
                        "expected_distance_m": 1.0,
                        "point_a_world_m": [0.0, 0.0, 0.0],
                        "point_b_world_m": [1.0, 0.0, 0.0],
                        "tolerance_m": 0.01,
                    }
                ],
            )

            report = process_session(root)

            self.assertTrue(report["scale_references"]["all_passed"])
            self.assertEqual(report["l1_gate"]["status"], "PENDING")
            self.assertIn("real_device_session_required", report["l1_gate"]["blockers"])

    def test_cli_processes_a_private_session_and_reports_gate_separately(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "capture"
            create_session(root)
            result = subprocess.run(
                [sys.executable, "scripts/lidar_session.py", "process", str(root)],
                cwd=ROOT,
                env={
                    **os.environ,
                    "PYTHONPATH": "src",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["l1_gate"], "PENDING")
            self.assertTrue((root / "validation/report.json").exists())


if __name__ == "__main__":
    unittest.main()
