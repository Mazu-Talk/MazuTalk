from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from common import audio_duration_sec, display_path, ensure_parent, read_metadata, resolve_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert wav files to a consistent STT format.")
    parser.add_argument("--input-metadata", default="ai/stt/data/processed/metadata.csv")
    parser.add_argument("--output-metadata", default="ai/stt/data/processed/metadata_preprocessed.csv")
    parser.add_argument("--output-wav-dir", default="ai/stt/data/processed/wav")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--absolute-paths", action="store_true")
    return parser.parse_args()


def convert_wav(input_path: Path, output_path: Path, sample_rate: int, force: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y" if force else "-n",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    df = read_metadata(args.input_metadata)
    output_wav_dir = resolve_path(args.output_wav_dir)
    output_metadata = resolve_path(args.output_metadata)

    rows: list[dict[str, object]] = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="preprocess"):
        source = resolve_path(row["audio_path"])
        target = output_wav_dir / f"{source.stem}.wav"

        if target.exists() and not args.force:
            pass
        else:
            convert_wav(source, target, args.sample_rate, args.force)

        updated = row.to_dict()
        updated["audio_path"] = display_path(target, args.absolute_paths)
        updated["duration_sec"] = audio_duration_sec(target)
        rows.append(updated)

    ensure_parent(output_metadata)
    pd.DataFrame(rows).to_csv(output_metadata, index=False)
    print(f"wrote {len(rows)} rows to {display_path(output_metadata)}")


if __name__ == "__main__":
    main()

