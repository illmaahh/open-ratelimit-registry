import json
import pathlib
import re
import sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROVIDERS_DIR = ROOT / "providers"
SCHEMA_PATH = ROOT / "schema" / "provider.schema.json"


def validate_all() -> list[dict]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required_top = schema["required"]
    specs = []
    seen_ids = set()

    for path in sorted(PROVIDERS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: must be a YAML mapping")

        for field in required_top:
            if field not in data:
                raise ValueError(f"{path.name}: missing required field '{field}'")

        pid = data["id"]
        if pid != path.stem:
            raise ValueError(f"{path.name}: id '{pid}' must match filename '{path.stem}'")
        if pid in seen_ids:
            raise ValueError(f"{path.name}: duplicate id '{pid}'")
        seen_ids.add(pid)

        if not re.match(r"^https://", data["source_url"]):
            raise ValueError(f"{path.name}: source_url must start with https://")
        if not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", str(data["last_verified"])):
            raise ValueError(f"{path.name}: last_verified must be YYYY-MM-DD")

        if not data["examples"]:
            raise ValueError(f"{path.name}: at least 1 example is required")

        specs.append(data)

    return specs


if __name__ == "__main__":
    specs = validate_all()
    print(f"Validated {len(specs)} provider specs successfully.")
