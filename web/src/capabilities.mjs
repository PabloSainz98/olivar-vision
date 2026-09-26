export async function detectWebCapabilities(environment = globalThis) {
  const navigatorObject = environment.navigator ?? {};
  const secureContext = environment.isSecureContext === true;
  const cameraAPI = typeof navigatorObject.mediaDevices?.getUserMedia === "function";
  const webXRAPI = typeof navigatorObject.xr?.isSessionSupported === "function";
  let immersiveAR = false;
  let xrReason = webXRAPI ? null : "El navegador no expone navigator.xr.";

  if (webXRAPI) {
    try {
      immersiveAR = await navigatorObject.xr.isSessionSupported("immersive-ar");
      if (!immersiveAR) xrReason = "El navegador no admite sesiones immersive-ar.";
    } catch (error) {
      xrReason = `No se pudo consultar WebXR: ${error.message}`;
    }
  }

  return {
    status: cameraAPI && secureContext ? "web_ready" : "web_limited",
    secure_context: secureContext,
    camera_api: cameraAPI,
    indexed_db: "indexedDB" in environment,
    service_worker: "serviceWorker" in navigatorObject,
    web_share: typeof navigatorObject.share === "function",
    webxr_api: webXRAPI,
    immersive_ar: immersiveAR,
    xr_depth_sensing: immersiveAR ? "NOT_PROBED" : "UNAVAILABLE",
    lidar_depth_camera: "NOT_EXPOSED_BY_STANDARD_CAMERA_API",
    arkit_scene_depth: "UNAVAILABLE_OUTSIDE_NATIVE_ARKIT",
    reason: capabilityReason({ secureContext, cameraAPI }),
    xr_reason: xrReason,
  };
}

export async function probeXRDepth(environment = globalThis) {
  const xr = environment.navigator?.xr;
  if (!xr || typeof xr.requestSession !== "function") {
    return {
      status: "UNAVAILABLE",
      reason: "El navegador no expone WebXR.",
    };
  }
  let session;
  try {
    session = await xr.requestSession("immersive-ar", {
      requiredFeatures: ["depth-sensing"],
      depthSensing: {
        usagePreference: ["cpu-optimized"],
        dataFormatPreference: ["float32", "luminance-alpha"],
      },
    });
    return {
      status: "SUPPORTED_BY_WEBXR_SESSION",
      reason: null,
    };
  } catch (error) {
    return {
      status: "UNAVAILABLE",
      reason: `${error.name ?? "Error"}: ${error.message ?? "sesion rechazada"}`,
    };
  } finally {
    if (session) await session.end();
  }
}

function capabilityReason({ secureContext, cameraAPI }) {
  const reasons = [];
  if (!secureContext) reasons.push("La camara web requiere HTTPS o localhost.");
  if (!cameraAPI) reasons.push("El navegador no expone getUserMedia.");
  return reasons.length > 0 ? reasons.join(" ") : null;
}
