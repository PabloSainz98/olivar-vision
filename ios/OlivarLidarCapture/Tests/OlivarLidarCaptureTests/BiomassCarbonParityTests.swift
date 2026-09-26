import Foundation
import XCTest
@testable import OlivarLidarCapture

/// Runs the shared fixture that `tests/test_biomass_carbon_parity.py` also runs,
/// so the on-device calculator and the Python estimator cannot drift apart.
final class BiomassCarbonParityTests: XCTestCase {
    private static var fixtureURL: URL {
        // Tests/OlivarLidarCaptureTests/<file> -> repository root.
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("tests/fixtures/biomass_carbon_parity_cases.json")
    }

    func testSharedFixtureCases() throws {
        let data = try Data(contentsOf: Self.fixtureURL)
        let fixture = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let tolerance = try XCTUnwrap(fixture["tolerance_kg"] as? Double)
        let base = try XCTUnwrap(fixture["base_input"] as? [String: Any])
        let cases = try XCTUnwrap(fixture["cases"] as? [[String: Any]])
        XCTAssertFalse(cases.isEmpty)

        for testCase in cases {
            let id = testCase["id"] as? String ?? "?"
            let override = testCase["override"] as? [String: Any] ?? [:]
            let flat = base.merging(override) { _, new in new }
            let expected = try XCTUnwrap(testCase["expected"] as? [String: Any], id)
            let result = BiomassCarbonEstimator.estimate(Self.input(from: flat))

            XCTAssertEqual(result.isAvailable, expected["available"] as? Bool, id)
            guard result.isAvailable else {
                XCTAssertNil(result.abovegroundDryBiomassKG, id)
                XCTAssertFalse(result.reasons.isEmpty, id)
                continue
            }
            let numeric: [(String, Double?)] = [
                ("aboveground_dry_biomass_kg", result.abovegroundDryBiomassKG),
                ("kg_c", result.storedCarbonKG),
                ("kg_co2e", result.storedCO2EquivalentKG),
            ]
            for (key, actual) in numeric {
                if let reference = expected[key] as? Double {
                    XCTAssertEqual(try XCTUnwrap(actual, id), reference, accuracy: tolerance, "\(id) \(key)")
                }
            }
            if expected.keys.contains("biomass_sensitivity_kg") {
                if let bounds = expected["biomass_sensitivity_kg"] as? [Double] {
                    let range = try XCTUnwrap(result.biomassSensitivityKG, id)
                    XCTAssertEqual(range.lowerBound, bounds[0], accuracy: tolerance, id)
                    XCTAssertEqual(range.upperBound, bounds[1], accuracy: tolerance, id)
                } else {
                    XCTAssertNil(result.biomassSensitivityKG, id)
                }
            }
            if let lowReliability = expected["low_reliability_warning"] as? Bool {
                let hasWarning = result.warnings.contains { $0.contains("10 cm") }
                XCTAssertEqual(hasWarning, lowReliability, id)
            }
            if expected["sensitivity_omitted_warning"] as? Bool == true {
                XCTAssertTrue(result.warnings.contains { $0.contains("sensibilidad") }, id)
            }
        }
    }

    private static func input(from flat: [String: Any]) -> BiomassCarbonInput {
        BiomassCarbonInput(
            basalDiameterCM: flat["basal_diameter_cm"] as? Double,
            measurementHeightM: flat["measurement_height_m"] as? Double,
            diameterUncertaintyCM: flat["diameter_uncertainty_cm"] as? Double,
            diameterSource: (flat["source"] as? String).flatMap(BiomassDiameterSource.init(rawValue:)),
            lidarValidationStatus: flat["validation_status"] as? String,
            cultivar: flat["cultivar"] as? String ?? "",
            trainingSystem: flat["training_system"] as? String ?? "",
            waterRegime: flat["water_regime"] as? String ?? "",
            orchardDensityTreesPerHa: flat["orchard_density_trees_per_ha"] as? Double,
            carbonFraction: flat["carbon_fraction"] as? Double,
            carbonFractionSource: flat["carbon_fraction_source"] as? String ?? "",
            carbonFractionIsProxy: flat["carbon_fraction_is_proxy"] as? Bool ?? false
        )
    }
}
