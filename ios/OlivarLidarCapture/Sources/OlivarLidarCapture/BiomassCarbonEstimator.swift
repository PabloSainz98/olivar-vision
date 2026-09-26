import Foundation

public enum BiomassDiameterSource: String, Codable, Sendable {
    case manualTape = "manual_tape"
    case lidar
}

public struct BiomassCarbonInput: Equatable, Sendable {
    public let basalDiameterCM: Double?
    public let measurementHeightM: Double?
    public let diameterUncertaintyCM: Double?
    public let diameterSource: BiomassDiameterSource?
    public let lidarValidationStatus: String?
    public let cultivar: String
    public let trainingSystem: String
    public let waterRegime: String
    public let orchardDensityTreesPerHa: Double?
    public let carbonFraction: Double?
    public let carbonFractionSource: String
    public let carbonFractionIsProxy: Bool

    public init(
        basalDiameterCM: Double?,
        measurementHeightM: Double?,
        diameterUncertaintyCM: Double? = nil,
        diameterSource: BiomassDiameterSource?,
        lidarValidationStatus: String? = nil,
        cultivar: String,
        trainingSystem: String,
        waterRegime: String,
        orchardDensityTreesPerHa: Double?,
        carbonFraction: Double?,
        carbonFractionSource: String,
        carbonFractionIsProxy: Bool
    ) {
        self.basalDiameterCM = basalDiameterCM
        self.measurementHeightM = measurementHeightM
        self.diameterUncertaintyCM = diameterUncertaintyCM
        self.diameterSource = diameterSource
        self.lidarValidationStatus = lidarValidationStatus
        self.cultivar = cultivar
        self.trainingSystem = trainingSystem
        self.waterRegime = waterRegime
        self.orchardDensityTreesPerHa = orchardDensityTreesPerHa
        self.carbonFraction = carbonFraction
        self.carbonFractionSource = carbonFractionSource
        self.carbonFractionIsProxy = carbonFractionIsProxy
    }
}

public struct BiomassCarbonEstimate: Equatable, Sendable {
    public let status: String
    public let reasons: [String]
    public let warnings: [String]
    public let abovegroundDryBiomassKG: Double?
    public let storedCarbonKG: Double?
    public let storedCO2EquivalentKG: Double?
    public let biomassSensitivityKG: ClosedRange<Double>?
    public let storedCarbonSensitivityKG: ClosedRange<Double>?
    public let storedCO2EquivalentSensitivityKG: ClosedRange<Double>?

    public var isAvailable: Bool { status == "EXPERIMENTAL_ESTIMATE" }
}

public enum BiomassCarbonEstimator {
    public static let modelVersion = "brunori-2017-leccino-db-agb-v1"
    public static let equation = "AGB_dry_kg = 0.0538 * DB_cm^2.4208"
    public static let sourceDOI = "10.1007/s00468-017-1592-9"

