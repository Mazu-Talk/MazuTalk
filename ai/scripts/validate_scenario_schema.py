from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = ROOT_DIR / "ai" / "schemas" / "scenario_schema.json"
DEFAULT_SCENARIO_PATH = (
    ROOT_DIR / "ai" / "schemas" / "examples" / "playground_greeting_001.json"
)


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def format_error_path(error_path: object) -> str:
    parts = [str(part) for part in error_path]
    return ".".join(parts) if parts else "<root>"


def validate(schema_path: Path, scenario_path: Path) -> int:
    schema = load_json(schema_path)
    scenario = load_json(scenario_path)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(scenario), key=lambda error: list(error.path))

    if not errors:
        print(f"OK: {scenario_path} is valid against {schema_path}")
        return 0

    print(f"INVALID: {scenario_path} failed validation against {schema_path}")
    for error in errors:
        print(f"- {format_error_path(error.path)}: {error.message}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a MazuTalk scenario JSON file.")
    parser.add_argument(
        "scenario",
        nargs="?",
        type=Path,
        default=DEFAULT_SCENARIO_PATH,
        help="Path to the scenario JSON file to validate.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="Path to the scenario JSON Schema file.",
    )
    args = parser.parse_args()

    return validate(args.schema, args.scenario)


if __name__ == "__main__":
    raise SystemExit(main())
