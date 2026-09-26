import { estimateBiomassCarbon, parseLocaleNumber } from "./biomass-carbon.mjs";
import { detectWebCapabilities, probeXRDepth } from "./capabilities.mjs";
import { buildSessionTar, downloadBlob, downloadJSON, sha256Hex } from "./export-session.mjs";
import {
  addEstimate,
  addMetricReference,
  appendPhoto,
  compareSessions,
  createSession,
  finalizeSession,
  recordDiscardedCapture,
  sessionManifest,
  setManualGeometry,
} from "./session-contract.mjs";
import {
  createStoredSession,
  listStoredSessions,
  openSessionDatabase,
  updateStoredSession,
} from "./storage.mjs";

const element = (id) => document.getElementById(id);
const state = {
  database: null,
  capabilities: null,
  activeSession: null,
  cameraStream: null,
  lastEstimate: null,
  installPrompt: null,
  toastTimer: null,
};

initialize();

async function initialize() {
  bindNavigation();
  bindControls();
  element("repeat-group-id").value = newID();
  element("geometry-coverage").dispatchEvent(new Event("input"));
  await registerServiceWorker();
  try {
    state.database = await openSessionDatabase();
    const sessions = await listStoredSessions(state.database);
    state.activeSession = sessions.find((session) => session.status === "in_progress") ?? null;
  } catch (error) {
    showToast(error.message);
  }
  await refreshCapabilities();
  updateActiveSessionUI();
  await renderSessions();
  updateConnectivity();
}

function bindNavigation() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  });
}

function activateTab(name) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    const active = button.dataset.tab === name;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    const active = panel.id === `tab-${name}`;
    panel.hidden = !active;
    panel.classList.toggle("is-active", active);
  });
  if (name === "sessions") renderSessions();
}

function bindControls() {
  element("refresh-capabilities").addEventListener("click", refreshCapabilities);
  element("probe-xr-depth").addEventListener("click", probeDepth);
  element("new-repeat-group").addEventListener("click", () => {
    element("repeat-group-id").value = newID();
  });
  element("start-camera").addEventListener("click", startCamera);
  element("start-session").addEventListener("click", startSession);
  element("capture-photo").addEventListener("click", capturePhoto);
  element("finish-session").addEventListener("click", finishSession);
  element("reference-form").addEventListener("submit", saveReference);
  element("geometry-form").addEventListener("submit", saveGeometry);
  element("geometry-coverage").addEventListener("input", () => {
    const value = Number(element("geometry-coverage").value);
    element("geometry-coverage-output").value = value.toLocaleString("es-ES", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  });
  element("refresh-sessions").addEventListener("click", renderSessions);
  element("compare-sessions").addEventListener("click", renderComparison);
  element("biomass-form").addEventListener("submit", calculateBiomass);
  element("biomass-source").addEventListener("change", updateLidarValidationField);
  updateLidarValidationField();
  element("use-active-geometry").addEventListener("click", useActiveGeometry);
  window.addEventListener("online", updateConnectivity);
  window.addEventListener("offline", updateConnectivity);
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    state.installPrompt = event;
    element("install-button").hidden = false;
  });
  element("install-button").addEventListener("click", installApplication);
}

async function refreshCapabilities() {
  state.capabilities = await detectWebCapabilities();
  capabilityValue("cap-secure", state.capabilities.secure_context, "Seguro", "Requiere HTTPS");
  capabilityValue("cap-camera", state.capabilities.camera_api, "Disponible", "No disponible");
  capabilityValue("cap-storage", Boolean(state.database), "Disponible", "No disponible");
  capabilityValue("cap-xr", state.capabilities.immersive_ar, "Disponible", "No disponible");
  element("probe-xr-depth").disabled = !state.capabilities.immersive_ar;
  const summary = state.capabilities.reason ?? state.capabilities.xr_reason ?? "Cámara y almacenamiento listos.";
  element("capability-summary").textContent = summary;
}

function capabilityValue(id, available, yes, no) {
  const target = element(id);
  target.textContent = available ? yes : no;
  target.dataset.state = available ? "ready" : "blocked";
}

