from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from common import corpus_cer, display_path, ensure_parent, resolve_path, safe_cer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate STT prediction CSV files with CER and speed metrics.")
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=[
            "ai/stt/results/whisper/predictions.csv",
            "ai/stt/results/faster-whisper/predictions.csv",
        ],
    )
    parser.add_argument("--summary-output", default="ai/stt/results/metrics/comparison.csv")
    parser.add_argument("--details-output", default="ai/stt/results/metrics/details.csv")
    return parser.parse_args()


def load_predictions(paths: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        resolved = resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"prediction file not found: {resolved}")
        frame = pd.read_csv(resolved)
        frame["source_file"] = display_path(resolved)
        frames.append(frame)

    df = pd.concat(frames, ignore_index=True)
    required = {"engine", "model_size", "audio_path", "reference", "prediction", "duration_sec", "elapsed_sec"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"prediction CSV is missing required columns: {missing}")
    return df


def build_details(df: pd.DataFrame) -> pd.DataFrame:
    details = df.copy()
    details["cer_raw"] = [
        safe_cer(ref, pred, normalized=False) for ref, pred in zip(details["reference"], details["prediction"])
    ]
    details["cer_normalized"] = [
        safe_cer(ref, pred, normalized=True) for ref, pred in zip(details["reference"], details["prediction"])
    ]
    return details


def build_summary(details: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_cols = ["engine", "model_size"]
    if "compute_type" in details.columns:
        group_cols.append("compute_type")

    for keys, group in details.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        total_audio = float(group["duration_sec"].fillna(0).sum())
        total_elapsed = float(group["elapsed_sec"].fillna(0).sum())
        row.update(
            {
                "num_files": int(len(group)),
                "cer_raw": corpus_cer(group["reference"], group["prediction"], normalized=False),
                "cer_normalized": corpus_cer(group["reference"], group["prediction"], normalized=True),
                "avg_file_cer_raw": group["cer_raw"].mean(),
                "avg_file_cer_normalized": group["cer_normalized"].mean(),
                "total_audio_sec": round(total_audio, 3),
                "total_elapsed_sec": round(total_elapsed, 3),
                "avg_rtf": round(total_elapsed / total_audio, 4) if total_audio > 0 else None,
            }
        )
        rows.append(row)

    return pd.DataFrame(rows).sort_values(group_cols).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    predictions = load_predictions(args.inputs)
    details = build_details(predictions)
    summary = build_summary(details)

    details_output = resolve_path(args.details_output)
    summary_output = resolve_path(args.summary_output)
    ensure_parent(details_output)
    ensure_parent(summary_output)
    details.to_csv(details_output, index=False)
    summary.to_csv(summary_output, index=False)

    print(f"wrote details to {display_path(details_output)}")
    print(f"wrote summary to {display_path(summary_output)}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

