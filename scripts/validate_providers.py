import json
import pathlib
import re
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROVIDERS_DIR = ROOT / "providers"
SCHEMA_PATH = ROOT / "schema" / "provider.schema.json"

try:
    import jsonschema
except ImportError:
    jsonschema = None


def validate_all() -> list[dict]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema) if jsonschema else None

    specs = []
    seen_ids: set[str] = set()
    seen_detect_headers: dict[str, str] = {}

    for path in sorted(PROVIDERS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: must be a YAML mapping")

        if validator is not None:
            errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
            if errors:
                err = errors[0]
                loc = ".".join(str(x) for x in err.path) or "<root>"
                raise ValueError(f"{path.name} [{loc}]: {err.message}")
        else:
            for field in schema["required"]:
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

        for h in data.get("detect_headers", []):
            key = h.lower()
            if key in seen_detect_headers:
                raise ValueError(
                    f"{path.name}: detect_header '{key}' collides with '{seen_detect_headers[key]}'"
                )
            seen_detect_headers[key] = pid

        specs.append(data)

    return specs


if __name__ == "__main__":
    specs = validate_all()
    mode = "JSON Schema (Draft 2020-12)" if jsonschema else "basic"
    print(f"Validated {len(specs)} provider specs ({mode}) with zero header collisions.")