async function probeDepth() {
  const button = element("probe-xr-depth");
  button.disabled = true;
  const target = element("cap-depth");
  target.textContent = "Probando";
  target.dataset.state = "pending";
  const result = await probeXRDepth();
  const supported = result.status === "SUPPORTED_BY_WEBXR_SESSION";
  target.textContent = supported ? "Disponible" : "No disponible";
  target.dataset.state = supported ? "ready" : "blocked";
  state.capabilities.xr_depth_sensing = result.status;
  state.capabilities.xr_depth_reason = result.reason;
  showToast(supported ? "El navegador aceptó una sesión WebXR con profundidad." : result.reason);
  button.disabled = !state.capabilities.immersive_ar;
}

async function startCamera() {
  if (!state.capabilities?.secure_context || !state.capabilities?.camera_api) {
    showToast(state.capabilities?.reason ?? "La cámara web no está disponible.");
    return;
  }
  stopCamera();
  try {
    state.cameraStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1920 },
        height: { ideal: 1440 },
      },
    });
    const preview = element("camera-preview");
    preview.srcObject = state.cameraStream;
    await preview.play();
    element("camera-placeholder").hidden = true;
    element("camera-state").textContent = cameraDescription(state.cameraStream);
    updateActiveSessionUI();
  } catch (error) {
    element("camera-state").textContent = "Permiso denegado o cámara no disponible";
    showToast(`${error.name}: ${error.message}`);
  }
}

function cameraDescription(stream) {
  const settings = stream.getVideoTracks()[0]?.getSettings?.() ?? {};
  const size = settings.width && settings.height ? `${settings.width} x ${settings.height}` : "resolución no declarada";
  return `Cámara activa · ${size}`;
}

function stopCamera() {
  state.cameraStream?.getTracks().forEach((track) => track.stop());
  state.cameraStream = null;
  const preview = element("camera-preview");
  preview.srcObject = null;
  element("camera-placeholder").hidden = false;
  element("camera-state").textContent = "Cámara detenida";
}

async function startSession() {
  if (!state.database) return showToast("El almacenamiento local no está disponible.");
  if (state.activeSession) return showToast("Finaliza la sesión activa antes de crear otra.");
  if (!element("context-form").reportValidity()) return;
  try {
    const session = createSession({
      repeatGroupID: element("repeat-group-id").value,
      context: {
        treeID: element("tree-id").value,
        operatorID: element("operator-id").value,
        siteID: element("site-id").value,
        variety: element("context-variety").value,
        weather: element("weather").value,
        wind: element("wind").value,
        pruningState: element("pruning-state").value,
      },
      capabilities: state.capabilities,
    });
    await createStoredSession(state.database, session);
    state.activeSession = session;
    updateActiveSessionUI();
    showToast("Sesión nueva guardada. Los originales no se sobrescribirán.");
  } catch (error) {
    showToast(error.message);
  }
}

async function capturePhoto() {
  if (!state.activeSession || !state.cameraStream) return;
  const video = element("camera-preview");
  if (!video.videoWidth || !video.videoHeight) return showToast("La cámara aún no entrega imagen.");
  const canvas = element("capture-canvas");
  const maximumWidth = 1920;
  const scale = Math.min(1, maximumWidth / video.videoWidth);
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext("2d", { alpha: false }).drawImage(video, 0, 0, canvas.width, canvas.height);
  try {
    const blob = await canvasBlob(canvas, "image/jpeg", 0.94);
    const count = state.activeSession.photos.length + 1;
    const id = `frame-${String(count).padStart(6, "0")}`;
    const previousTimestamp = state.activeSession.photos.at(-1)?.timestamp_ms ?? 0;
    const timestampMS = Math.max(Date.now(), previousTimestamp + 1);
    state.activeSession = appendPhoto(state.activeSession, {
      id,
      timestampMS,
      width: canvas.width,
      height: canvas.height,
      mimeType: blob.type,
      sizeBytes: blob.size,
      sha256: await sha256Hex(blob),
      blob,
    });
    await persistActiveSession();
    updateActiveSessionUI();
    showToast(`Foto ${count} conservada en el dispositivo.`);
  } catch (error) {
    state.activeSession = recordDiscardedCapture(state.activeSession, `photo_capture_failed: ${error.message}`);
    await persistActiveSession();
    showToast(error.message);
  }
}

