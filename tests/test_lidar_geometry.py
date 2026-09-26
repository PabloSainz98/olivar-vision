import hashlib
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path

from olivar_vision.lidar_geometry import (
    LidarGeometryError,
    compare_tree_geometry_reports,
    measure_session_geometry,
    measure_tree_geometry,
)


def known_tree_points(radius=0.2, height=3.0):
    points = []
    for index in range(72):
        angle = 2.0 * math.pi * index / 72.0
        points.append((radius * math.cos(angle), 0.3, radius * math.sin(angle)))
    points.extend(
        [
            (-1.0, 1.0, -0.75),
            (1.0, 1.0, -0.75),
            (-1.0, 1.0, 0.75),
            (1.0, 1.0, 0.75),
            (-0.8, height, -0.6),
            (0.8, height, 0.6),
            (0.0, 0.0, 0.0),
        ]
    )
    return points


class LidarGeometryTests(unittest.TestCase):
    def test_known_shape_reports_height_crown_and_basal_diameter(self):
        report = measure_tree_geometry(
            known_tree_points(),
            tree_isolated=True,
            sample_coverage_fraction=0.95,
            vertical_coverage_fraction=0.9,
            ground_y_m=0.0,
        )

        self.assertEqual(report["status"], "AVAILABLE")
        self.assertEqual(report["units"], "meter")
        self.assertEqual(report["coordinate_system"], "arkit_world_right_handed_y_up")
        self.assertAlmostEqual(report["measurements"]["height_m"], 3.0, places=6)
        self.assertAlmostEqual(report["measurements"]["crown_span_x_m"], 2.0, places=6)
        self.assertAlmostEqual(report["measurements"]["crown_span_z_m"], 1.5, places=6)
        self.assertAlmostEqual(
            report["measurements"]["basal_diameter"]["diameter_m"],
            0.4,
            places=6,
        )
        self.assertFalse(report["l2_gate"]["validated"])
        self.assertFalse(report["represents_complete_tree_volume"])

    def test_incomplete_coverage_does_not_publish_tree_measurements(self):
        report = measure_tree_geometry(
            known_tree_points(),
            tree_isolated=True,
            sample_coverage_fraction=0.4,
            vertical_coverage_fraction=0.7,
            ground_y_m=0.0,
        )

        self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
        self.assertIsNone(report["measurements"])
        self.assertIsNotNone(report["observed_bounds"])
        codes = {reason["code"] for reason in report["availability"]["reasons"]}
        self.assertIn("insufficient_sample_coverage", codes)
        self.assertIn("insufficient_vertical_coverage", codes)

    def test_surrounding_scene_is_not_presented_as_tree_geometry(self):
        report = measure_tree_geometry(
            known_tree_points(),
            tree_isolated=False,
            sample_coverage_fraction=1.0,
            vertical_coverage_fraction=1.0,
            ground_y_m=0.0,
        )

        self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
        self.assertIsNone(report["measurements"])
        self.assertIn(
            "tree_not_isolated",
            {reason["code"] for reason in report["availability"]["reasons"]},
        )

    def test_missing_ground_reference_blocks_height_and_diameter(self):
        report = measure_tree_geometry(
            known_tree_points(),
            tree_isolated=True,
            sample_coverage_fraction=1.0,
            vertical_coverage_fraction=1.0,
            ground_y_m=None,
        )

        self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
        self.assertIn(
            "missing_ground_reference",
            {reason["code"] for reason in report["availability"]["reasons"]},
        )

    def test_wrong_units_or_coordinates_are_rejected(self):
        report = measure_tree_geometry(
            known_tree_points(),
            tree_isolated=True,
            sample_coverage_fraction=1.0,
            vertical_coverage_fraction=1.0,
            ground_y_m=0.0,
            units="centimeter",
            coordinate_system="unknown",
        )

        codes = {reason["code"] for reason in report["availability"]["reasons"]}
        self.assertIn("unsupported_units", codes)
        self.assertIn("unsupported_coordinate_system", codes)

    def test_partial_basal_arc_fails_diameter_quality_gate(self):
        points = [
            (0.2 * math.cos(index * math.pi / 36.0), 0.3, 0.2 * math.sin(index * math.pi / 36.0))
            for index in range(19)
        ]
        points.extend([(0.0, 0.0, 0.0), (-1.0, 2.0, -1.0), (1.0, 3.0, 1.0)])

        report = measure_tree_geometry(
            points,
            tree_isolated=True,
            sample_coverage_fraction=1.0,
            vertical_coverage_fraction=1.0,
            ground_y_m=0.0,
        )

        self.assertEqual(report["status"], "PARTIAL")
        basal = report["measurements"]["basal_diameter"]
        self.assertEqual(basal["status"], "ESTIMATION_NOT_AVAILABLE")
        self.assertIn(
            "insufficient_basal_angular_coverage",
            {reason["code"] for reason in basal["reasons"]},
        )

    def test_non_finite_points_are_rejected(self):
        with self.assertRaises(LidarGeometryError):
            measure_tree_geometry(
                [(0.0, float("nan"), 0.0)] * 12,
                tree_isolated=True,
                sample_coverage_fraction=1.0,
                vertical_coverage_fraction=1.0,
                ground_y_m=0.0,
            )

    def test_rejected_l1_session_cannot_publish_tree_measurements(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "derived").mkdir()
            (root / "validation").mkdir()
            point_bytes = b"".join(struct.pack("<fff", *point) for point in known_tree_points())
            point_path = root / "derived" / "points.f32le"
            point_path.write_bytes(point_bytes)
            geometry_path = root / "derived" / "geometry.json"
            geometry_path.write_text(
                json.dumps(
                    {
                        "format_id": "olivar-lidar-geometry",
                        "schema_version": 1,
                        "point_cloud": {
                            "path": "derived/points.f32le",
                            "format": "float32_le_xyz",
                            "coordinate_system": "arkit_world_right_handed_y_up",
                            "units": "meter",
                            "point_count": len(known_tree_points()),
                            "sha256": hashlib.sha256(point_bytes).hexdigest(),
                        }
                    }
                ),
                encoding="utf-8",
            )
            (root / "validation" / "report.json").write_text(
                json.dumps(
                    {
                        "format_id": "olivar-lidar-validation",
                        "schema_version": 1,
                        "session_id": "rejected-session",
                        "status": "REJECTED",
                        "coverage": {"sample_coverage_fraction": 1.0},
                    }
                ),
                encoding="utf-8",
            )

            report = measure_session_geometry(
                root,
                root / "derived" / "tree-measurement.json",
                tree_isolated=True,
                vertical_coverage_fraction=1.0,
                ground_y_m=0.0,
            )

            self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
            self.assertIsNone(report["measurements"])
            self.assertIn(
                "source_l1_validation_not_passed",
                {reason["code"] for reason in report["availability"]["reasons"]},
            )
            with self.assertRaises(LidarGeometryError):
                measure_session_geometry(
                    root,
                    root / "derived" / "tree-measurement.json",
                    tree_isolated=True,
                    vertical_coverage_fraction=1.0,
                    ground_y_m=0.0,
                )

    def test_session_geometry_rejects_point_path_outside_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "derived").mkdir()
            (root / "validation").mkdir()
            (root / "derived" / "geometry.json").write_text(
                json.dumps(
                    {
                        "format_id": "olivar-lidar-geometry",
                        "schema_version": 1,
                        "point_cloud": {
                            "path": "../outside.f32le",
                            "format": "float32_le_xyz",
                            "coordinate_system": "arkit_world_right_handed_y_up",
                            "units": "meter",
                            "point_count": 1,
                            "sha256": "0" * 64,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "validation" / "report.json").write_text(
                json.dumps(
                    {
                        "format_id": "olivar-lidar-validation",
                        "schema_version": 1,
                        "session_id": "unsafe-session",
                        "status": "PASS",
                        "coverage": {"sample_coverage_fraction": 1.0},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(LidarGeometryError):
                measure_session_geometry(
                    root,
                    root / "derived" / "tree-measurement.json",
                    tree_isolated=True,
                    vertical_coverage_fraction=1.0,
                    ground_y_m=0.0,
                )

    def test_geometry_repetitions_compare_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_path = root / "left.json"
            right_path = root / "right.json"
            output_path = root / "comparison.json"

            def report(session_id, height, diameter):
                return {
                    "format_id": "olivar-tree-geometry-measurement",
                    "schema_version": 1,
                    "status": "AVAILABLE",
                    "units": "meter",
                    "coordinate_system": "arkit_world_right_handed_y_up",
                    "source": {
                        "session_id": session_id,
                        "repeat_group_id": "tree-7-repeat",
                    },
                    "quality": {
                        "sample_coverage_fraction": 0.9,
                        "vertical_coverage_fraction": 0.9,
                    },
                    "measurements": {
                        "height_m": height,
                        "crown_span_x_m": 2.0,
                        "crown_span_z_m": 1.5,
                        "basal_diameter": {"diameter_m": diameter},
                    },
                }

            left_path.write_text(json.dumps(report("session-a", 3.0, 0.4)), encoding="utf-8")
            right_path.write_text(json.dumps(report("session-b", 3.1, 0.42)), encoding="utf-8")

            comparison = compare_tree_geometry_reports(left_path, right_path, output_path)

            self.assertEqual(comparison["status"], "COMPARISON_AVAILABLE")
            self.assertAlmostEqual(
                comparison["measurements"]["height_m"]["difference"],
                0.1,
                places=6,
            )
            self.assertAlmostEqual(
                comparison["measurements"]["basal_diameter_m"]["difference"],
                0.02,
                places=6,
            )
            self.assertFalse(comparison["l2_gate"]["validated"])
            with self.assertRaises(LidarGeometryError):
                compare_tree_geometry_reports(left_path, right_path, output_path)


if __name__ == "__main__":
    unittest.main()
