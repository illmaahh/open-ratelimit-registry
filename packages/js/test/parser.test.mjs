import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { detectProvider, listProviders, parseRateLimit } from "../src/index.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REGISTRY = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../src/registry.json"), "utf8")
).providers;

test("validates every example across all registered providers", () => {
  assert.ok(listProviders().length >= 8);
  for (const [pid, spec] of Object.entries(REGISTRY)) {
    for (const ex of spec.examples) {
      const res = parseRateLimit(pid, ex.headers, ex.status, 1795443500000);
      assert.equal(res.isLimited, ex.expected.is_limited, `${pid}: ${ex.description}`);
      assert.equal(res.limit, ex.expected.limit ?? null, `${pid}: ${ex.description}`);
      assert.equal(res.remaining, ex.expected.remaining ?? null, `${pid}: ${ex.description}`);
      assert.equal(res.retryAfterMs, ex.expected.retry_after_ms ?? null, `${pid}: ${ex.description}`);
    }
  }
});

test("detects providers automatically from response headers", () => {
  assert.equal(detectProvider({ "Anthropic-RateLimit-Requests-Remaining": "5" }), "anthropic");
  assert.equal(detectProvider({ "X-Shopify-Shop-Api-Call-Limit": "40/40" }), "shopify");
});