async function saveReference(event) {
  event.preventDefault();
  if (!state.activeSession) return;
  const form = event.currentTarget;
  try {
    state.activeSession = addMetricReference(state.activeSession, {
      expectedDistanceM: requiredNumber("reference-expected", "Distancia real"),
      observedDistanceM: optionalNumber("reference-observed"),
      note: element("reference-note").value,
    });
    await persistActiveSession();
    form.reset();
    updateActiveSessionUI();
    showToast("Referencia guardada como medida externa.");
  } catch (error) {
    showToast(error.message);
  }
}

async function saveGeometry(event) {
  event.preventDefault();
  if (!state.activeSession) return;
  try {
    state.activeSession = setManualGeometry(state.activeSession, {
      treeIsolated: element("geometry-isolated").checked,
      basalDiameterCM: optionalNumber("geometry-db"),
      diameterUncertaintyCM: optionalNumber("geometry-db-uncertainty"),
      treeHeightM: optionalNumber("geometry-height"),
      crownSpanXM: optionalNumber("geometry-crown-x"),
      crownSpanZM: optionalNumber("geometry-crown-z"),
      verticalCoverage: Number(element("geometry-coverage").value),
      note: element("geometry-note").value,
    });
    await persistActiveSession();
    updateActiveSessionUI();
    showToast("Geometría manual guardada con calidad y cobertura declaradas.");
  } catch (error) {
    showToast(error.message);
  }
}

async function finishSession() {
  if (!state.activeSession) return;
  try {
    const completed = finalizeSession(state.activeSession);
    await updateStoredSession(state.database, completed);
    state.activeSession = null;
    stopCamera();
    updateActiveSessionUI();
    await renderSessions();
    showToast("Sesión finalizada. El historial queda bloqueado contra sobrescritura.");
  } catch (error) {
    showToast(error.message);
  }
}

async function persistActiveSession() {
  await updateStoredSession(state.database, state.activeSession);
}

function updateActiveSessionUI() {
  const active = Boolean(state.activeSession);
  const badge = element("active-session-badge");
  badge.textContent = active ? "En curso" : "Sin iniciar";
  badge.dataset.state = active ? "warning" : "neutral";
  element("start-session").disabled = active;
  element("capture-photo").disabled = !active || !state.cameraStream;
  element("finish-session").disabled = !active;
  element("reference-form").querySelector("button[type=submit]").disabled = !active;
  element("geometry-form").querySelector("button[type=submit]").disabled = !active;
  element("session-id-output").textContent = active ? state.activeSession.session_id : "";
  element("photo-count").textContent = `${state.activeSession?.photos.length ?? 0} fotos`;
  element("reference-count").textContent = `${state.activeSession?.metric_references.length ?? 0} referencias`;
}

async function renderSessions() {
  if (!state.database) return;
  const sessions = await listStoredSessions(state.database);
  const list = element("session-list");
  list.replaceChildren();
  if (sessions.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No hay sesiones guardadas.";
    list.append(empty);
  }
  for (const session of sessions) list.append(sessionRow(session));
  fillComparisonSelectors(sessions.filter((session) => session.status === "complete"));
}

function sessionRow(session) {
  const row = document.createElement("article");
  row.className = "session-row";
  const content = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = session.capture.tree_id;
  const meta = document.createElement("p");
  meta.textContent = `${formatDate(session.created_at)} · ${session.photos.length} fotos · ${session.status}`;
  const group = document.createElement("p");
  group.textContent = `Grupo ${session.repeat_group_id}`;
  content.append(title, meta, group);
  const actions = document.createElement("div");
  actions.className = "session-actions";
  const manifestButton = iconButton("i-download", "Descargar manifiesto");
  manifestButton.addEventListener("click", () => {
    downloadJSON(sessionManifest(session), `${safeFileName(session.session_id)}-manifest.json`);
  });
  const archiveButton = iconButton("i-folder", "Descargar sesión TAR");
  archiveButton.addEventListener("click", async () => {
    try {
      const tar = await buildSessionTar(session);
      downloadBlob(tar, `${safeFileName(session.session_id)}.tar`);
    } catch (error) {
      showToast(error.message);
    }
  });
  actions.append(manifestButton, archiveButton);
  row.append(content, actions);
  return row;
}

