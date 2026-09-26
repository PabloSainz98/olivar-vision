import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

test("Pages service worker isolates caches and requests by project scope", async () => {
  const scope = "https://example.github.io/olivar-vision/";
  const prefix = `olivar-vision:${scope}:`;
  const events = {};
  const deleted = [];
  const opened = [];
  const cache = { match: async () => new Response("cached app") };
  vm.runInNewContext(await readFile(new URL("../service-worker.js", import.meta.url), "utf8"), {
    self: {
      registration: { scope },
      clients: { claim: async () => {} },
      skipWaiting() {},
      addEventListener: (name, handler) => { events[name] = handler; },
    },
    caches: {
      keys: async () => ["another-site", `${prefix}v4`, `${prefix}v5`, "olivar-vision:https://example.github.io/other/:v1"],
      delete: async (key) => { deleted.push(key); },
      open: async (key) => { opened.push(key); return cache; },
    },
  });
  let activation;
  events.activate({ waitUntil: (promise) => { activation = promise; } });
  await activation;
  assert.deepEqual(deleted, [`${prefix}v4`]);
  let response;
  events.fetch({
    request: { method: "GET", url: `${scope}index.html` },
    respondWith: (promise) => { response = promise; },
  });
  assert.equal(await (await response).text(), "cached app");
  assert.deepEqual(opened, [`${prefix}v5`]);
  events.fetch({
    request: { method: "GET", url: "https://example.github.io/other/index.html" },
    respondWith: () => assert.fail("must not intercept another Pages project"),
  });
});
