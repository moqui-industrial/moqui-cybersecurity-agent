from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate norm graph IR JSON/JSONL files against their schemas.")
    parser.add_argument("--ir-dir", required=True, help="IR output directory to validate.")
    parser.add_argument("--schema-dir", required=True, help="Directory containing JSON schemas.")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_type(value, schema_type: str) -> bool:
    type_map = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }
    expected = type_map[schema_type]
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, expected)


def validate_value(value, schema: dict, path: str, errors: list[str]) -> None:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if not any(validate_type(value, t) for t in schema_type):
            errors.append(f"{path}: expected one of {schema_type}, found {type(value).__name__}")
            return
    elif schema_type:
        if not validate_type(value, schema_type):
            errors.append(f"{path}: expected {schema_type}, found {type(value).__name__}")
            return

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property '{key}'")
        properties = schema.get("properties", {})
        for key, sub_schema in properties.items():
            if key in value:
                validate_value(value[key], sub_schema, f"{path}.{key}", errors)
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_value(item, item_schema, f"{path}[{index}]", errors)


def validate_jsonl(data_path: Path, schema: dict, label: str, errors: list[str]) -> int:
    count = 0
    with data_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            validate_value(payload, schema, f"{label}:{line_no}", errors)
            count += 1
    return count


def main() -> int:
    args = parse_args()
    ir_dir = Path(args.ir_dir).resolve()
    schema_dir = Path(args.schema_dir).resolve()
    errors: list[str] = []

    schemas = {
        "documents.jsonl": load_json(schema_dir / "document.schema.json"),
        "clauses.jsonl": load_json(schema_dir / "clause.schema.json"),
        "relations.jsonl": load_json(schema_dir / "relation.schema.json"),
        "diagnostics.jsonl": load_json(schema_dir / "diagnostic.schema.json"),
    }

    counts = {}
    for filename, schema in schemas.items():
        data_path = ir_dir / filename
        if not data_path.exists():
            errors.append(f"Missing IR file: {data_path}")
            continue
        counts[filename] = validate_jsonl(data_path, schema, filename, errors)

    for singleton_name in ["project.json", "summary.json"]:
        singleton_path = ir_dir / singleton_name
        if not singleton_path.exists():
            errors.append(f"Missing IR file: {singleton_path}")
        else:
            load_json(singleton_path)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", "counts": counts}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
