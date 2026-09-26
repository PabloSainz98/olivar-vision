"""Versioned, domain-restricted olive biomass and carbon estimates.

The implemented allometry is intentionally isolated from LiDAR capture. A scan
cannot become a biomass estimate unless its diameter has passed real-device
validation; a manual tape diameter is accepted as the current reference path.
"""

import math
from typing import Any, Dict, List, Mapping, Optional


INPUT_FORMAT_ID = "olivar-biomass-carbon-input"
OUTPUT_FORMAT_ID = "olivar-biomass-carbon-estimate"
SCHEMA_VERSION = 1
MODEL_VERSION = "brunori-2017-leccino-db-agb-v1"
MODEL_DOI = "10.1007/s00468-017-1592-9"
MODEL_COEFFICIENT = 0.0538
MODEL_EXPONENT = 2.4208
MODEL_MIN_DB_CM = 5.0
MODEL_RELIABLE_FROM_DB_CM = 10.0
MODEL_MAX_DB_CM = 45.0
MODEL_MIN_DENSITY_HA = 70.0
MODEL_MAX_DENSITY_HA = 250.0
MODEL_DB_HEIGHT_M = 0.30
MODEL_DB_HEIGHT_TOLERANCE_M = 0.02
# Absorbs binary rounding so that 0.28 m and 0.32 m are both inside the
# documented inclusive tolerance; it does not widen the tolerance itself.
FLOAT_COMPARISON_EPSILON = 1e-9
MODEL_RMSE_KG = 9.6909
CO2_TO_C_MASS_RATIO = 44.0 / 12.0


class BiomassCarbonError(ValueError):
    """Raised when the versioned input envelope itself is invalid."""


