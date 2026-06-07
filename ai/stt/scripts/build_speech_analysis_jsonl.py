from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from common import display_path, ensure_parent, read_metadata, resolve_path


TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
KOREAN_SYLLABLE_RE = re.compile(r"[가-힣]")
FILLER_WORDS = {"음", "어", "아", "그", "저", "막", "이제", "그러니까", "뭐지"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build readable JSONL records for speech analysis and STT training.",
    )
    parser.add_argument("--metadata", default="ai/data/processed/stt/metadata_preprocessed.csv")
    parser.add_argument("--output", default="ai/data/processed/stt/speech_analysis_dataset.jsonl")
    parser.add_argument("--sample-output", default="ai/data/processed/stt/speech_analysis_sample.json")
    parser.add_argument("--split-mode", choices=("metadata", "speaker"), default="speaker")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--valid-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def load_json(path: str | Path) -> dict[str, Any]:
    with resolve_path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def to_int(value: Any) -> int | None:
    try:
        if value in (None, "", "N/A"):
            return None
        return int(float(str(value).replace("+", "").replace("dB", "")))
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    try:
        if value in (None, "", "N/A"):
            return None
        return float(str(value).replace("+", "").replace("dB", ""))
    except (TypeError, ValueError):
        return None


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def repeated_expressions(tokens: list[str]) -> list[dict[str, Any]]:
    repeated: dict[tuple[str, str], dict[str, Any]] = {}

    for token, count in Counter(tokens).items():
        if count >= 3 or (token in FILLER_WORDS and count >= 2):
            repeated[("word", token)] = {
                "expression": token,
                "count": count,
                "type": "filler" if token in FILLER_WORDS else "word",
            }

    for index in range(1, len(tokens)):
        if tokens[index] == tokens[index - 1]:
            token = tokens[index]
            current = repeated.get(("consecutive", token))
            repeated[("consecutive", token)] = {
                "expression": token,
                "count": current["count"] + 1 if current else 2,
                "type": "consecutive",
            }

    return sorted(repeated.values(), key=lambda item: (-item["count"], item["expression"]))[:10]


def pace_label(words_per_minute: float | None) -> str:
    if words_per_minute is None:
        return "unknown"
    if words_per_minute < 70:
        return "slow"
    if words_per_minute > 160:
        return "fast"
    return "normal"


def build_record(row: pd.Series) -> dict[str, Any]:
    label = load_json(row["source_json"])
    transcript = clean_text(row["text"])
    tokens = tokenize(transcript)
    syllable_count = len(KOREAN_SYLLABLE_RE.findall(transcript))

    file_length = to_float(get(label, "File", "FileLength"))
    speech_start = to_float(get(label, "Miscellaneous_Info", "SpeechStart"))
    speech_end = to_float(get(label, "Miscellaneous_Info", "SpeechEnd"))
    if speech_start is not None and speech_end is not None and speech_end > speech_start:
        speech_duration = round(speech_end - speech_start, 3)
    else:
        speech_duration = to_float(row.get("duration_sec"))

    words_per_minute = (
        round(len(tokens) / speech_duration * 60, 2)
        if speech_duration and speech_duration > 0
        else None
    )
    syllables_per_second = (
        round(syllable_count / speech_duration, 2)
        if speech_duration and speech_duration > 0
        else None
    )
    repeated = repeated_expressions(tokens)

    sample_rate = to_int(get(label, "Wav", "SamplingRate"))
    channels = to_int(get(label, "Wav", "NumberOfChannel"))
    bit_depth = to_int(get(label, "Wav", "NumberOfBit"))
    quality_status = clean_text(get(label, "Other", "QualityStatus"))

    usable_for_training = all(
        [
            bool(transcript),
            sample_rate == 16000,
            channels == 1,
            clean_text(get(label, "File", "FileFormat")).lower() == "wav",
            quality_status.lower() == "good",
            speech_duration is not None and speech_duration > 0.3,
        ]
    )

    return {
        "utterance_id": Path(str(row["audio_path"])).stem,
        "audio": {
            "path": row["audio_path"],
            "file_name": clean_text(get(label, "File", "FileName")),
            "format": clean_text(get(label, "File", "FileFormat")).lower(),
            "sample_rate": sample_rate,
            "channels": channels,
            "bit_depth": bit_depth,
            "file_duration_sec": file_length,
            "speech_start_sec": speech_start,
            "speech_end_sec": speech_end,
            "speech_duration_sec": speech_duration,
            "signal_to_noise_ratio_db": to_float(get(label, "Wav", "SignalToNoiseRatio")),
        },
        "environment": {
            "recording_environment": clean_text(get(label, "Environment", "RecordingEnviron")),
            "noise_environment": clean_text(get(label, "Environment", "NoiseEnviron")),
            "recording_device": clean_text(get(label, "Environment", "RecordingDevices")),
        },
        "speaker": {
            "speaker_id": clean_text(get(label, "Basic", "NumberOfSpeaker")),
            "speaker_name": clean_text(get(label, "Speaker", "SpeakerName")),
            "gender": clean_text(get(label, "Speaker", "Gender")),
            "age": to_int(get(label, "Speaker", "Age")),
            "age_group": clean_text(get(label, "Speaker", "AgeGroup")),
            "school_year": clean_text(get(label, "Speaker", "SchoolYear")),
            "region": clean_text(get(label, "Speaker", "Region")),
            "dialect": clean_text(get(label, "Speaker", "Dialect")),
        },
        "transcription": {
            "text": transcript,
            "language": clean_text(get(label, "Basic", "Language")) or "KOR",
            "error_tagged": clean_text(get(label, "Transcription", "ErrorTagged")),
            "grammatical_error": clean_text(get(label, "Transcription", "GrammaticalError")),
        },
        "speech_features": {
            "word_count": len(tokens),
            "syllable_count": syllable_count,
            "character_count": len(transcript),
            "words_per_minute": words_per_minute,
            "syllables_per_second": syllables_per_second,
            "pace_label": pace_label(words_per_minute),
            "repeated_expressions": repeated,
            "has_repetition": bool(repeated),
            "response_latency_sec": None,
            "response_latency_label": "not_available_in_offline_dataset",
        },
        "quality": {
            "quality_status": quality_status,
            "number_of_repeat": to_int(get(label, "File", "NumberOfRepeat")),
            "is_16k_mono_wav": sample_rate == 16000 and channels == 1,
            "usable_for_training": usable_for_training,
        },
        "training": {
            "task": "speech_to_text",
            "input_audio_path": row["audio_path"],
            "target_text": transcript,
            "split": clean_text(row.get("analysis_split", row.get("split", "train"))),
        },
        "source": {
            "label_path": row["source_json"],
            "data_category": clean_text(get(label, "Basic", "DataCategory")),
            "recording_date": clean_text(get(label, "Basic", "RecordingDate")),
            "dataset_version": clean_text(get(label, "Basic", "Version")),
        },
    }


