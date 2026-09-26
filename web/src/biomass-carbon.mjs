export const BIOMASS_MODEL = Object.freeze({
  version: "brunori-2017-leccino-db-agb-v1",
  equation: "AGB_dry_kg = 0.0538 * DB_cm^2.4208",
  sourceDOI: "10.1007/s00468-017-1592-9",
  coefficient: 0.0538,
  exponent: 2.4208,
  minimumDiameterCM: 5,
  reliableFromDiameterCM: 10,
  maximumDiameterCM: 45,
  minimumDensityPerHa: 70,
  maximumDensityPerHa: 250,
  fitRMSEKG: 9.6909,
});

const CO2_TO_C_RATIO = 44 / 12;

export function estimateBiomassCarbon(input) {
  const reasons = [];
  const warnings = [];
  const diameter = finiteNumber(input.basalDiameterCM);
  const measurementHeight = finiteNumber(input.measurementHeightM);
  const density = finiteNumber(input.orchardDensityTreesPerHa);
  const carbonFraction = finiteNumber(input.carbonFraction);
  const uncertainty = optionalFiniteNumber(input.diameterUncertaintyCM);

  if (diameter === null) reasons.push("Falta el diametro basal.");
  if (measurementHeight === null) reasons.push("Falta la altura de medida del diametro.");
  if (density === null) reasons.push("Falta la densidad de plantacion.");
  if (carbonFraction === null) reasons.push("Falta la fraccion de carbono.");

  if (diameter !== null && !inRange(diameter, 5, 45)) {
    reasons.push("El diametro basal esta fuera del dominio publicado de 5 a 45 cm.");
  }
  if (measurementHeight !== null && Math.abs(measurementHeight - 0.3) > 0.02 + 1e-9) {
    reasons.push("El diametro basal debe medirse a 0,30 m, con tolerancia de 0,02 m.");
  }
  if (!['manual_tape', 'lidar'].includes(input.diameterSource)) {
    reasons.push("Falta el origen valido del diametro.");
  } else if (
    input.diameterSource === "lidar" &&
    input.lidarValidationStatus !== "VALIDATED_REAL_DEVICE"
  ) {
    reasons.push("El diametro LiDAR no esta validado en dispositivo real.");
  }
  if (normalized(input.cultivar) !== "leccino") {
    reasons.push("El modelo v1 solo admite la variedad Leccino.");
  }
  if (!["vase", "polyconic_vase"].includes(normalized(input.trainingSystem))) {
    reasons.push("El modelo v1 requiere formacion en vaso.");
  }
  if (normalized(input.waterRegime) !== "traditional_rainfed") {
    reasons.push("El modelo v1 requiere secano tradicional.");
  }
  if (density !== null && !inRange(density, 70, 250)) {
    reasons.push("La densidad debe estar entre 70 y 250 arboles por hectarea.");
  }
  if (carbonFraction !== null && !(carbonFraction > 0 && carbonFraction <= 1)) {
    reasons.push("La fraccion de carbono debe ser mayor que 0 y menor o igual que 1.");
  }
  if (typeof input.carbonFractionSource !== "string" || !input.carbonFractionSource.trim()) {
    reasons.push("Falta la fuente de la fraccion de carbono.");
  }
  if (input.diameterUncertaintyCM !== null && input.diameterUncertaintyCM !== undefined) {
    if (uncertainty === null || uncertainty < 0) {
      reasons.push("La incertidumbre del diametro debe ser finita y no negativa.");
    }
  }

  if (diameter !== null && diameter >= 5 && diameter < 10) {
    warnings.push("La publicacion informa mayor fiabilidad desde 10 cm de diametro basal.");
  }
  if (input.carbonFractionIsProxy === true) {
    warnings.push(
      "La fraccion de carbono es un proxy documentado, no una validacion especifica de Leccino.",
    );
  }

  if (reasons.length > 0) {
    return unavailable(reasons, warnings);
  }

  const biomass = biomassForDiameter(diameter);
  const carbon = biomass * carbonFraction;
  let biomassSensitivityKG = null;
  if (uncertainty !== null && uncertainty > 0) {
    const lowerDiameter = diameter - uncertainty;
    const upperDiameter = diameter + uncertainty;
    if (lowerDiameter >= 5 && upperDiameter <= 45) {
      biomassSensitivityKG = [
        biomassForDiameter(lowerDiameter),
        biomassForDiameter(upperDiameter),
      ];
    } else {
      warnings.push("La sensibilidad cruza el dominio publicado y no se calcula.");
    }
  }

  return {
    status: "EXPERIMENTAL_ESTIMATE",
    available: true,
    reasons: [],
    warnings,
    model: BIOMASS_MODEL,
    geometryInput: {
      basalDiameterCM: diameter,
      measurementHeightM: measurementHeight,
      diameterUncertaintyCM: uncertainty,
      source: input.diameterSource,
      lidarValidationStatus: input.lidarValidationStatus ?? null,
    },
    abovegroundDryBiomassKG: biomass,
    storedCarbonKG: carbon,
    storedCO2EquivalentKG: carbon * CO2_TO_C_RATIO,
    biomassSensitivityKG,
    storedCarbonSensitivityKG: scaleRange(biomassSensitivityKG, carbonFraction),
    storedCO2EquivalentSensitivityKG: scaleRange(
      biomassSensitivityKG,
      carbonFraction * CO2_TO_C_RATIO,
    ),
    carbonFraction: {
      value: carbonFraction,
      source: input.carbonFractionSource.trim(),
      isProxy: input.carbonFractionIsProxy === true,
    },
    l3Gate: {
      validated: false,
      status: "PENDING_LOCAL_CALIBRATION_AND_INDEPENDENT_VALIDATION",
    },
  };
}

export function parseLocaleNumber(value) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = Number(value.trim().replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function unavailable(reasons, warnings) {
  return {
    status: "ESTIMATION_NOT_AVAILABLE",
    available: false,
    reasons,
    warnings,
    model: BIOMASS_MODEL,
    abovegroundDryBiomassKG: null,
    storedCarbonKG: null,
    storedCO2EquivalentKG: null,
    biomassSensitivityKG: null,
    storedCarbonSensitivityKG: null,
    storedCO2EquivalentSensitivityKG: null,
    l3Gate: {
      validated: false,
      status: "PENDING_LOCAL_CALIBRATION_AND_INDEPENDENT_VALIDATION",
    },
  };
}

function biomassForDiameter(diameterCM) {
  return BIOMASS_MODEL.coefficient * diameterCM ** BIOMASS_MODEL.exponent;
}

function scaleRange(range, factor) {
  return range ? [range[0] * factor, range[1] * factor] : null;
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function optionalFiniteNumber(value) {
  if (value === null || value === undefined) return null;
  return finiteNumber(value);
}

function inRange(value, minimum, maximum) {
  return value >= minimum && value <= maximum;
}

function normalized(value) {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}
