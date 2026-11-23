import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "python"))
from open_ratelimit_registry import parse_rate_limit

NOW_MS = 1795443500000
reg = json.loads((ROOT / "packages" / "python" / "open_ratelimit_registry" / "registry.json").read_text(encoding="utf-8"))["providers"]

js_script = f'''
import {{ parseRateLimit }} from "./packages/js/src/index.mjs";
import fs from "node:fs";
const reg = JSON.parse(fs.readFileSync("./packages/js/src/registry.json", "utf8")).providers;
const out = {{}};
for (const [pid, spec] of Object.entries(reg)) {{
  out[pid] = spec.examples.map((ex) => parseRateLimit(pid, ex.headers, ex.status, {NOW_MS}));
}}
console.log(JSON.stringify(out));
'''
js_out = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", js_script], cwd=ROOT, text=True))

checked = 0
for pid, spec in reg.items():
    for idx, ex in enumerate(spec["examples"]):
        py_res = parse_rate_limit(pid, ex["headers"], status=ex["status"], now_ms=NOW_MS)
        js_res = js_out[pid][idx]
        assert py_res.is_limited == js_res["isLimited"], f"{pid}[{idx}] is_limited mismatch"
        assert py_res.limit == js_res["limit"], f"{pid}[{idx}] limit mismatch"
        assert py_res.remaining == js_res["remaining"], f"{pid}[{idx}] remaining mismatch"
        assert py_res.retry_after_ms == js_res["retryAfterMs"], f"{pid}[{idx}] retry_after_ms mismatch"
        assert py_res.reset_after_ms == js_res["resetAfterMs"], f"{pid}[{idx}] reset_after_ms mismatch"
        checked += 1

print(f"Cross-language Python/JS parity verified across {len(reg)} providers ({checked} test cases).")
