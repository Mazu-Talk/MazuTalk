"""Run OpenAI Whisper over metadata.csv.

Example:
    python ai/stt/scripts/run_whisper.py --metadata ai/data/processed/stt/metadata.csv --limit 50
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_METADATA = "ai/data/processed/stt/metadata.csv"
DEFAULT_OUTPUT = "ai/stt/results/whisper_result.csv"

FIELDNAMES = ["file_name", "audio_path", "ground_truth", "whisper_text", "whisper_time_sec"]


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def csv_path(path: str | Path) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenAI Whisper transcription for STT metadata rows.")
    parser.add_argument("--metadata", default=DEFAULT_METADATA)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default="ko")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def read_metadata(path: Path, limit: int | None) -> list[dict[str, str]]:
    if not path.exists():
        print(f"Metadata file not found: {csv_path(path)}", file=sys.stderr)
        print("Run this first:", file=sys.stderr)
        print("  python ai/stt/scripts/build_dataset.py", file=sys.stderr)
        raise SystemExit(1)

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return rows[:limit] if limit is not None else rows


def load_whisper_model(model_name: str, device: str):
    try:
        import whisper
    except ImportError as exc:
        print("OpenAI Whisper is not installed.", file=sys.stderr)
        print("Install dependencies with:", file=sys.stderr)
        print("  source .venv/bin/activate && pip install -r ai/stt/requirements.txt", file=sys.stderr)
        raise SystemExit(1) from exc
    return whisper.load_model(model_name, device=device)


def main() -> None:
    args = parse_args()
    metadata_path = resolve_path(args.metadata)
    output_path = resolve_path(args.output)

    rows = read_metadata(metadata_path, args.limit)
    runnable_rows: list[dict[str, str]] = []
    skipped_missing = 0
    for row in rows:
        audio_path = resolve_path(row.get("audio_path", ""))
        if not audio_path.exists():
            skipped_missing += 1
            print(f"[skip] wav not found: {csv_path(audio_path)}")
            continue
        runnable_rows.append(row)

    results: list[dict[str, str]] = []
    if runnable_rows:
        model = load_whisper_model(args.model, args.device)
        for row in runnable_rows:
            audio_path = resolve_path(row["audio_path"])
            started = time.perf_counter()
            result = model.transcribe(
                str(audio_path),
                language=args.language,
                fp16=args.device != "cpu",
            )
            elapsed = time.perf_counter() - started
            results.append(
                {
                    "file_name": row.get("file_name", audio_path.name),
                    "audio_path": row.get("audio_path", csv_path(audio_path)),
                    "ground_truth": row.get("text", ""),
                    "whisper_text": str(result.get("text", "")).strip(),
                    "whisper_time_sec": f"{elapsed:.3f}",
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print(f"Input rows: {len(rows)}")
    print(f"Skipped missing wav: {skipped_missing}")
    print(f"Transcribed rows: {len(results)}")
    print(f"Saved result: {csv_path(output_path)}")


if __name__ == "__main__":
    main()
