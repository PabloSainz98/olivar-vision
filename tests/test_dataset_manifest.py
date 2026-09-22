import copy
import unittest

from olivar_vision.dataset_manifest import ManifestError, validate_manifest


def valid_manifest():
    return {
        "schema_version": 1,
        "project": "olivar-vision",
        "updated_at": "2026-09-22",
        "consulted_at": "2026-09-22",
        "sources": [
            {
                "id": "roboflow_example",
                "name": "Example",
                "publisher": "Publisher",
                "source_type": "roboflow_universe_dataset",
                "status": "APTO_PARA_AUDITORIA",
                "status_justification": "License is declared and evidence is linked.",
                "urls": [
                    {
                        "label": "dataset",
                        "url": "https://example.com/dataset",
                    }
                ],
                "license": {
                    "declared": "CC-BY-4.0",
                    "spdx": "CC-BY-4.0",
                    "status": "VERIFIED_DECLARED",
                    "evidence_urls": [
                        "https://example.com/dataset"
                    ],
                    "evidence_summary": "The page declares the license.",
                },
                "access": {
                    "access_status": "PUBLIC_METADATA_VISIBLE",
                    "requires_account": "unknown",
                    "downloaded_in_phase_1": False,
                },
                "declared_content": {
                    "capture_types": [
                        "terrestrial_leaf_closeup"
                    ],
                    "task_types": [
                        "classification"
                    ],
                    "declared_total_images": 10,
                    "declared_total_images_verified": False,
                    "declared_classes": [
                        "healthy"
                    ],
                    "declared_splits": [
                        "train"
                    ],
                    "geography": "unknown",
                    "capture_context": "Synthetic test fixture.",
                },
                "quality_and_risk_notes": [
                    "fixture"
                ],
                "relationships": [],
            }
        ],
    }


class DatasetManifestValidationTests(unittest.TestCase):
    def test_valid_manifest_passes(self):
        result = validate_manifest(valid_manifest())

        self.assertEqual(result.source_count, 1)
        self.assertEqual(result.apt_for_audit_count, 1)

    def test_apt_source_requires_verified_license(self):
        manifest = valid_manifest()
        manifest["sources"][0]["license"]["status"] = "MISSING_OR_UNVERIFIED"

        with self.assertRaisesRegex(ManifestError, "license is not verified"):
            validate_manifest(manifest)

    def test_duplicate_source_id_fails(self):
        manifest = valid_manifest()
        manifest["sources"].append(copy.deepcopy(manifest["sources"][0]))

        with self.assertRaisesRegex(ManifestError, "duplicate source id"):
            validate_manifest(manifest)

    def test_invalid_url_fails(self):
        manifest = valid_manifest()
        manifest["sources"][0]["urls"][0]["url"] = "not-a-url"

        with self.assertRaisesRegex(ManifestError, "not a valid"):
            validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()

