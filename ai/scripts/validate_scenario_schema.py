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


def validate_file(schema: object, schema_path: Path, scenario_path: Path) -> list[str]:
    scenario = load_json(scenario_path)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(scenario), key=lambda error: list(error.path))

    if not errors:
        return []

    messages = [
        f"INVALID: {scenario_path} failed validation against {schema_path}",
    ]
    for error in errors:
        messages.append(f"- {format_error_path(error.path)}: {error.message}")
    return messages


def iter_scenario_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.rglob("*.json"))
    return [path]


def validate(schema_path: Path, scenario_path: Path) -> int:
    schema = load_json(schema_path)
    scenario_files = iter_scenario_files(scenario_path)

    if not scenario_files:
        print(f"INVALID: no JSON files found under {scenario_path}")
        return 1

    failures: list[str] = []
    for scenario_file in scenario_files:
        failures.extend(validate_file(schema, schema_path, scenario_file))

    if not failures:
        print(
            f"OK: {len(scenario_files)} scenario file(s) are valid against {schema_path}"
        )
        return 0

    for failure in failures:
        print(failure)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a MazuTalk scenario JSON file.")
    parser.add_argument(
        "scenario",
        nargs="?",
        type=Path,
        default=DEFAULT_SCENARIO_PATH,
        help="Path to a scenario JSON file or a directory containing scenario JSON files.",
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
