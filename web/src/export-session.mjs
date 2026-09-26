import { sessionManifest } from "./session-contract.mjs";

const TAR_BLOCK_SIZE = 512;

export async function sha256Hex(blob, cryptoObject = globalThis.crypto) {
  if (!cryptoObject?.subtle) throw new Error("Web Crypto SHA-256 no esta disponible.");
  const digest = await cryptoObject.subtle.digest("SHA-256", await blob.arrayBuffer());
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function buildSessionTar(session) {
  const files = [];
  const manifest = JSON.stringify(sessionManifest(session), null, 2) + "\n";
  files.push({
    path: `${safeSegment(session.session_id)}/session.json`,
    bytes: new TextEncoder().encode(manifest),
  });
  for (const photo of session.photos) {
    if (!(photo.blob instanceof Blob)) continue;
    files.push({
      path: `${safeSegment(session.session_id)}/${photo.path}`,
      bytes: new Uint8Array(await photo.blob.arrayBuffer()),
    });
  }
  const parts = [];
  for (const file of files) {
    parts.push(tarHeader(file.path, file.bytes.byteLength));
    parts.push(file.bytes);
    const remainder = file.bytes.byteLength % TAR_BLOCK_SIZE;
    if (remainder !== 0) parts.push(new Uint8Array(TAR_BLOCK_SIZE - remainder));
  }
  parts.push(new Uint8Array(TAR_BLOCK_SIZE * 2));
  return new Blob(parts, { type: "application/x-tar" });
}

export function downloadBlob(blob, fileName, documentObject = globalThis.document) {
  const anchor = documentObject.createElement("a");
  const url = URL.createObjectURL(blob);
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadJSON(value, fileName, documentObject = globalThis.document) {
  const data = JSON.stringify(value, null, 2) + "\n";
  downloadBlob(new Blob([data], { type: "application/json" }), fileName, documentObject);
}

function tarHeader(path, size) {
  const encoded = new TextEncoder().encode(path);
  if (encoded.byteLength > 100) throw new Error(`La ruta TAR supera 100 bytes: ${path}`);
  const header = new Uint8Array(TAR_BLOCK_SIZE);
  writeBytes(header, 0, encoded);
  writeOctal(header, 100, 8, 0o644);
  writeOctal(header, 108, 8, 0);
  writeOctal(header, 116, 8, 0);
  writeOctal(header, 124, 12, size);
  writeOctal(header, 136, 12, Math.floor(Date.now() / 1000));
  header.fill(0x20, 148, 156);
  header[156] = "0".charCodeAt(0);
  writeText(header, 257, "ustar\0");
  writeText(header, 263, "00");
  writeText(header, 265, "olivar");
  writeText(header, 297, "olivar");
  const checksum = header.reduce((sum, byte) => sum + byte, 0);
  const checksumText = checksum.toString(8).padStart(6, "0");
  writeText(header, 148, checksumText);
  header[154] = 0;
  header[155] = 0x20;
  return header;
}

function writeOctal(target, offset, length, value) {
  const text = value.toString(8).padStart(length - 1, "0") + "\0";
  writeText(target, offset, text.slice(-length));
}

function writeText(target, offset, value) {
  writeBytes(target, offset, new TextEncoder().encode(value));
}

function writeBytes(target, offset, bytes) {
  target.set(bytes, offset);
}

function safeSegment(value) {
  return String(value).replace(/[^a-zA-Z0-9._-]/g, "_");
}