    public static func estimate(_ input: BiomassCarbonInput) -> BiomassCarbonEstimate {
        var reasons: [String] = []
        var warnings: [String] = []
        guard let diameter = input.basalDiameterCM, diameter.isFinite else {
            return unavailable("Falta el diametro basal.")
        }
        guard let measurementHeight = input.measurementHeightM, measurementHeight.isFinite else {
            return unavailable("Falta la altura de medida del diametro.")
        }
        guard let density = input.orchardDensityTreesPerHa, density.isFinite else {
            return unavailable("Falta la densidad de plantacion.")
        }
        guard let carbonFraction = input.carbonFraction, carbonFraction.isFinite else {
            return unavailable("Falta la fraccion de carbono.")
        }

        if !(5.0...45.0).contains(diameter) {
            reasons.append("El diametro basal esta fuera del dominio publicado de 5 a 45 cm.")
        }
        // The epsilon absorbs binary rounding so 0.28 m and 0.32 m stay inside
        // the documented inclusive tolerance; it does not widen it.
        if abs(measurementHeight - 0.3) > 0.02 + 1e-9 {
            reasons.append("El diametro basal debe medirse a 0,30 m, con tolerancia de 0,02 m.")
        }
        if input.diameterSource == nil {
            reasons.append("Falta el origen del diametro.")
        } else if input.diameterSource == .lidar && input.lidarValidationStatus != "VALIDATED_REAL_DEVICE" {
            reasons.append("El diametro LiDAR no esta validado en dispositivo real.")
        }
        if normalized(input.cultivar) != "leccino" {
            reasons.append("El modelo v1 solo admite la variedad Leccino.")
        }
        if !["vase", "polyconic_vase"].contains(normalized(input.trainingSystem)) {
            reasons.append("El modelo v1 requiere formacion en vaso.")
        }
        if normalized(input.waterRegime) != "traditional_rainfed" {
            reasons.append("El modelo v1 requiere secano tradicional.")
        }
        if !(70.0...250.0).contains(density) {
            reasons.append("La densidad debe estar entre 70 y 250 arboles por hectarea.")
        }
        if !(carbonFraction > 0.0 && carbonFraction <= 1.0) {
            reasons.append("La fraccion de carbono debe ser mayor que 0 y menor o igual que 1.")
        }
        if input.carbonFractionSource.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            reasons.append("Falta la fuente de la fraccion de carbono.")
        }
        if let uncertainty = input.diameterUncertaintyCM,
           !uncertainty.isFinite || uncertainty < 0 {
            reasons.append("La incertidumbre del diametro debe ser finita y no negativa.")
        }
        if diameter >= 5.0 && diameter < 10.0 {
            warnings.append("La publicacion informa mayor fiabilidad desde 10 cm de diametro basal.")
        }
        if input.carbonFractionIsProxy {
            warnings.append("La fraccion de carbono es un proxy documentado, no una validacion especifica de Leccino.")
        }
        if !reasons.isEmpty {
            return BiomassCarbonEstimate(
                status: "ESTIMATION_NOT_AVAILABLE",
                reasons: reasons,
                warnings: warnings,
                abovegroundDryBiomassKG: nil,
                storedCarbonKG: nil,
                storedCO2EquivalentKG: nil,
                biomassSensitivityKG: nil,
                storedCarbonSensitivityKG: nil,
                storedCO2EquivalentSensitivityKG: nil
            )
        }

        let biomass = 0.0538 * pow(diameter, 2.4208)
        let carbon = biomass * carbonFraction
        var sensitivity: ClosedRange<Double>?
        if let uncertainty = input.diameterUncertaintyCM, uncertainty > 0 {
            let lowerDiameter = diameter - uncertainty
            let upperDiameter = diameter + uncertainty
            if lowerDiameter >= 5.0 && upperDiameter <= 45.0 {
                let lowerBiomass = 0.0538 * pow(lowerDiameter, 2.4208)
                let upperBiomass = 0.0538 * pow(upperDiameter, 2.4208)
                sensitivity = lowerBiomass...upperBiomass
            } else {
                warnings.append("La sensibilidad cruza el dominio publicado y no se calcula.")
            }
        }
        return BiomassCarbonEstimate(
            status: "EXPERIMENTAL_ESTIMATE",
            reasons: [],
            warnings: warnings,
            abovegroundDryBiomassKG: biomass,
            storedCarbonKG: carbon,
            storedCO2EquivalentKG: carbon * 44.0 / 12.0,
            biomassSensitivityKG: sensitivity,
            storedCarbonSensitivityKG: scale(sensitivity, by: carbonFraction),
            storedCO2EquivalentSensitivityKG: scale(
                sensitivity,
                by: carbonFraction * 44.0 / 12.0
            )
        )
    }

    private static func unavailable(_ reason: String) -> BiomassCarbonEstimate {
        BiomassCarbonEstimate(
            status: "ESTIMATION_NOT_AVAILABLE",
            reasons: [reason],
            warnings: [],
            abovegroundDryBiomassKG: nil,
            storedCarbonKG: nil,
            storedCO2EquivalentKG: nil,
            biomassSensitivityKG: nil,
            storedCarbonSensitivityKG: nil,
            storedCO2EquivalentSensitivityKG: nil
        )
    }

    private static func scale(
        _ range: ClosedRange<Double>?,
        by factor: Double
    ) -> ClosedRange<Double>? {
        guard let range else { return nil }
        return (range.lowerBound * factor)...(range.upperBound * factor)
    }

    private static func normalized(_ value: String) -> String {
        value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }
}
