"""Build metadata.csv for AI Hub child speech STT experiments.

Example:
    python ai/stt/scripts/build_dataset.py --limit 50
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_LABEL_DIR = "ai/data/raw/kor_free/labels"
DEFAULT_AUDIO_ROOT = "ai/data/raw/kor_free/audio"
DEFAULT_OUTPUT = "ai/data/processed/stt/metadata.csv"

FIELDNAMES = [
    "file_name",
    "audio_path",
    "text",
    "age",
    "gender",
    "speaker_id",
    "duration",
    "speech_start",
    "speech_end",
    "sampling_rate",
    "channels",
    "bit_depth",
    "quality",
    "recording_env",
    "noise_env",
    "data_category",
    "file_format",
    "is_16k_mono_wav",
]


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def csv_path(path: str | Path) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def safe_get(data: dict[str, Any], *keys: str, default: str = "") -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_good_quality(value: Any) -> bool:
    return clean(value).lower() == "good"


def is_16k_mono_wav(sampling_rate: Any, channels: Any, file_format: Any) -> bool:
    return clean(sampling_rate) == "16000" and clean(channels) == "1" and clean(file_format).lower() == "wav"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create STT metadata.csv from AI Hub label JSON files.",
    )
    parser.add_argument("--label-dir", default=DEFAULT_LABEL_DIR)
    parser.add_argument("--audio-root", default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, help="Write only the first N valid rows.")
    parser.add_argument(
        "--include-all-quality",
        action="store_true",
        help="Include rows whose Other.QualityStatus is not Good.",
    )
    return parser.parse_args()


def empty_output(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()


def main() -> None:
    args = parse_args()
    label_dir = resolve_path(args.label_dir)
    audio_root = resolve_path(args.audio_root)
    output_path = resolve_path(args.output)

    if not label_dir.exists():
        empty_output(output_path)
        print(f"Label directory not found: {csv_path(label_dir)}")
        print(f"Created empty metadata with headers: {csv_path(output_path)}")
        print("Total JSON files: 0")
        print("Valid rows: 0")
        print("Excluded rows: 0")
        print("Excluded reasons: {}")
        return

    json_files = sorted(label_dir.rglob("*.json"))
    rows: list[dict[str, str]] = []
    excluded = Counter()

    for json_path in json_files:
        try:
            with json_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            excluded["invalid_json"] += 1
            print(f"[skip] invalid json: {csv_path(json_path)} ({exc})")
            continue

        file_name = clean(safe_get(data, "File", "FileName"))
        text = clean(safe_get(data, "Transcription", "LabelText"))
        quality = clean(safe_get(data, "Other", "QualityStatus"))

        if not file_name:
            excluded["missing_file_name"] += 1
            continue
        if not text:
            excluded["missing_label_text"] += 1
            continue
        if not args.include_all_quality and not is_good_quality(quality):
            excluded["non_good_quality"] += 1
            continue
        if args.limit is not None and len(rows) >= args.limit:
            excluded["limit_not_written"] += 1
            continue

        file_format = clean(safe_get(data, "File", "FileFormat"))
        sampling_rate = clean(safe_get(data, "Wav", "SamplingRate"))
        channels = clean(safe_get(data, "Wav", "NumberOfChannel"))

        audio_path = audio_root / file_name
        rows.append(
            {
                "file_name": file_name,
                "audio_path": csv_path(audio_path),
                "text": text,
                "age": clean(safe_get(data, "Speaker", "Age")),
                "gender": clean(safe_get(data, "Speaker", "Gender")),
                "speaker_id": clean(safe_get(data, "Speaker", "SpeakerName")),
                "duration": clean(safe_get(data, "File", "FileLength")),
                "speech_start": clean(safe_get(data, "Miscellaneous_Info", "SpeechStart")),
                "speech_end": clean(safe_get(data, "Miscellaneous_Info", "SpeechEnd")),
                "sampling_rate": sampling_rate,
                "channels": channels,
                "bit_depth": clean(safe_get(data, "Wav", "NumberOfBit")),
                "quality": quality,
                "recording_env": clean(safe_get(data, "Environment", "RecordingEnviron")),
                "noise_env": clean(safe_get(data, "Environment", "NoiseEnviron")),
                "data_category": clean(safe_get(data, "Basic", "DataCategory")),
                "file_format": file_format,
                "is_16k_mono_wav": str(is_16k_mono_wav(sampling_rate, channels, file_format)),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    excluded_total = sum(excluded.values())
    print(f"Total JSON files: {len(json_files)}")
    print(f"Valid rows: {len(rows)}")
    print(f"Excluded rows: {excluded_total}")
    print(f"Excluded reasons: {dict(excluded)}")
    print(f"Saved metadata: {csv_path(output_path)}")


if __name__ == "__main__":
    main()