function iconButton(iconID, title) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "icon-button";
  button.title = title;
  button.setAttribute("aria-label", title);
  button.innerHTML = `<svg class="icon"><use href="#${iconID}"/></svg>`;
  return button;
}

function fillComparisonSelectors(sessions) {
  for (const id of ["compare-left", "compare-right"]) {
    const select = element(id);
    select.replaceChildren();
    for (const session of sessions) {
      const option = document.createElement("option");
      option.value = session.session_id;
      option.textContent = `${session.capture.tree_id} · ${shortID(session.session_id)}`;
      select.append(option);
    }
  }
  if (sessions.length > 1) element("compare-right").selectedIndex = 1;
  element("compare-sessions").disabled = sessions.length < 2;
}

async function renderComparison() {
  const sessions = await listStoredSessions(state.database);
  const left = sessions.find((session) => session.session_id === element("compare-left").value);
  const right = sessions.find((session) => session.session_id === element("compare-right").value);
  try {
    const comparison = compareSessions(left, right);
    const target = element("comparison-result");
    target.hidden = false;
    target.replaceChildren(resultBlock("Estado", "Comparación disponible", comparison.interpretation));
    for (const [field, difference] of Object.entries(comparison.differences)) {
      if (!difference) continue;
      target.append(resultBlock(
        comparisonLabel(field),
        signedNumber(difference.delta),
        `A ${formatNumber(difference.left)} · B ${formatNumber(difference.right)}`,
      ));
    }
    const download = document.createElement("button");
    download.className = "secondary-button";
    download.type = "button";
    download.textContent = "Descargar comparación";
    download.addEventListener("click", () => downloadJSON(comparison, "comparacion-sesiones.json"));
    const block = document.createElement("div");
    block.className = "result-block";
    block.append(download);
    target.append(block);
  } catch (error) {
    showToast(error.message);
  }
}

function calculateBiomass(event) {
  event.preventDefault();
  const result = estimateBiomassCarbon({
    basalDiameterCM: optionalNumber("biomass-db"),
    measurementHeightM: optionalNumber("biomass-height"),
    diameterUncertaintyCM: optionalNumber("biomass-uncertainty"),
    diameterSource: element("biomass-source").value,
    lidarValidationStatus: element("biomass-lidar-validation").value,
    cultivar: element("biomass-cultivar").value,
    trainingSystem: element("biomass-vase").checked ? "vase" : "",
    waterRegime: element("biomass-rainfed").checked ? "traditional_rainfed" : "",
    orchardDensityTreesPerHa: optionalNumber("biomass-density"),
    carbonFraction: optionalNumber("biomass-carbon-fraction"),
    carbonFractionSource: element("biomass-carbon-source").value,
    carbonFractionIsProxy: element("biomass-proxy").checked,
  });
  state.lastEstimate = result;
  renderBiomassResult(result);
}

function renderBiomassResult(result) {
  const target = element("biomass-result");
  target.hidden = false;
  target.replaceChildren();
  if (!result.available) {
    const block = document.createElement("div");
    block.className = "result-block";
    const heading = document.createElement("h3");
    heading.textContent = "Estimación no disponible";
    const list = document.createElement("ul");
    list.className = "result-list";
    for (const reason of result.reasons) {
      const item = document.createElement("li");
      item.textContent = reason;
      list.append(item);
    }
    block.append(heading, list);
    target.append(block);
    return;
  }
  const grid = document.createElement("div");
  grid.className = "result-grid";
  grid.append(
    resultBlock("Biomasa seca aérea", `${formatNumber(result.abovegroundDryBiomassKG)} kg`, sensitivityText(result.biomassSensitivityKG, "kg")),
    resultBlock("Carbono almacenado", `${formatNumber(result.storedCarbonKG)} kg C`, sensitivityText(result.storedCarbonSensitivityKG, "kg C")),
    resultBlock("CO2e almacenado", `${formatNumber(result.storedCO2EquivalentKG)} kg CO2e`, sensitivityText(result.storedCO2EquivalentSensitivityKG, "kg CO2e")),
  );
  target.append(grid);
  target.append(resultBlock("Estado", "Estimación experimental", "Pendiente de calibración local. Stock, no absorción anual."));
  if (result.warnings.length > 0) {
    target.append(resultBlock("Límites", result.warnings.join(" "), result.model.equation));
  }
  const controls = document.createElement("div");
  controls.className = "result-block action-row";
  const download = document.createElement("button");
  download.className = "secondary-button";
  download.type = "button";
  download.textContent = "Descargar resultado";
  download.addEventListener("click", () => downloadJSON(result, "estimacion-biomasa-carbono.json"));
  controls.append(download);
  if (state.activeSession) {
    const save = document.createElement("button");
    save.className = "secondary-button";
    save.type = "button";
    save.textContent = "Guardar en sesión activa";
    save.addEventListener("click", saveEstimateToActiveSession);
    controls.append(save);
  }
  target.append(controls);
}

