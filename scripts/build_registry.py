import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate_providers import validate_all

TARGETS = [
    ROOT / "packages" / "python" / "open_ratelimit_registry" / "registry.json",
    ROOT / "packages" / "js" / "src" / "registry.json",
]


def build():
    specs = validate_all()
    bundle = {
        "version": "0.1.0",
        "providers": {spec["id"]: spec for spec in specs},
    }
    payload = json.dumps(bundle, indent=2, ensure_ascii=False) + "\n"
    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
        print(f"Wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
