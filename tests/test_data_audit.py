import binascii
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from olivar_vision.data_audit import (
    AuditError,
    NoDataError,
    audit_dataset_roots,
    canonical_json,
    validate_audit_config,
    write_reports,
)
from olivar_vision.image_fingerprint import decode_image, dhash64


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "roboflow_example"


def manifest(status="APTO_PARA_AUDITORIA"):
    return {
        "schema_version": 1,
        "project": "olivar-vision",
        "updated_at": "2026-09-22",
        "consulted_at": "2026-09-22",
        "sources": [
            {
                "id": SOURCE_ID,
                "name": "Synthetic audit source",
                "publisher": "Tests",
                "source_type": "synthetic_fixture",
                "status": status,
                "status_justification": "Synthetic fixture only.",
                "urls": [{"label": "fixture", "url": "https://example.com/fixture"}],
                "license": {
                    "declared": "CC-BY-4.0",
                    "spdx": "CC-BY-4.0",
                    "status": "VERIFIED_DECLARED",
                    "evidence_urls": ["https://example.com/fixture"],
                    "evidence_summary": "Synthetic fixture license.",
                },
                "access": {
                    "access_status": "SYNTHETIC",
                    "requires_account": "no",
                    "downloaded_in_phase_1": False,
                },
                "declared_content": {
                    "capture_types": ["terrestrial_leaf_closeup"],
                    "task_types": ["classification"],
                    "declared_total_images": 3,
                    "declared_total_images_verified": False,
                    "declared_classes": ["healthy", "spot"],
                    "declared_splits": ["train", "valid", "test"],
                    "geography": "synthetic",
                    "capture_context": "Synthetic test fixture.",
                },
                "quality_and_risk_notes": ["fixture"],
                "relationships": [],
            }
        ],
    }


def config(source_id=SOURCE_ID):
    return {
        "schema_version": 1,
        "audit_id": "synthetic_phase2",
        "audit_date": "2026-09-22",
        "perceptual_hash": {
            "algorithm": "dhash64-luma-nearest-v1",
            "max_hamming_distance": 4,
        },
        "manual_review_sample_size_per_label": 2,
        "sources": [
            {
                "source_id": source_id,
                "version": "fixture-v1",
                "root_env": "OLIVAR_FIXTURE_ROOT",
                "splits": {"train": "train", "valid": "valid", "test": "test"},
                "allowed_labels": ["healthy", "spot"],
                "extensions": [".pgm", ".png"],
                "manual_review_status": "COMPLETED",
                "group_identifiers": {"tree": True, "session": True, "farm": True},
            }
        ],
    }


def pixels_increasing(width=16, height=16):
    return [[x * 16 for x in range(width)] for _ in range(height)]


def pixels_decreasing(width=16, height=16):
    return [[255 - x * 16 for x in range(width)] for _ in range(height)]


def pixels_checker(width=16, height=16):
    return [[255 if (x + y) % 2 else 0 for x in range(width)] for y in range(height)]


def write_pgm(path, pixels):
    path.parent.mkdir(parents=True, exist_ok=True)
    height = len(pixels)
    width = len(pixels[0])
    rows = "\n".join(" ".join(str(value) for value in row) for row in pixels)
    path.write_text(f"P2\n{width} {height}\n255\n{rows}\n", encoding="ascii")


def write_png(path, pixels, compression_level=6):
    path.parent.mkdir(parents=True, exist_ok=True)
    height = len(pixels)
    width = len(pixels[0])
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    signature = b"\x89PNG\r\n\x1a\n"

    def chunk(kind, payload):
        crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.write_bytes(
        signature
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, compression_level))
        + chunk(b"IEND", b"")
    )


def create_clean_dataset(root):
    write_pgm(root / "train" / "healthy" / "increasing.pgm", pixels_increasing())
    write_pgm(root / "valid" / "spot" / "decreasing.pgm", pixels_decreasing())
    write_pgm(root / "test" / "healthy" / "checker.pgm", pixels_checker())


