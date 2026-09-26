import math
import unittest

from olivar_vision.biomass_carbon import (
    BiomassCarbonError,
    estimate_biomass_carbon,
)


def valid_input():
    return {
        "format_id": "olivar-biomass-carbon-input",
        "schema_version": 1,
        "tree_id": "tree-001",
        "measurement": {
            "basal_diameter_cm": 20.0,
            "measurement_height_m": 0.3,
            "diameter_uncertainty_cm": 0.5,
            "source": "manual_tape",
        },
        "domain": {
            "cultivar": "Leccino",
            "training_system": "vase",
            "water_regime": "traditional_rainfed",
            "orchard_density_trees_per_ha": 150,
        },
        "carbon_fraction": {
            "value": 0.47,
            "source": "Torrus-Castillo et al. 2026; explicit proxy for synthetic test",
            "is_proxy": True,
        },
    }


class BiomassCarbonTests(unittest.TestCase):
    def test_valid_manual_input_reports_separate_stocks(self):
        report = estimate_biomass_carbon(valid_input())

        expected_biomass = 0.0538 * math.pow(20.0, 2.4208)
        self.assertEqual(report["status"], "EXPERIMENTAL_ESTIMATE")
        self.assertAlmostEqual(
            report["result"]["modeled_biomass"]["aboveground_dry_biomass_kg"],
            expected_biomass,
            places=6,
        )
        self.assertAlmostEqual(
            report["result"]["stored_carbon"]["kg_c"],
            expected_biomass * 0.47,
            places=6,
        )
        self.assertAlmostEqual(
            report["result"]["stored_co2_equivalent"]["kg_co2e"],
            expected_biomass * 0.47 * 44.0 / 12.0,
            places=6,
        )
        self.assertFalse(report["l3_gate"]["validated"])
        self.assertEqual(report["input_parameters"]["domain"]["cultivar"], "Leccino")
        sensitivity = report["result"]["modeled_biomass"]["sensitivity_from_diameter_only_kg"]
        self.assertEqual(sensitivity["diameter_range_cm"], [19.5, 20.5])
        self.assertIn("not a confidence interval", sensitivity["interpretation"])
        self.assertIsNotNone(
            report["result"]["stored_carbon"]["sensitivity_from_diameter_only_kg_c"]
        )
        self.assertIsNotNone(
            report["result"]["stored_co2_equivalent"][
                "sensitivity_from_diameter_only_kg_co2e"
            ]
        )

    def test_outside_published_diameter_domain_is_blocked(self):
        payload = valid_input()
        payload["measurement"]["basal_diameter_cm"] = 46.0

        report = estimate_biomass_carbon(payload)

        self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
        self.assertIsNone(report["result"])
        self.assertIn(
            "diameter_outside_model_domain",
            {reason["code"] for reason in report["availability"]["reasons"]},
        )

    def test_non_leccino_or_wrong_management_is_blocked(self):
        payload = valid_input()
        payload["domain"].update(
            {
                "cultivar": "Picual",
                "training_system": "hedgerow",
                "water_regime": "irrigated",
                "orchard_density_trees_per_ha": 1000,
            }
        )

        report = estimate_biomass_carbon(payload)

        codes = {reason["code"] for reason in report["availability"]["reasons"]}
        self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
        self.assertTrue(
            {
                "unsupported_cultivar",
                "unsupported_training_system",
                "unsupported_water_regime",
                "density_outside_model_domain",
            }.issubset(codes)
        )

    def test_lidar_diameter_requires_real_device_validation(self):
        payload = valid_input()
        payload["measurement"]["source"] = "lidar"
        payload["measurement"]["validation_status"] = "SYNTHETIC_ONLY"

        report = estimate_biomass_carbon(payload)

        self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
        self.assertIn(
            "lidar_diameter_not_validated",
            {reason["code"] for reason in report["availability"]["reasons"]},
        )

    def test_missing_carbon_fraction_source_is_blocked(self):
        payload = valid_input()
        payload["carbon_fraction"]["source"] = ""

        report = estimate_biomass_carbon(payload)

        self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
        self.assertIn(
            "missing_carbon_fraction_source",
            {reason["code"] for reason in report["availability"]["reasons"]},
        )

    def test_invalid_versioned_envelope_is_rejected(self):
        payload = valid_input()
        payload["schema_version"] = 2

        with self.assertRaises(BiomassCarbonError):
            estimate_biomass_carbon(payload)


if __name__ == "__main__":
    unittest.main()
