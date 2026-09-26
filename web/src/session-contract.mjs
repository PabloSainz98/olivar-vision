export const WEB_SESSION_FORMAT = "olivar-web-field-session";
export const WEB_SESSION_SCHEMA_VERSION = 1;
export const WEB_COMPARISON_FORMAT = "olivar-web-session-comparison";

export function createSession({
  sessionID = generateID(),
  repeatGroupID,
  context,
  capabilities,
  createdAt = new Date().toISOString(),
  userAgent = globalThis.navigator?.userAgent ?? "unknown",
}) {
  requireText(sessionID, "sessionID");
  requireText(repeatGroupID, "repeatGroupID");
  for (const field of ["treeID", "operatorID", "siteID"]) {
    requireText(context?.[field], `context.${field}`);
  }
  return {
    format_id: WEB_SESSION_FORMAT,
    schema_version: WEB_SESSION_SCHEMA_VERSION,
    session_id: sessionID,
    repeat_group_id: repeatGroupID,
    source_type: "web_rgb_manual",
    status: "in_progress",
    created_at: createdAt,
    finalized_at: null,
    capture: {
      tree_id: context.treeID.trim(),
      operator_id: context.operatorID.trim(),
      site_id: context.siteID.trim(),
      protocol_id: "lidar-carbon-web-v1",
      variety: optionalText(context.variety),
      weather: optionalText(context.weather),
      wind: optionalText(context.wind),
      pruning_state: optionalText(context.pruningState),
    },
    device: {
      user_agent: userAgent,
      platform: globalThis.navigator?.platform ?? "unknown",
    },
    capabilities: structuredCloneSafe(capabilities),
    units: {
      length: "meter",
      diameter: "centimeter",
    },
    coordinate_system: null,
    photos: [],
    discarded_captures: [],
    metric_references: [],
    manual_geometry: null,
    estimates: [],
    limitations: [
      "A browser RGB session is not an ARKit LiDAR capture.",
      "No depth, confidence map, camera intrinsics or world pose are inferred when the browser does not expose them.",
      "Manual geometry is stored as operator-provided reference data.",
    ],
  };
}

export function appendPhoto(session, photo) {
  requireMutable(session);
  requireText(photo.id, "photo.id");
  requireText(photo.sha256, "photo.sha256");
  if (session.photos.some((item) => item.id === photo.id)) {
    throw new Error(`photo already exists: ${photo.id}`);
  }
  const timestamp = requireFinite(photo.timestampMS, "photo.timestampMS");
  const previous = session.photos.at(-1)?.timestamp_ms;
  if (previous !== undefined && timestamp <= previous) {
    throw new Error("photo timestamps must increase strictly");
  }
  const next = cloneSession(session);
  next.photos.push({
    id: photo.id,
    path: `captured/${photo.id}/color.jpg`,
    timestamp_ms: timestamp,
    width: requirePositiveInteger(photo.width, "photo.width"),
    height: requirePositiveInteger(photo.height, "photo.height"),
    mime_type: photo.mimeType === "image/jpeg" ? photo.mimeType : "image/jpeg",
    size_bytes: requirePositiveInteger(photo.sizeBytes, "photo.sizeBytes"),
    sha256: photo.sha256,
    blob: photo.blob,
  });
  return next;
}

export function recordDiscardedCapture(session, reason, timestampMS = Date.now()) {
  requireMutable(session);
  requireText(reason, "reason");
  const next = cloneSession(session);
  next.discarded_captures.push({
    timestamp_ms: requireFinite(timestampMS, "timestampMS"),
    reason: reason.trim(),
  });
  return next;
}

export function addMetricReference(session, reference) {
  requireMutable(session);
  const expected = requirePositive(reference.expectedDistanceM, "expectedDistanceM");
  const observed = optionalPositive(reference.observedDistanceM, "observedDistanceM");
  const tolerance = reference.toleranceM === undefined
    ? 0.02
    : requirePositive(reference.toleranceM, "toleranceM");
  const next = cloneSession(session);
  const errorM = observed === null ? null : observed - expected;
  next.metric_references.push({
    reference_id: reference.referenceID ?? generateID(),
    expected_distance_m: expected,
    observed_distance_m: observed,
    absolute_error_m: errorM === null ? null : Math.abs(errorM),
    tolerance_m: tolerance,
    within_tolerance: errorM === null ? null : Math.abs(errorM) <= tolerance,
    method: "manual_external_reference",
    note: optionalText(reference.note),
  });
  return next;
}