async function saveEstimateToActiveSession() {
  if (!state.activeSession || !state.lastEstimate) return;
  state.activeSession = addEstimate(state.activeSession, state.lastEstimate);
  await persistActiveSession();
  showToast("Estimación guardada por separado dentro de la sesión.");
}

function useActiveGeometry() {
  const geometry = state.activeSession?.manual_geometry;
  if (!geometry?.basal_diameter_cm) return showToast("La sesión activa no tiene diámetro basal manual.");
  element("biomass-db").value = formatInputNumber(geometry.basal_diameter_cm);
  element("biomass-height").value = "0,30";
  element("biomass-uncertainty").value = geometry.diameter_uncertainty_cm === null
    ? ""
    : formatInputNumber(geometry.diameter_uncertainty_cm);
  element("biomass-source").value = "manual_tape";
  updateLidarValidationField();
}

function updateLidarValidationField() {
  const target = element("lidar-validation-field");
  const visible = element("biomass-source").value === "lidar";
  target.hidden = !visible;
  target.style.display = visible ? "" : "none";
}

function resultBlock(title, value, detail = "") {
  const block = document.createElement("div");
  block.className = "result-block";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const main = document.createElement("p");
  main.className = "result-value";
  main.textContent = value;
  block.append(heading, main);
  if (detail) {
    const supporting = document.createElement("p");
    supporting.className = "result-detail";
    supporting.textContent = detail;
    block.append(supporting);
  }
  return block;
}

function requiredNumber(id, label) {
  const value = optionalNumber(id);
  if (value === null) throw new Error(`${label} debe ser un número.`);
  return value;
}

function optionalNumber(id) {
  return parseLocaleNumber(element(id).value);
}

function formatNumber(value) {
  return value.toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatInputNumber(value) {
  return String(value).replace(".", ",");
}

function sensitivityText(range, unit) {
  return range ? `Sensibilidad DB: ${formatNumber(range[0])} - ${formatNumber(range[1])} ${unit}` : "Sin rango de sensibilidad calculado";
}

function comparisonLabel(field) {
  return ({
    basal_diameter_cm: "Diámetro basal (cm)",
    tree_height_m: "Altura (m)",
    crown_span_x_m: "Copa X (m)",
    crown_span_z_m: "Copa Z (m)",
    vertical_coverage: "Cobertura vertical",
  })[field] ?? field;
}

function signedNumber(value) {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${formatNumber(value)}`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function shortID(value) {
  return value.length > 12 ? value.slice(0, 8) : value;
}

function safeFileName(value) {
  return String(value).replace(/[^a-zA-Z0-9._-]/g, "_");
}

function newID() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().toLowerCase();
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function canvasBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("No se pudo codificar la foto.")), type, quality);
  });
}

function updateConnectivity() {
  const target = element("offline-state");
  target.textContent = navigator.onLine ? "Local listo" : "Sin red · local";
  target.dataset.state = "ready";
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  try {
    await navigator.serviceWorker.register("./service-worker.js", { scope: "./" });
  } catch (error) {
    showToast(`Modo offline no registrado: ${error.message}`);
  }
}

async function installApplication() {
  if (!state.installPrompt) return;
  await state.installPrompt.prompt();
  state.installPrompt = null;
  element("install-button").hidden = true;
}

function showToast(message) {
  if (!message) return;
  const toast = element("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { toast.hidden = true; }, 4200);
}
