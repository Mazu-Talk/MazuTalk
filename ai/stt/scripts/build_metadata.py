from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from common import audio_duration_sec, display_path, ensure_parent, resolve_path


TEXT_CANDIDATES = (
    "transcript",
    "transcription",
    "text",
    "sentence",
    "utterance",
    "utterance_text",
    "script",
    "original_form",
    "normalized_form",
    "form",
    "label_text",
    "발화내용",
    "전사내용",
    "전사",
    "문장",
    "대화내용",
)

SPEAKER_CANDIDATES = (
    "speaker_id",
    "speaker",
    "speakerId",
    "speakerID",
    "화자",
    "화자ID",
)


def get_by_path(data: Any, key_path: str) -> Any:
    current = data
    for part in key_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            return None
    return current


def collect_values_for_key(data: Any, target_key: str) -> list[str]:
    values: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key and isinstance(value, str) and value.strip():
                values.append(value.strip())
            elif isinstance(value, (dict, list)):
                values.extend(collect_values_for_key(value, target_key))
    elif isinstance(data, list):
        for item in data:
            values.extend(collect_values_for_key(item, target_key))
    return values


def collect_candidate_values(data: Any, candidates: tuple[str, ...]) -> list[str]:
    for key in candidates:
        values = collect_values_for_key(data, key)
        if values:
            return values
    return []


def extract_text(data: Any, text_key: str | None) -> str:
    if text_key:
        value = get_by_path(data, text_key)
        if isinstance(value, list):
            return " ".join(str(item).strip() for item in value if str(item).strip())
        return "" if value is None else str(value).strip()

    values = collect_candidate_values(data, TEXT_CANDIDATES)
    return " ".join(dict.fromkeys(values))


def extract_speaker(data: Any, speaker_key: str | None) -> str:
    if speaker_key:
        value = get_by_path(data, speaker_key)
        return "" if value is None else str(value).strip()

    values = collect_candidate_values(data, SPEAKER_CANDIDATES)
    return values[0] if values else ""


def index_labels(label_dir: Path) -> dict[str, Path]:
    labels: dict[str, Path] = {}
    for path in sorted(label_dir.rglob("*.json")):
        labels.setdefault(path.stem, path)
    return labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build STT metadata.csv from wav files and AI Hub JSON labels.")
    parser.add_argument("--wav-dir", default="ai/stt/data/raw/wav")
    parser.add_argument("--label-dir", default="ai/stt/data/raw/labels")
    parser.add_argument("--output", default="ai/stt/data/processed/metadata.csv")
    parser.add_argument("--audio-ext", default=".wav")
    parser.add_argument("--split", default="test")
    parser.add_argument("--text-key", help="Optional dotted JSON path, e.g. data.0.transcript")
    parser.add_argument("--speaker-key", help="Optional dotted JSON path, e.g. speaker.id")
    parser.add_argument("--allow-empty-text", action="store_true")
    parser.add_argument("--absolute-paths", action="store_true")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wav_dir = resolve_path(args.wav_dir)
    label_dir = resolve_path(args.label_dir)
    output = resolve_path(args.output)

    if not wav_dir.exists():
        raise FileNotFoundError(f"wav dir not found: {wav_dir}")
    if not label_dir.exists():
        raise FileNotFoundError(f"label dir not found: {label_dir}")

    label_index = index_labels(label_dir)
    wav_files = sorted(wav_dir.rglob(f"*{args.audio_ext}"))
    if args.limit:
        wav_files = wav_files[: args.limit]

    rows: list[dict[str, object]] = []
    skipped = 0
    for wav_path in tqdm(wav_files, desc="metadata"):
        label_path = label_index.get(wav_path.stem)
        if label_path is None:
            skipped += 1
            continue

        with label_path.open("r", encoding="utf-8") as file:
            label = json.load(file)

        text = extract_text(label, args.text_key)
        if not text and not args.allow_empty_text:
            skipped += 1
            continue

        rows.append(
            {
                "audio_path": display_path(wav_path, args.absolute_paths),
                "text": text,
                "speaker_id": extract_speaker(label, args.speaker_key),
                "duration_sec": audio_duration_sec(wav_path),
                "split": args.split,
                "source_json": display_path(label_path, args.absolute_paths),
            }
        )

    ensure_parent(output)
    pd.DataFrame(rows).to_csv(output, index=False)
    print(f"wrote {len(rows)} rows to {display_path(output)}")
    if skipped:
        print(f"skipped {skipped} files without matching labels or usable text")


if __name__ == "__main__":
    main()
