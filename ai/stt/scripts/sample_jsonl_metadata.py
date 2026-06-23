from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]

FIELDNAMES = [
    "file_name",
    "audio_path",
    "text",
    "speaker_id",
    "duration_sec",
    "split",
    "source_json",
]


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def display_path(path: str | Path) -> str:
    path = Path(path).resolve()
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample metadata CSV rows from speech_analysis_dataset.jsonl.",
    )
    parser.add_argument("--input", default="ai/data/processed/stt/speech_analysis_dataset.jsonl")
    parser.add_argument("--output", default="ai/data/processed/stt/metadata_smoke_100.csv")
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def row_from_record(record: dict[str, Any]) -> dict[str, str]:
    audio = record["audio"]
    speaker = record["speaker"]
    transcription = record["transcription"]
    training = record["training"]
    source = record["source"]
    return {
        "file_name": audio["file_name"],
        "audio_path": training["input_audio_path"],
        "text": transcription["text"],
        "speaker_id": speaker["speaker_name"] or speaker["speaker_id"],
        "duration_sec": str(audio["speech_duration_sec"] or audio["file_duration_sec"] or ""),
        "split": training["split"],
        "source_json": source["label_path"],
    }


def main() -> None:
    args = parse_args()
    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output)

    candidates: list[dict[str, str]] = []
    with input_path.open("r", encoding="utf-8") as file:
        for line in file:
            record = json.loads(line)
            if record["training"]["split"] != args.split:
                continue
            if not record["quality"]["usable_for_training"]:
                continue
            candidates.append(row_from_record(record))

    rng = random.Random(args.seed)
    rng.shuffle(candidates)
    rows = candidates[: args.limit]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"candidates: {len(candidates)}")
    print(f"sampled: {len(rows)}")
    print(f"output: {display_path(output_path)}")


if __name__ == "__main__":
    main()