def apply_speaker_split(
    df: pd.DataFrame,
    train_ratio: float,
    valid_ratio: float,
    seed: int,
) -> pd.DataFrame:
    if not 0 < train_ratio < 1:
        raise ValueError("--train-ratio must be between 0 and 1")
    if not 0 <= valid_ratio < 1:
        raise ValueError("--valid-ratio must be between 0 and 1")
    if train_ratio + valid_ratio >= 1:
        raise ValueError("--train-ratio + --valid-ratio must be less than 1")

    speakers = sorted(df["speaker_id"].fillna("unknown").astype(str).unique())
    rng = random.Random(seed)
    rng.shuffle(speakers)

    train_cutoff = int(len(speakers) * train_ratio)
    valid_cutoff = train_cutoff + int(len(speakers) * valid_ratio)
    train_speakers = set(speakers[:train_cutoff])
    valid_speakers = set(speakers[train_cutoff:valid_cutoff])

    def choose_split(speaker_id: object) -> str:
        speaker = str(speaker_id)
        if speaker in train_speakers:
            return "train"
        if speaker in valid_speakers:
            return "valid"
        return "test"

    df = df.copy()
    df["analysis_split"] = df["speaker_id"].map(choose_split)
    return df


def main() -> None:
    args = parse_args()
    df = read_metadata(args.metadata)
    if args.limit:
        df = df.head(args.limit)
    if args.split_mode == "speaker":
        df = apply_speaker_split(df, args.train_ratio, args.valid_ratio, args.seed)

    output = resolve_path(args.output)
    sample_output = resolve_path(args.sample_output)
    ensure_parent(output)
    ensure_parent(sample_output)

    first_record: dict[str, Any] | None = None
    written = 0
    usable = 0
    with output.open("w", encoding="utf-8") as file:
        for _, row in tqdm(df.iterrows(), total=len(df), desc="analysis-jsonl"):
            record = build_record(row)
            if first_record is None:
                first_record = record
            usable += int(record["quality"]["usable_for_training"])
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    if first_record:
        sample_output.write_text(
            json.dumps(first_record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"wrote {written} records to {display_path(output)}")
    print(f"usable_for_training: {usable}")
    if "analysis_split" in df.columns:
        print(f"split_counts: {df['analysis_split'].value_counts().to_dict()}")
    print(f"sample: {display_path(sample_output)}")


if __name__ == "__main__":
    main()
