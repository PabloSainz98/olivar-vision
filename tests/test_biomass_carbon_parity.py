"""Shared-fixture cases that the Swift estimator must also satisfy.

Expected numbers come from an independent `bc -l` calculation stored in
`tests/fixtures/biomass_carbon_parity_cases.json`, not from this package.
"""

import json
import unittest
from pathlib import Path

from olivar_vision.biomass_carbon import estimate_biomass_carbon


FIXTURE = Path(__file__).parent / "fixtures" / "biomass_carbon_parity_cases.json"


def build_payload(flat):
    return {
        "format_id": "olivar-biomass-carbon-input",
        "schema_version": 1,
        "tree_id": "parity-fixture",
        "measurement": {
            "basal_diameter_cm": flat["basal_diameter_cm"],
            "measurement_height_m": flat["measurement_height_m"],
            "diameter_uncertainty_cm": flat["diameter_uncertainty_cm"],
            "source": flat["source"],
            "validation_status": flat["validation_status"],
        },
        "domain": {
            "cultivar": flat["cultivar"],
            "training_system": flat["training_system"],
            "water_regime": flat["water_regime"],
            "orchard_density_trees_per_ha": flat["orchard_density_trees_per_ha"],
        },
        "carbon_fraction": {
            "value": flat["carbon_fraction"],
            "source": flat["carbon_fraction_source"],
            "is_proxy": flat["carbon_fraction_is_proxy"],
        },
    }


class BiomassCarbonParityFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_cases(self):
        tolerance = self.fixture["tolerance_kg"]
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                flat = dict(self.fixture["base_input"], **case["override"])
                report = estimate_biomass_carbon(build_payload(flat))
                expected = case["expected"]
                warning_codes = {warning["code"] for warning in report["warnings"]}

                self.assertEqual(report["availability"]["available"], expected["available"])
                if not expected["available"]:
                    self.assertEqual(report["status"], "ESTIMATION_NOT_AVAILABLE")
                    self.assertIsNone(report["result"])
                    self.assertTrue(report["availability"]["reasons"])
                    continue

                result = report["result"]
                numeric = {
                    "aboveground_dry_biomass_kg": result["modeled_biomass"]["aboveground_dry_biomass_kg"],
                    "kg_c": result["stored_carbon"]["kg_c"],
                    "kg_co2e": result["stored_co2_equivalent"]["kg_co2e"],
                }
                for key, value in numeric.items():
                    if key in expected:
                        self.assertAlmostEqual(value, expected[key], delta=tolerance)
                if "biomass_sensitivity_kg" in expected:
                    sensitivity = result["modeled_biomass"]["sensitivity_from_diameter_only_kg"]
                    if expected["biomass_sensitivity_kg"] is None:
                        self.assertIsNone(sensitivity)
                    else:
                        for actual, reference in zip(
                            sensitivity["biomass_range_kg"], expected["biomass_sensitivity_kg"]
                        ):
                            self.assertAlmostEqual(actual, reference, delta=tolerance)
                if "low_reliability_warning" in expected:
                    self.assertEqual(
                        "lower_reliability_below_10_cm" in warning_codes,
                        expected["low_reliability_warning"],
                    )
                if expected.get("sensitivity_omitted_warning"):
                    self.assertIn("sensitivity_crosses_model_domain", warning_codes)
                self.assertFalse(report["l3_gate"]["validated"])


if __name__ == "__main__":
    unittest.main()