def estimate_biomass_carbon(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return an explicit estimate or an unavailable result with reasons.

    Numeric output is only produced inside the published model domain. Carbon
    concentration is never assumed: callers must provide both a fraction and a
    source, even when using a literature value as an explicit proxy.
    """

    if payload.get("format_id") != INPUT_FORMAT_ID:
        raise BiomassCarbonError(f"format_id must be {INPUT_FORMAT_ID}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BiomassCarbonError(f"schema_version must be {SCHEMA_VERSION}")

    reasons: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    measurement = _mapping_or_reason(payload.get("measurement"), "measurement", reasons)
    domain = _mapping_or_reason(payload.get("domain"), "domain", reasons)
    carbon = _mapping_or_reason(payload.get("carbon_fraction"), "carbon_fraction", reasons)

    diameter_cm = _number_or_reason(
        measurement.get("basal_diameter_cm"), "missing_basal_diameter", reasons
    )
    measurement_height_m = _number_or_reason(
        measurement.get("measurement_height_m"), "missing_measurement_height", reasons
    )
    diameter_uncertainty_cm = _optional_number(
        measurement.get("diameter_uncertainty_cm"), "diameter_uncertainty_cm", reasons
    )
    diameter_source = measurement.get("source")
    if diameter_source not in {"manual_tape", "lidar"}:
        reasons.append(
            _reason(
                "invalid_diameter_source",
                "measurement.source must be manual_tape or lidar",
            )
        )
    if diameter_source == "lidar" and measurement.get("validation_status") != "VALIDATED_REAL_DEVICE":
        reasons.append(
            _reason(
                "lidar_diameter_not_validated",
                "a LiDAR diameter requires VALIDATED_REAL_DEVICE status from the L2 protocol",
            )
        )

    if diameter_cm is not None and not (MODEL_MIN_DB_CM <= diameter_cm <= MODEL_MAX_DB_CM):
        reasons.append(
            _reason(
                "diameter_outside_model_domain",
                f"basal diameter must be within {MODEL_MIN_DB_CM:g}-{MODEL_MAX_DB_CM:g} cm",
            )
        )
    if measurement_height_m is not None and (
        abs(measurement_height_m - MODEL_DB_HEIGHT_M)
        > MODEL_DB_HEIGHT_TOLERANCE_M + FLOAT_COMPARISON_EPSILON
    ):
        reasons.append(
            _reason(
                "measurement_height_outside_definition",
                "basal diameter must be measured over the stump at 0.30 m (+/- 0.02 m)",
            )
        )
    if diameter_uncertainty_cm is not None and diameter_uncertainty_cm < 0:
        reasons.append(
            _reason(
                "invalid_diameter_uncertainty",
                "diameter_uncertainty_cm must be zero or positive",
            )
        )

    cultivar = _normalized(domain.get("cultivar"))
    training_system = _normalized(domain.get("training_system"))
    water_regime = _normalized(domain.get("water_regime"))
    density = _number_or_reason(
        domain.get("orchard_density_trees_per_ha"), "missing_orchard_density", reasons
    )
    if cultivar != "leccino":
        reasons.append(_reason("unsupported_cultivar", "model v1 is restricted to Leccino"))
    if training_system not in {"vase", "polyconic_vase"}:
        reasons.append(
            _reason("unsupported_training_system", "model v1 requires vase training")
        )
    if water_regime != "traditional_rainfed":
        reasons.append(
            _reason(
                "unsupported_water_regime",
                "model v1 requires traditional rain-fed conditions",
            )
        )
    if density is not None and not (MODEL_MIN_DENSITY_HA <= density <= MODEL_MAX_DENSITY_HA):
        reasons.append(
            _reason(
                "density_outside_model_domain",
                f"orchard density must be within {MODEL_MIN_DENSITY_HA:g}-{MODEL_MAX_DENSITY_HA:g} trees/ha",
            )
        )

    carbon_fraction = _number_or_reason(
        carbon.get("value"), "missing_carbon_fraction", reasons
    )
    carbon_source = carbon.get("source")
    if carbon_fraction is not None and not (0.0 < carbon_fraction <= 1.0):
        reasons.append(
            _reason("invalid_carbon_fraction", "carbon fraction must be greater than 0 and at most 1")
        )
    if not isinstance(carbon_source, str) or not carbon_source.strip():
        reasons.append(
            _reason(
                "missing_carbon_fraction_source",
                "carbon fraction source must be recorded explicitly",
            )
        )

    if diameter_cm is not None and MODEL_MIN_DB_CM <= diameter_cm < MODEL_RELIABLE_FROM_DB_CM:
        warnings.append(
            _reason(
                "lower_reliability_below_10_cm",
                "the publication reports more reliable prediction from 10 cm basal diameter onward",
            )
        )
    if carbon.get("is_proxy") is True:
        warnings.append(
            _reason(
                "carbon_fraction_proxy",
                "the selected carbon fraction is a documented proxy, not a Leccino-specific validation",
            )
        )

    available = not reasons
    result: Optional[Dict[str, Any]] = None
    if available:
        assert diameter_cm is not None
        assert carbon_fraction is not None
        biomass_kg = _biomass_kg(diameter_cm)
        carbon_kg = biomass_kg * carbon_fraction
        co2e_kg = carbon_kg * CO2_TO_C_MASS_RATIO
        sensitivity = _diameter_sensitivity(diameter_cm, diameter_uncertainty_cm)
        if sensitivity is None and diameter_uncertainty_cm is not None and diameter_uncertainty_cm > 0:
            warnings.append(
                _reason(
                    "sensitivity_crosses_model_domain",
                    "diameter sensitivity was omitted because its bounds cross the published model domain",
                )
            )
        result = {
            "geometry_input": {
                "basal_diameter_cm": _rounded(diameter_cm),
                "measurement_height_m": _rounded(measurement_height_m),
                "source": diameter_source,
                "diameter_uncertainty_cm": _rounded(diameter_uncertainty_cm),
            },
            "modeled_biomass": {
                "aboveground_dry_biomass_kg": _rounded(biomass_kg),
                "sensitivity_from_diameter_only_kg": sensitivity,
            },
            "stored_carbon": {
                "kg_c": _rounded(carbon_kg),
                "sensitivity_from_diameter_only_kg_c": _scaled_sensitivity(
                    sensitivity, carbon_fraction
                ),
                "biomass_carbon_fraction": _rounded(carbon_fraction),
                "fraction_source": carbon_source.strip(),
                "fraction_is_proxy": carbon.get("is_proxy") is True,
            },
            "stored_co2_equivalent": {
                "kg_co2e": _rounded(co2e_kg),
                "sensitivity_from_diameter_only_kg_co2e": _scaled_sensitivity(
                    sensitivity, carbon_fraction * CO2_TO_C_MASS_RATIO
                ),
                "conversion": "kg C * 44/12",
            },
        }

    return {
        "format_id": OUTPUT_FORMAT_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "EXPERIMENTAL_ESTIMATE" if available else "ESTIMATION_NOT_AVAILABLE",
        "tree_id": payload.get("tree_id"),
        "input_parameters": {
            "measurement": dict(measurement),
            "domain": dict(domain),
            "carbon_fraction": dict(carbon),
        },
        "model": _model_metadata(),
        "availability": {"available": available, "reasons": reasons},
        "warnings": warnings,
        "result": result,
        "l3_gate": {
            "status": "PENDING_LOCAL_CALIBRATION_AND_INDEPENDENT_VALIDATION",
            "validated": False,
        },
        "limitations": [
            "This is above-ground dry biomass; roots and soil carbon are excluded.",
            "Canopy volume is not converted to wood or biomass.",
            "Stored CO2 equivalent is a stock conversion, not annual absorption or sequestration.",
            "Publication fit RMSE is descriptive and is not an individual prediction interval.",
        ],
    }


def _model_metadata() -> Dict[str, Any]:
    return {
        "version": MODEL_VERSION,
        "source_doi": MODEL_DOI,
        "equation": "AGB_dry_kg = 0.0538 * DB_cm^2.4208",
        "dependent_variable": "above-ground dry biomass in kilograms",
        "independent_variable": "basal diameter DB in centimeters, measured over the stump",
        "measurement_height_convention": (
            "project convention 0.30 +/- 0.02 m; the publication defines DB as over the "
            "stump and cites Villalobos et al. 2005 for 0.3 m, without stating its own height"
        ),
        "fit_rmse_kg": MODEL_RMSE_KG,
        "sample_size_trees": 14,
        "domain": {
            "cultivar": "Leccino",
            "training_system": "vase",
            "water_regime": "traditional_rainfed",
            "orchard_density_trees_per_ha": [MODEL_MIN_DENSITY_HA, MODEL_MAX_DENSITY_HA],
            "basal_diameter_cm": [MODEL_MIN_DB_CM, MODEL_MAX_DB_CM],
        },
    }


def _diameter_sensitivity(
    diameter_cm: float, uncertainty_cm: Optional[float]
) -> Optional[Dict[str, Any]]:
    if uncertainty_cm is None or uncertainty_cm == 0:
        return None
    low = diameter_cm - uncertainty_cm
    high = diameter_cm + uncertainty_cm
    if low < MODEL_MIN_DB_CM or high > MODEL_MAX_DB_CM:
        return None
    return {
        "diameter_range_cm": [_rounded(low), _rounded(high)],
        "biomass_range_kg": [_rounded(_biomass_kg(low)), _rounded(_biomass_kg(high))],
        "interpretation": "input-measurement sensitivity, not a confidence interval",
    }


def _biomass_kg(diameter_cm: float) -> float:
    return MODEL_COEFFICIENT * math.pow(diameter_cm, MODEL_EXPONENT)


def _scaled_sensitivity(
    sensitivity: Optional[Mapping[str, Any]], factor: float
) -> Optional[Dict[str, Any]]:
    if sensitivity is None:
        return None
    low, high = sensitivity["biomass_range_kg"]
    return {
        "range": [_rounded(low * factor), _rounded(high * factor)],
        "interpretation": sensitivity["interpretation"],
    }


def _mapping_or_reason(
    value: Any, field: str, reasons: List[Dict[str, str]]
) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    reasons.append(_reason(f"missing_{field}", f"{field} must be an object"))
    return {}


def _number_or_reason(
    value: Any, code: str, reasons: List[Dict[str, str]]
) -> Optional[float]:
    number = _as_finite_number(value)
    if number is None:
        reasons.append(_reason(code, code.replace("_", " ")))
    return number


def _optional_number(
    value: Any, field: str, reasons: List[Dict[str, str]]
) -> Optional[float]:
    if value is None:
        return None
    number = _as_finite_number(value)
    if number is None:
        reasons.append(_reason(f"invalid_{field}", f"{field} must be a finite number"))
    return number


def _as_finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _normalized(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _reason(code: str, detail: str) -> Dict[str, str]:
    return {"code": code, "detail": detail}


def _rounded(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 6)