export function setManualGeometry(session, geometry) {
  requireMutable(session);
  const verticalCoverage = optionalFraction(geometry.verticalCoverage, "verticalCoverage");
  const next = cloneSession(session);
  next.manual_geometry = {
    source: "operator_manual_reference",
    measured_at: geometry.measuredAt ?? new Date().toISOString(),
    tree_isolated: geometry.treeIsolated === true,
    basal_diameter_cm: optionalPositive(geometry.basalDiameterCM, "basalDiameterCM"),
    diameter_uncertainty_cm: optionalNonNegative(
      geometry.diameterUncertaintyCM,
      "diameterUncertaintyCM",
    ),
    measurement_height_m: 0.3,
    tree_height_m: optionalPositive(geometry.treeHeightM, "treeHeightM"),
    crown_span_x_m: optionalPositive(geometry.crownSpanXM, "crownSpanXM"),
    crown_span_z_m: optionalPositive(geometry.crownSpanZM, "crownSpanZM"),
    vertical_coverage: verticalCoverage,
    coverage_source: verticalCoverage === null ? null : "operator_declared",
    quality: geometryQuality(geometry.treeIsolated === true, verticalCoverage),
    note: optionalText(geometry.note),
    represents_complete_tree_volume: false,
  };
  return next;
}

export function addEstimate(session, estimate, createdAt = new Date().toISOString()) {
  requireMutable(session);
  const next = cloneSession(session);
  next.estimates.push({
    estimate_id: generateID(),
    created_at: createdAt,
    ...structuredCloneSafe(estimate),
  });
  return next;
}

export function finalizeSession(session, finalizedAt = new Date().toISOString()) {
  requireMutable(session);
  const next = cloneSession(session);
  next.status = "complete";
  next.finalized_at = finalizedAt;
  return next;
}

export function sessionManifest(session) {
  const manifest = cloneSession(session);
  manifest.photos = manifest.photos.map(({ blob: _blob, ...metadata }) => metadata);
  return manifest;
}

export function compareSessions(left, right, createdAt = new Date().toISOString()) {
  validateComparable(left, right);
  const leftGeometry = left.manual_geometry;
  const rightGeometry = right.manual_geometry;
  const fields = [
    "basal_diameter_cm",
    "tree_height_m",
    "crown_span_x_m",
    "crown_span_z_m",
    "vertical_coverage",
  ];
  const differences = {};
  for (const field of fields) {
    differences[field] = numericDifference(leftGeometry?.[field], rightGeometry?.[field]);
  }
  return {
    format_id: WEB_COMPARISON_FORMAT,
    schema_version: 1,
    created_at: createdAt,
    repeat_group_id: left.repeat_group_id,
    left_session_id: left.session_id,
    right_session_id: right.session_id,
    differences,
    interpretation: "paired observation only; not field validation or a precision claim",
  };
}

function validateComparable(left, right) {
  if (left.session_id === right.session_id) throw new Error("select two different sessions");
  if (left.repeat_group_id !== right.repeat_group_id) {
    throw new Error("sessions must share a repeat group");
  }
  if (left.status !== "complete" || right.status !== "complete") {
    throw new Error("both sessions must be complete");
  }
}

function numericDifference(left, right) {
  if (!Number.isFinite(left) || !Number.isFinite(right)) return null;
  const delta = right - left;
  return {
    left,
    right,
    delta,
    absolute_delta: Math.abs(delta),
    relative_delta: left === 0 ? null : delta / left,
  };
}

function geometryQuality(treeIsolated, verticalCoverage) {
  const reasons = [];
  if (!treeIsolated) reasons.push("tree_not_confirmed_isolated");
  if (verticalCoverage === null) reasons.push("vertical_coverage_missing");
  else if (verticalCoverage < 0.8) reasons.push("vertical_coverage_below_0_8");
  return {
    status: reasons.length === 0 ? "MANUAL_REFERENCE_COMPLETE" : "INCOMPLETE",
    reasons,
    field_validated: false,
  };
}

function requireMutable(session) {
  if (session.status !== "in_progress") throw new Error("session is finalized");
}

function cloneSession(session) {
  return structuredCloneSafe(session);
}

function structuredCloneSafe(value) {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

function requireText(value, field) {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${field} is required`);
  return value.trim();
}

function optionalText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function requireFinite(value, field) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${field} must be finite`);
  }
  return value;
}

function requirePositive(value, field) {
  const result = requireFinite(value, field);
  if (result <= 0) throw new Error(`${field} must be positive`);
  return result;
}

function optionalPositive(value, field) {
  if (value === null || value === undefined) return null;
  return requirePositive(value, field);
}

function optionalNonNegative(value, field) {
  if (value === null || value === undefined) return null;
  const result = requireFinite(value, field);
  if (result < 0) throw new Error(`${field} must be non-negative`);
  return result;
}

function optionalFraction(value, field) {
  if (value === null || value === undefined) return null;
  const result = requireFinite(value, field);
  if (result < 0 || result > 1) throw new Error(`${field} must be between zero and one`);
  return result;
}

function requirePositiveInteger(value, field) {
  if (!Number.isInteger(value) || value <= 0) throw new Error(`${field} must be a positive integer`);
  return value;
}

function generateID() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().toLowerCase();
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
