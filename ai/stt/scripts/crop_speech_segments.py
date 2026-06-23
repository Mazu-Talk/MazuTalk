from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any

from tqdm import tqdm


REPO_ROOT = Path(__file__).resolve().parents[3]


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
        description="Crop wav files to SpeechStart/SpeechEnd ranges from AI Hub labels.",
    )
    parser.add_argument("--metadata", default="ai/data/processed/stt/metadata_smoke_100.csv")
    parser.add_argument("--output-metadata", default="ai/data/processed/stt/metadata_smoke_100_cropped.csv")
    parser.add_argument("--output-wav-dir", default="ai/data/processed/stt/cropped_smoke_100/wav")
    parser.add_argument("--padding-sec", type=float, default=0.15)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_label(path: str) -> dict[str, Any]:
    with resolve_path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def get_float(data: dict[str, Any], *keys: str) -> float | None:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current in (None, "", "N/A"):
            return None
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def crop_wav(source: Path, target: Path, start_sec: float, duration_sec: float, force: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        return
    cmd = [
        "ffmpeg",
        "-y" if force else "-n",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_sec:.3f}",
        "-t",
        f"{duration_sec:.3f}",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(target),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    metadata = resolve_path(args.metadata)
    output_metadata = resolve_path(args.output_metadata)
    output_wav_dir = resolve_path(args.output_wav_dir)

    rows = read_rows(metadata)
    output_rows: list[dict[str, str]] = []
    skipped = 0
    for row in tqdm(rows, desc="crop"):
        source = resolve_path(row["audio_path"])
        if not source.exists():
            skipped += 1
            continue

        label = load_label(row["source_json"])
        file_duration = get_float(label, "File", "FileLength")
        speech_start = get_float(label, "Miscellaneous_Info", "SpeechStart")
        speech_end = get_float(label, "Miscellaneous_Info", "SpeechEnd")
        if speech_start is None or speech_end is None or speech_end <= speech_start:
            skipped += 1
            continue

        padded_start = max(0.0, speech_start - args.padding_sec)
        padded_end = speech_end + args.padding_sec
        if file_duration is not None:
            padded_end = min(file_duration, padded_end)
        duration = padded_end - padded_start
        if duration <= 0:
            skipped += 1
            continue

        target = output_wav_dir / source.name
        crop_wav(source, target, padded_start, duration, args.force)

        updated = dict(row)
        updated["audio_path"] = display_path(target)
        updated["duration_sec"] = f"{duration:.3f}"
        updated["crop_start_sec"] = f"{padded_start:.3f}"
        updated["crop_end_sec"] = f"{padded_end:.3f}"
        updated["original_audio_path"] = row["audio_path"]
        output_rows.append(updated)

    fieldnames = list(output_rows[0].keys()) if output_rows else list(rows[0].keys())
    output_metadata.parent.mkdir(parents=True, exist_ok=True)
    with output_metadata.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"input rows: {len(rows)}")
    print(f"cropped rows: {len(output_rows)}")
    print(f"skipped rows: {skipped}")
    print(f"output: {display_path(output_metadata)}")


if __name__ == "__main__":
    main()
