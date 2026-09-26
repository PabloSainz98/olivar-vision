import assert from "node:assert/strict";
import test from "node:test";
import { webcrypto } from "node:crypto";

import { detectWebCapabilities, probeXRDepth } from "../src/capabilities.mjs";
import { buildSessionTar, sha256Hex } from "../src/export-session.mjs";
import { appendPhoto, createSession, finalizeSession } from "../src/session-contract.mjs";

test("capability detection reports missing APIs without simulating LiDAR", async () => {
  const result = await detectWebCapabilities({ navigator: {}, isSecureContext: false });
  assert.equal(result.status, "web_limited");
  assert.equal(result.camera_api, false);
  assert.equal(result.immersive_ar, false);
  assert.equal(result.arkit_scene_depth, "UNAVAILABLE_OUTSIDE_NATIVE_ARKIT");
  assert.match(result.reason, /HTTPS/);
});

test("WebXR depth probe requests the real required feature", async () => {
  let options;
  const session = { end: async () => {} };
  const result = await probeXRDepth({
    navigator: {
      xr: {
        requestSession: async (_mode, received) => {
          options = received;
          return session;
        },
      },
    },
  });
  assert.equal(result.status, "SUPPORTED_BY_WEBXR_SESSION");
  assert.deepEqual(options.requiredFeatures, ["depth-sensing"]);
});

test("session TAR contains a clean manifest and preserved photo bytes", async () => {
  const photo = new Blob([new Uint8Array([11, 12, 13])], { type: "image/jpeg" });
  let session = createSession({
    sessionID: "session-export",
    repeatGroupID: "repeat-1",
    context: { treeID: "tree", operatorID: "operator", siteID: "site" },
    capabilities: { camera_api: true },
    createdAt: "2026-09-26T10:00:00.000Z",
    userAgent: "test",
  });
  session = appendPhoto(session, {
    id: "frame-000001",
    timestampMS: 1,
    width: 1,
    height: 1,
    mimeType: "image/jpeg",
    sizeBytes: photo.size,
    sha256: await sha256Hex(photo, webcrypto),
    blob: photo,
  });
  session = finalizeSession(session);
  const tar = new Uint8Array(await (await buildSessionTar(session)).arrayBuffer());
  const entries = parseTar(tar);

  assert.deepEqual([...entries.keys()], [
    "session-export/session.json",
    "session-export/captured/frame-000001/color.jpg",
  ]);
  const manifest = JSON.parse(new TextDecoder().decode(entries.get("session-export/session.json")));
  assert.equal(manifest.photos[0].blob, undefined);
  assert.deepEqual([...entries.get("session-export/captured/frame-000001/color.jpg")], [11, 12, 13]);
});

function parseTar(bytes) {
  const entries = new Map();
  let offset = 0;
  while (offset + 512 <= bytes.length) {
    const header = bytes.slice(offset, offset + 512);
    if (header.every((byte) => byte === 0)) break;
    const name = readString(header.slice(0, 100));
    const size = Number.parseInt(readString(header.slice(124, 136)).trim(), 8);
    const start = offset + 512;
    entries.set(name, bytes.slice(start, start + size));
    offset = start + Math.ceil(size / 512) * 512;
  }
  return entries;
}

function readString(bytes) {
  const zero = bytes.indexOf(0);
  return new TextDecoder().decode(zero >= 0 ? bytes.slice(0, zero) : bytes);
}
