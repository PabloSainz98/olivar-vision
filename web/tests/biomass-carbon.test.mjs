import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { estimateBiomassCarbon, parseLocaleNumber } from "../src/biomass-carbon.mjs";

const fixtureURL = new URL("../../tests/fixtures/biomass_carbon_parity_cases.json", import.meta.url);
const fixture = JSON.parse(await readFile(fixtureURL, "utf8"));

test("web estimator matches every shared Python and Swift parity case", () => {
  for (const item of fixture.cases) {
    const flat = { ...fixture.base_input, ...item.override };
    const result = estimateBiomassCarbon({
      basalDiameterCM: flat.basal_diameter_cm,
      measurementHeightM: flat.measurement_height_m,
      diameterUncertaintyCM: flat.diameter_uncertainty_cm,
      diameterSource: flat.source,
      lidarValidationStatus: flat.validation_status,
      cultivar: flat.cultivar,
      trainingSystem: flat.training_system,
      waterRegime: flat.water_regime,
      orchardDensityTreesPerHa: flat.orchard_density_trees_per_ha,
      carbonFraction: flat.carbon_fraction,
      carbonFractionSource: flat.carbon_fraction_source,
      carbonFractionIsProxy: flat.carbon_fraction_is_proxy,
    });
    assert.equal(result.available, item.expected.available, item.id);
    assertClose(result.abovegroundDryBiomassKG, item.expected.aboveground_dry_biomass_kg, item.id);
    assertClose(result.storedCarbonKG, item.expected.kg_c, item.id);
    assertClose(result.storedCO2EquivalentKG, item.expected.kg_co2e, item.id);
    if ("biomass_sensitivity_kg" in item.expected) {
      assertRangeClose(result.biomassSensitivityKG, item.expected.biomass_sensitivity_kg, item.id);
    }
    if (item.expected.low_reliability_warning === true) {
      assert.ok(result.warnings.some((warning) => warning.includes("mayor fiabilidad")), item.id);
    }
    if (item.expected.low_reliability_warning === false) {
      assert.ok(!result.warnings.some((warning) => warning.includes("mayor fiabilidad")), item.id);
    }
    if (item.expected.sensitivity_omitted_warning === true) {
      assert.ok(result.warnings.some((warning) => warning.includes("cruza el dominio")), item.id);
    }
  }
});

test("locale parser accepts decimal comma and rejects blank values", () => {
  assert.equal(parseLocaleNumber("0,47"), 0.47);
  assert.equal(parseLocaleNumber(""), null);
  assert.equal(parseLocaleNumber("abc"), null);
});

function assertClose(actual, expected, label) {
  if (expected === undefined) return;
  assert.ok(actual !== null, label);
  assert.ok(Math.abs(actual - expected) <= fixture.tolerance_kg, label);
}

function assertRangeClose(actual, expected, label) {
  if (expected === null) {
    assert.equal(actual, null, label);
    return;
  }
  assert.ok(actual !== null, label);
  assertClose(actual[0], expected[0], label);
  assertClose(actual[1], expected[1], label);
}
