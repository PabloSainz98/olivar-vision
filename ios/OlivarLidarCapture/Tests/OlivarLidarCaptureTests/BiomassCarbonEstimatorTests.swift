import XCTest
@testable import OlivarLidarCapture

final class BiomassCarbonEstimatorTests: XCTestCase {
    func testValidManualInputProducesSeparatedStocks() {
        let input = BiomassCarbonInput(
            basalDiameterCM: 20,
            measurementHeightM: 0.3,
            diameterUncertaintyCM: 0.5,
            diameterSource: .manualTape,
            cultivar: "Leccino",
            trainingSystem: "vase",
            waterRegime: "traditional_rainfed",
            orchardDensityTreesPerHa: 150,
            carbonFraction: 0.47,
            carbonFractionSource: "synthetic test proxy",
            carbonFractionIsProxy: true
        )

        let result = BiomassCarbonEstimator.estimate(input)
        let biomass = 0.0538 * pow(20.0, 2.4208)

        XCTAssertTrue(result.isAvailable)
        XCTAssertEqual(result.abovegroundDryBiomassKG!, biomass, accuracy: 1e-9)
        XCTAssertEqual(result.storedCarbonKG!, biomass * 0.47, accuracy: 1e-9)
        XCTAssertEqual(result.storedCO2EquivalentKG!, biomass * 0.47 * 44 / 12, accuracy: 1e-9)
        XCTAssertNotNil(result.biomassSensitivityKG)
        XCTAssertNotNil(result.storedCarbonSensitivityKG)
        XCTAssertNotNil(result.storedCO2EquivalentSensitivityKG)
    }

    func testOutOfDomainInputIsUnavailable() {
        let input = BiomassCarbonInput(
            basalDiameterCM: 50,
            measurementHeightM: 0.3,
            diameterSource: .lidar,
            lidarValidationStatus: "SYNTHETIC_ONLY",
            cultivar: "Picual",
            trainingSystem: "hedgerow",
            waterRegime: "irrigated",
            orchardDensityTreesPerHa: 1000,
            carbonFraction: 0.47,
            carbonFractionSource: "synthetic test proxy",
            carbonFractionIsProxy: true
        )

        let result = BiomassCarbonEstimator.estimate(input)

        XCTAssertFalse(result.isAvailable)
        XCTAssertNil(result.abovegroundDryBiomassKG)
        XCTAssertGreaterThanOrEqual(result.reasons.count, 5)
    }
}
