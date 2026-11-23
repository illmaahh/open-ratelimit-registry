import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  RateLimitTracker,
  computeBackoffMs,
  detectProvider,
  fetchWithRateLimit,
  listProviders,
  parseHttpHeadersText,
  parseRateLimit,
} from "../src/index.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REGISTRY = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../src/registry.json"), "utf8")
).providers;

test("validates every example across all 25 registered providers", () => {
  assert.equal(listProviders().length, 25);
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

test("parses RFC 9110 HTTP-date Retry-After headers", () => {
  const nowMs = Date.parse("2026-11-23T14:00:00Z");
  const res = parseRateLimit("slack", { "Retry-After": "Mon, 23 Nov 2026 14:00:10 GMT" }, 429, nowMs);
  assert.equal(res.isLimited, true);
  assert.equal(res.retryAfterMs, 10000);
});

test("RateLimitTracker computes proactive delay and backoff", () => {
  let now = 1795443500000;
  const tracker = new RateLimitTracker(() => now);
  tracker.update("github", { "x-ratelimit-limit": "5000", "x-ratelimit-remaining": "0", "x-ratelimit-reset": "1795443520" }, 200);
  assert.equal(tracker.getDelayMs("github", { minRemaining: 1 }), 20000);
  now += 5000;
  assert.equal(tracker.getDelayMs("github", { minRemaining: 1 }), 15000);
  assert.equal(computeBackoffMs(2, { baseMs: 1000, maxMs: 10000, jitter: "none" }), 4000);
});

test("parses raw curl -si output and auto-detects provider", () => {
  const raw = "HTTP/2 429\r\nretry-after: 12\r\nanthropic-ratelimit-requests-remaining: 0\r\n\r\n{}";
  const { status, headers } = parseHttpHeadersText(raw);
  assert.equal(status, 429);
  assert.equal(detectProvider(headers), "anthropic");
  const res = parseRateLimit(null, headers, status);
  assert.equal(res.retryAfterMs, 12000);
});

test("fetchWithRateLimit retries on 429 and respects Retry-After", async () => {
  let calls = 0;
  const sleeps = [];
  const fakeFetch = async () => {
    calls += 1;
    if (calls === 1) return { status: 429, headers: new Map([["retry-after", "3"]]) };
    return { status: 200, headers: new Map([["ratelimit-limit", "10"], ["ratelimit-remaining", "9"]]) };
  };
  const { response, rateLimit } = await fetchWithRateLimit(
    "https://api.resend.com/emails",
    {},
    { provider: "resend", maxRetries: 2, fetchImpl: fakeFetch, sleepImpl: async (ms) => sleeps.push(ms) }
  );
  assert.equal(calls, 2);
  assert.equal(response.status, 200);
  assert.equal(rateLimit.isLimited, false);
  assert.deepEqual(sleeps, [3000]);
});
