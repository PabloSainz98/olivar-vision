import assert from "node:assert/strict";
import test from "node:test";

import {
  addEstimate,
  addMetricReference,
  appendPhoto,
  compareSessions,
  createSession,
  finalizeSession,
  sessionManifest,
  setManualGeometry,
} from "../src/session-contract.mjs";

test("web session preserves photo originals and separates manual geometry", () => {
  const original = baseSession("session-1");
  const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "image/jpeg" });
  const withPhoto = appendPhoto(original, {
    id: "frame-000001",
    timestampMS: 100,
    width: 2,
    height: 1,
    mimeType: "image/jpeg",
    sizeBytes: blob.size,
    sha256: "abc",
    blob,
  });
  const withReference = addMetricReference(withPhoto, {
    referenceID: "rule-1",
    expectedDistanceM: 1,
    observedDistanceM: 0.99,
  });
  const withGeometry = setManualGeometry(withReference, {
    treeIsolated: true,
    basalDiameterCM: 20,
    diameterUncertaintyCM: 0.5,
    treeHeightM: 3.2,
    crownSpanXM: 2.4,
    crownSpanZM: 2.1,
    verticalCoverage: 0.9,
  });

  assert.equal(original.photos.length, 0);
  assert.equal(withGeometry.photos[0].blob.size, blob.size);
  assert.equal(withGeometry.photos[0].blob.type, blob.type);
  assert.equal(withGeometry.manual_geometry.represents_complete_tree_volume, false);
  assert.equal(withGeometry.manual_geometry.quality.field_validated, false);
  assert.equal(withGeometry.metric_references[0].within_tolerance, true);
  assert.equal(sessionManifest(withGeometry).photos[0].blob, undefined);
});

test("finalized sessions reject mutation and repeated sessions can be compared", () => {
  const left = finalizeSession(setManualGeometry(baseSession("left"), {
    treeIsolated: true,
    basalDiameterCM: 20,
    treeHeightM: 3,
    crownSpanXM: 2,
    crownSpanZM: 2.5,
    verticalCoverage: 0.9,
  }));
  const right = finalizeSession(setManualGeometry(baseSession("right"), {
    treeIsolated: true,
    basalDiameterCM: 21,
    treeHeightM: 3.3,
    crownSpanXM: 2.1,
    crownSpanZM: 2.4,
    verticalCoverage: 0.85,
  }));
  const comparison = compareSessions(left, right);

  assert.equal(comparison.differences.basal_diameter_cm.delta, 1);
  assert.ok(Math.abs(comparison.differences.tree_height_m.delta - 0.3) < 1e-12);
  assert.throws(() => addEstimate(left, { status: "EXPERIMENTAL_ESTIMATE" }), /finalized/);
  assert.throws(() => compareSessions(left, { ...right, repeat_group_id: "another" }), /repeat group/);
});

function baseSession(sessionID) {
  return createSession({
    sessionID,
    repeatGroupID: "repeat-1",
    context: {
      treeID: "tree-1",
      operatorID: "operator-1",
      siteID: "site-1",
    },
    capabilities: { camera_api: true, arkit_scene_depth: "UNAVAILABLE_OUTSIDE_NATIVE_ARKIT" },
    createdAt: "2026-09-26T10:00:00.000Z",
    userAgent: "test",
  });
}
