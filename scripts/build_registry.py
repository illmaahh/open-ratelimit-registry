import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate_providers import validate_all

TARGETS = [
    ROOT / "packages" / "python" / "open_ratelimit_registry" / "registry.json",
    ROOT / "packages" / "js" / "src" / "registry.json",
]
README_PATH = ROOT / "README.md"


def render_providers_table(specs: list[dict]) -> str:
    lines = [
        f"Currently tracking **{len(specs)} API providers**:",
        "",
        "| Provider | ID | Format | Reset Format | Retry Strategy | Docs |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for s in specs:
        buckets = s.get("buckets", [])
        fmt = ", ".join(sorted({b["format"] for b in buckets})) if buckets else "retry-after only"
        resets = sorted({b.get("reset_format", "none") for b in buckets if b.get("reset_format", "none") != "none"})
        reset_str = ", ".join(f"`{r}`" for r in resets) if resets else "`retry-after`"
        strat = f"`{s['retry']['strategy']}`"
        lines.append(
            f"| {s['name']} | `{s['id']}` | `{fmt}` | {reset_str} | {strat} | [Docs]({s['source_url']}) |"
        )
    return "\n".join(lines)


def update_readme(specs: list[dict]) -> None:
    if not README_PATH.exists():
        return
    text = README_PATH.read_text(encoding="utf-8")
    table = render_providers_table(specs)
    updated = re.sub(
        r"<!-- PROVIDERS:START -->.*?<!-- PROVIDERS:END -->",
        f"<!-- PROVIDERS:START -->\n{table}\n<!-- PROVIDERS:END -->",
        text,
        flags=re.S,
    )
    README_PATH.write_text(updated, encoding="utf-8")
    print("Updated README.md providers table")


def build():
    specs = validate_all()
    bundle = {
        "version": "2.0.0",
        "providers": {spec["id"]: spec for spec in specs},
    }
    payload = json.dumps(bundle, indent=2, ensure_ascii=False) + "\n"
    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
        print(f"Wrote {target.relative_to(ROOT)}")
    update_readme(specs)


if __name__ == "__main__":
    build()
