#!/usr/bin/env node
import fs from "node:fs";
import {
  VERSION,
  getProvider,
  listProviders,
  parseHttpHeadersText,
  parseRateLimit,
} from "../src/index.mjs";

const args = process.argv.slice(2);
const cmd = args[0];

if (!cmd || cmd === "--help" || cmd === "-h") {
  console.log("Usage: open-ratelimit <list|show <id>|inspect [--provider ID] [--json] [--file PATH]>");
  process.exit(0);
}

if (cmd === "--version" || cmd === "-v") {
  console.log(`open-ratelimit ${VERSION}`);
  process.exit(0);
}

if (cmd === "list") {
  for (const pid of listProviders()) console.log(pid);
  process.exit(0);
}

if (cmd === "show") {
  const id = args[1];
  const spec = id ? getProvider(id) : null;
  if (!spec) {
    console.error(`Unknown provider: ${id ?? ""}`);
    process.exit(1);
  }
  console.log(JSON.stringify(spec, null, 2));
  process.exit(0);
}

if (cmd === "inspect") {
  let provider = null;
  let file = null;
  let asJson = false;
  let statusOverride = null;
  for (let i = 1; i < args.length; i += 1) {
    if (args[i] === "--provider") provider = args[++i];
    else if (args[i] === "--file") file = args[++i];
    else if (args[i] === "--status") statusOverride = Number(args[++i]);
    else if (args[i] === "--json") asJson = true;
  }
  const raw = file ? fs.readFileSync(file, "utf8") : fs.readFileSync(0, "utf8");
  const { status: detectedStatus, headers } = parseHttpHeadersText(raw);
  const status = statusOverride !== null ? statusOverride : detectedStatus;
  const result = parseRateLimit(provider, headers, status);
  if (asJson) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(`Provider   : ${result.provider ?? "unknown"}`);
    console.log(`Limited    : ${result.isLimited ? "YES" : "no"} (HTTP ${status})`);
    console.log(`Quota      : ${result.remaining} / ${result.limit}`);
    if (result.resetAt) console.log(`Reset At   : ${result.resetAt} (${result.resetAfterMs} ms)`);
    if (result.retryAfterMs !== null) console.log(`Retry After: ${result.retryAfterMs} ms (${result.strategy})`);
  }
  process.exit(0);
}

console.error(`Unknown command: ${cmd}`);
process.exit(1);