class DataAuditTests(unittest.TestCase):
    def setUp(self):
        self.raw_manifest = manifest()
        self.audit_config = validate_audit_config(config(), self.raw_manifest)

    def audit(self, root):
        return audit_dataset_roots(
            self.audit_config,
            self.raw_manifest,
            {SOURCE_ID: Path(root)},
            config_sha256="config-hash",
            manifest_sha256="manifest-hash",
        )

    def test_clean_inventory_is_deterministic_and_identifies_source_and_split(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_clean_dataset(root)

            first = self.audit(root)
            second = self.audit(root)

            self.assertEqual(canonical_json(first), canonical_json(second))
            self.assertEqual(first["result"]["audit_status"], "PASS")
            self.assertEqual(first["summary"]["valid_image_count"], 3)
            self.assertEqual(first["files"][0]["source_id"], SOURCE_ID)
            self.assertEqual({item["split"] for item in first["files"]}, {"train", "valid", "test"})
            self.assertTrue(first["sources"][0]["input_integrity"]["unchanged"])
            self.assertEqual(len(first["result"]["split_manifest_sha256"]), 64)
            self.assertIn("healthy", first["manual_review_samples"][SOURCE_ID])

    def test_corrupt_empty_unknown_label_and_unexpected_format_are_blocking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_pgm(root / "train" / "healthy" / "valid.pgm", pixels_increasing())
            corrupt = root / "valid" / "healthy" / "corrupt.png"
            corrupt.parent.mkdir(parents=True)
            corrupt.write_bytes(b"not a png")
            empty = root / "test" / "healthy" / "empty.pgm"
            empty.parent.mkdir(parents=True)
            empty.write_bytes(b"")
            write_pgm(root / "test" / "mystery" / "unknown.pgm", pixels_checker())
            note = root / "test" / "healthy" / "note.txt"
            note.write_text("not an image", encoding="utf-8")

            report = self.audit(root)

            codes = {issue["code"] for issue in report["issues"]}
            self.assertTrue(
                {"corrupt_or_unsupported_image", "empty_file", "unknown_label", "unexpected_format"}
                <= codes
            )
            self.assertEqual(report["result"]["audit_status"], "FAIL")

    def test_exact_duplicate_across_splits_blocks_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pixels = pixels_increasing()
            write_pgm(root / "train" / "healthy" / "first.pgm", pixels)
            write_pgm(root / "test" / "healthy" / "copy.pgm", pixels)
            (root / "valid").mkdir()

            report = self.audit(root)

            self.assertEqual(report["summary"]["exact_duplicate_group_count"], 1)
            self.assertTrue(report["result"]["split_leakage_detected"])
            self.assertIn("exact_duplicate_leakage", {item["code"] for item in report["issues"]})

    def test_same_pixels_reencoded_are_near_duplicates_not_exact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pixels = pixels_checker()
            write_png(root / "train" / "healthy" / "compression-1.png", pixels, compression_level=1)
            write_png(root / "test" / "healthy" / "compression-9.png", pixels, compression_level=9)
            (root / "valid").mkdir()

            report = self.audit(root)

            self.assertEqual(report["summary"]["exact_duplicate_group_count"], 0)
            self.assertEqual(report["summary"]["near_duplicate_pair_count"], 1)
            self.assertEqual(report["duplicates"]["near_pairs"][0]["distance"], 0)
            self.assertTrue(report["result"]["split_leakage_detected"])

    def test_different_existing_report_is_not_overwritten_without_opt_in(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "dataset"
            create_clean_dataset(root)
            report = self.audit(root)
            json_path = Path(temp_dir) / "audit.json"
            markdown_path = Path(temp_dir) / "audit.md"
            json_path.write_text("historical\n", encoding="utf-8")

            with self.assertRaisesRegex(AuditError, "refusing to overwrite"):
                write_reports(report, json_path, markdown_path)

            self.assertEqual(json_path.read_text(encoding="utf-8"), "historical\n")
            self.assertFalse(markdown_path.exists())

    def test_symlink_outside_root_is_reported_without_reading_target(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(temp_dir)
            for split in ("train", "valid", "test"):
                (root / split / "healthy").mkdir(parents=True)
            outside = Path(outside_dir) / "private.pgm"
            write_pgm(outside, pixels_increasing())
            (root / "train" / "healthy" / "linked.pgm").symlink_to(outside)

            report = self.audit(root)

            self.assertIn("unsafe_path", {item["code"] for item in report["issues"]})
            self.assertNotIn(str(outside), canonical_json(report))

    def test_empty_dataset_raises_without_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for split in ("train", "valid", "test"):
                (root / split).mkdir()

            with self.assertRaisesRegex(NoDataError, "no local files"):
                self.audit(root)

    def test_config_rejects_path_traversal_and_non_auditable_source(self):
        unsafe = config()
        unsafe["sources"][0]["splits"]["train"] = "../outside"
        with self.assertRaisesRegex(AuditError, "unsafe relative path"):
            validate_audit_config(unsafe, self.raw_manifest)

        blocked_manifest = manifest(status="PENDIENTE_DE_LICENCIA")
        with self.assertRaisesRegex(AuditError, "not APTO_PARA_AUDITORIA"):
            validate_audit_config(config(), blocked_manifest)

    def test_cli_without_authorized_root_returns_two_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_json = Path(temp_dir) / "audit.json"
            output_md = Path(temp_dir) / "audit.md"
            env = dict(os.environ)
            env.pop("OLIVAR_ROBOFLOW_ROOT", None)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/data_audit.py",
                    "--output-json",
                    str(output_json),
                    "--output-markdown",
                    str(output_md),
                ],
                cwd=ROOT,
                env={**env, "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("missing authorized local dataset root", result.stderr)
            self.assertFalse(output_json.exists())
            self.assertFalse(output_md.exists())

    def test_cli_audits_synthetic_input_and_writes_private_reports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            dataset = base / "dataset"
            for split, pixels in (
                ("train", pixels_increasing()),
                ("valid", pixels_decreasing()),
                ("test", pixels_checker()),
            ):
                write_pgm(dataset / split / "healthy" / f"{split}.pgm", pixels)
            output_json = base / "audit.json"
            output_md = base / "audit.md"
            env = {
                **os.environ,
                "PYTHONPATH": "src",
                "PYTHONDONTWRITEBYTECODE": "1",
                "OLIVAR_ROBOFLOW_ROOT": str(dataset),
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/data_audit.py",
                    "--output-json",
                    str(output_json),
                    "--output-markdown",
                    str(output_md),
                ],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["valid_image_count"], 3)
            self.assertNotIn(str(dataset), output_json.read_text(encoding="utf-8"))
            self.assertTrue(output_md.exists())

    def test_cli_returns_three_and_keeps_report_when_split_leaks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            dataset = base / "dataset"
            pixels = pixels_increasing()
            write_pgm(dataset / "train" / "healthy" / "first.pgm", pixels)
            write_pgm(dataset / "test" / "healthy" / "copy.pgm", pixels)
            (dataset / "valid").mkdir()
            output_json = base / "audit.json"
            output_md = base / "audit.md"
            env = {
                **os.environ,
                "PYTHONPATH": "src",
                "PYTHONDONTWRITEBYTECODE": "1",
                "OLIVAR_ROBOFLOW_ROOT": str(dataset),
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/data_audit.py",
                    "--output-json",
                    str(output_json),
                    "--output-markdown",
                    str(output_md),
                ],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 3)
            self.assertTrue(output_json.exists())
            report = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertTrue(report["result"]["split_leakage_detected"])

    @unittest.skipUnless(shutil.which("sips"), "macOS sips is unavailable")
    def test_macos_sips_decodes_a_reencoded_jpeg_without_touching_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            jpeg = root / "converted.jpg"
            write_png(source, pixels_increasing())
            converted = subprocess.run(
                ["sips", "-s", "format", "jpeg", str(source), "--out", str(jpeg)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(converted.returncode, 0, converted.stderr)
            before = jpeg.read_bytes()

            decoded = decode_image(jpeg)

            self.assertEqual(decoded.image_format, "JPEG")
            self.assertEqual((decoded.width, decoded.height), (16, 16))
            self.assertEqual(len(dhash64(decoded)), 16)
            self.assertEqual(jpeg.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
