import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REGISTRY = JSON.parse(fs.readFileSync(path.join(__dirname, "registry.json"), "utf8")).providers;

function normalizeHeaders(headers) {
  const out = {};
  if (!headers) return out;
  const entries = typeof headers.entries === "function" ? headers.entries() : Object.entries(headers);
  for (const [k, v] of entries) {
    if (v !== undefined && v !== null) out[String(k).toLowerCase()] = String(v).trim();
  }
  return out;
}

function parseIntSafe(val) {
  if (val === undefined || val === null || val === "") return null;
  const n = Number(val);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

function parseDurationMs(val) {
  const re = /(\d+(?:\.\d+)?)(ms|s|m|h|d)/gi;
  let total = 0;
  let matched = false;
  for (const m of val.matchAll(re)) {
    matched = true;
    const amt = Number(m[1]);
    const unit = m[2].toLowerCase();
    if (unit === "ms") total += amt;
    else if (unit === "s") total += amt * 1000;
    else if (unit === "m") total += amt * 60000;
    else if (unit === "h") total += amt * 3600000;
    else if (unit === "d") total += amt * 86400000;
  }
  return matched ? Math.round(total) : null;
}

function parseReset(raw, format, nowMs) {
  if (!raw || format === "none") return { resetAfterMs: null, resetAt: null };
  if (format === "epoch_milliseconds") {
    const ms = parseIntSafe(raw);
    if (ms === null) return { resetAfterMs: null, resetAt: null };
    return {
      resetAfterMs: Math.max(0, ms - nowMs),
      resetAt: new Date(ms).toISOString(),
    };
  }
  if (format === "epoch_seconds") {
    const sec = parseIntSafe(raw);
    if (sec === null) return { resetAfterMs: null, resetAt: null };
    return {
      resetAfterMs: Math.max(0, sec * 1000 - nowMs),
      resetAt: new Date(sec * 1000).toISOString(),
    };
  }
  if (format === "delta_seconds") {
    const sec = parseIntSafe(raw);
    if (sec === null) return { resetAfterMs: null, resetAt: null };
    const ms = Math.max(0, sec * 1000);
    return { resetAfterMs: ms, resetAt: new Date(nowMs + ms).toISOString() };
  }
  if (format === "rfc3339") {
    const t = Date.parse(raw);
    if (Number.isNaN(t)) return { resetAfterMs: null, resetAt: null };
    return { resetAfterMs: Math.max(0, t - nowMs), resetAt: new Date(t).toISOString() };
  }
  if (format === "duration_string") {
    const ms = parseDurationMs(raw);
    if (ms === null) return { resetAfterMs: null, resetAt: null };
    return { resetAfterMs: ms, resetAt: new Date(nowMs + ms).toISOString() };
  }
  return { resetAfterMs: null, resetAt: null };
}

export function listProviders() {
  return Object.keys(REGISTRY).sort();
}

export function getProvider(id) {
  return REGISTRY[String(id).toLowerCase()] ?? null;
}

export function detectProvider(headers) {
  const norm = normalizeHeaders(headers);
  for (const [pid, spec] of Object.entries(REGISTRY)) {
    for (const hint of spec.detect_headers ?? []) {
      if (hint.toLowerCase() in norm) return pid;
    }
  }
  return null;
}

export function parseRateLimit(provider, headers, status = 200, nowMs = Date.now()) {
  const norm = normalizeHeaders(headers);
  const pid = provider ? String(provider).toLowerCase() : detectProvider(norm);
  const spec = pid ? REGISTRY[pid] ?? null : null;

  if (!spec) {
    const retrySec = parseIntSafe(norm["retry-after"]);
    const isLimited = status === 429;
    return {
      provider: pid,
      isLimited,
      limit: null,
      remaining: null,
      resetAfterMs: null,
      resetAt: null,
      retryAfterMs: isLimited ? (retrySec !== null ? retrySec * 1000 : 5000) : null,
      strategy: "exponential_backoff_jitter",
      buckets: {},
    };
  }

  const buckets = {};
  let primaryLimit = null;
  let primaryRemaining = null;
  let primaryResetMs = null;
  let primaryResetAt = null;

  for (const b of spec.buckets ?? []) {
    const state = {
      name: b.name,
      unit: b.unit,
      limit: null,
      remaining: null,
      used: null,
      resetAfterMs: null,
      resetAt: null,
    };

    if (b.format === "triplet") {
      state.limit = parseIntSafe(norm[(b.limit_header ?? "").toLowerCase()]);
      state.remaining = parseIntSafe(norm[(b.remaining_header ?? "").toLowerCase()]);
      if (state.limit !== null && state.remaining !== null) {
        state.used = Math.max(0, state.limit - state.remaining);
      }
      const { resetAfterMs, resetAt } = parseReset(
        norm[(b.reset_header ?? "").toLowerCase()],
        b.reset_format ?? "none",
        nowMs
      );
      state.resetAfterMs = resetAfterMs;
      state.resetAt = resetAt;
    } else if (b.format === "ratio") {
      const raw = norm[(b.ratio_header ?? "").toLowerCase()] ?? "";
      if (raw.includes("/")) {
        const [u, l] = raw.split("/", 2);
        const used = parseIntSafe(u);
        const limit = parseIntSafe(l);
        if (used !== null && limit !== null) {
          state.used = used;
          state.limit = limit;
          state.remaining = Math.max(0, limit - used);
        }
      }
    } else if (b.format === "ietf_structured") {
      const rlRaw = norm[(b.structured_header ?? "").toLowerCase()] ?? "";
      const polRaw = norm[(b.policy_header ?? "").toLowerCase()] ?? "";
      const rMatch = rlRaw.match(/\br=(\d+)/);
      const tMatch = rlRaw.match(/\bt=(\d+)/);
      const qMatch = polRaw.match(/\bq=(\d+)/);
      state.remaining = rMatch ? Number(rMatch[1]) : null;
      state.limit = qMatch ? Number(qMatch[1]) : null;
      if (state.limit !== null && state.remaining !== null) {
        state.used = Math.max(0, state.limit - state.remaining);
      }
      if (tMatch) {
        const { resetAfterMs, resetAt } = parseReset(tMatch[1], "delta_seconds", nowMs);
        state.resetAfterMs = resetAfterMs;
        state.resetAt = resetAt;
      }
    }

    if (state.limit !== null || state.remaining !== null || state.resetAfterMs !== null) {
      buckets[b.name] = state;
      if (primaryLimit === null && state.limit !== null) primaryLimit = state.limit;
      if (primaryRemaining === null && state.remaining !== null) primaryRemaining = state.remaining;
      if (primaryResetMs === null && state.resetAfterMs !== null) {
        primaryResetMs = state.resetAfterMs;
        primaryResetAt = state.resetAt;
      }
    }
  }

  const retryCfg = spec.retry;
  const retryHeader = (retryCfg.retry_after_header ?? "retry-after").toLowerCase();
  const retryRaw = norm[retryHeader];
  let retryAfterMs = null;
  if (retryRaw !== undefined && retryRaw !== "") {
    const n = Number(retryRaw);
    if (Number.isFinite(n)) retryAfterMs = Math.max(0, Math.round(n * 1000));
  }

  let isLimited = retryCfg.status_codes.includes(status);
  if (pid === "github" && status === 403) {
    isLimited = primaryRemaining === 0 || retryAfterMs !== null;
  }

  if (isLimited && retryAfterMs === null) {
    retryAfterMs =
      retryCfg.strategy === "wait_until_reset" && primaryResetMs !== null
        ? primaryResetMs
        : retryCfg.default_backoff_ms ?? 1000;
  }

  return {
    provider: pid,
    isLimited,
    limit: primaryLimit,
    remaining: primaryRemaining,
    resetAfterMs: primaryResetMs,
    resetAt: primaryResetAt,
    retryAfterMs: isLimited ? retryAfterMs : null,
    strategy: retryCfg.strategy,
    buckets,
  };
}
