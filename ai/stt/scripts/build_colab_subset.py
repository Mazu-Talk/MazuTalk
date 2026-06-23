"""Build a speaker-balanced child speech archive for Colab training."""

from __future__ import annotations

import argparse
import io
import json
import math
import tarfile
from pathlib import Path

import pandas as pd
from tqdm import tqdm


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CHILD_METADATA = "ai/data/processed/stt/metadata_preprocessed.csv"
DEFAULT_ASD_METADATA = "ai/stt/data/processed/asd_metadata.csv"
ARCHIVE_CHILD_METADATA = "ai/data/processed/stt/metadata_preprocessed.csv"
ARCHIVE_ASD_METADATA = "ai/stt/data/processed/asd_metadata.csv"


def resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child-metadata", default=DEFAULT_CHILD_METADATA)
    parser.add_argument("--asd-metadata", default=DEFAULT_ASD_METADATA)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def balanced_sample(frame: pd.DataFrame, limit: int, seed: int) -> pd.DataFrame:
    if limit <= 0:
        raise ValueError("limit must be positive")
    if len(frame) <= limit:
        return frame.sample(frac=1, random_state=seed).reset_index(drop=True)

    speakers = sorted(frame["speaker_id"].fillna("unknown").astype(str).unique())
    quota = math.ceil(limit / len(speakers))
    selected: list[pd.DataFrame] = []

    for offset, speaker_id in enumerate(speakers):
        speaker_rows = frame[frame["speaker_id"].fillna("unknown").astype(str) == speaker_id]
        selected.append(speaker_rows.sample(min(quota, len(speaker_rows)), random_state=seed + offset))

    sample = pd.concat(selected).drop_duplicates()
    if len(sample) < limit:
        remaining = frame.drop(index=sample.index, errors="ignore")
        sample = pd.concat(
            [sample, remaining.sample(min(limit - len(sample), len(remaining)), random_state=seed)],
            ignore_index=True,
        )

    return sample.sample(min(limit, len(sample)), random_state=seed).reset_index(drop=True)


def checked_audio_paths(frame: pd.DataFrame) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    missing: list[str] = []
    for value in frame["audio_path"].astype(str):
        source = resolve(value)
        if not source.exists():
            missing.append(value)
            continue
        files.append((source, value))
    if missing:
        preview = ", ".join(missing[:3])
        raise FileNotFoundError(f"{len(missing)} audio files are missing, e.g. {preview}")
    return files


def main() -> None:
    args = parse_args()
    child_metadata_path = resolve(args.child_metadata)
    asd_metadata_path = resolve(args.asd_metadata)
    output_path = resolve(args.output)

    child = pd.read_csv(child_metadata_path)
    asd = pd.read_csv(asd_metadata_path)
    child = child[child["audio_path"].astype(str).str.startswith("ai/data/raw/audio/")].reset_index(drop=True)
    child_sample = balanced_sample(child, args.limit, args.seed)
    child_files = checked_audio_paths(child_sample)
    asd_files = checked_audio_paths(asd)
    source_bytes = sum(path.stat().st_size for path, _ in child_files + asd_files)

    summary = {
        "child_samples": len(child_sample),
        "child_speakers": int(child_sample["speaker_id"].nunique()),
        "child_duration_hours": round(float(child_sample["duration_sec"].sum()) / 3600, 3),
        "asd_samples": len(asd),
        "source_bytes": source_bytes,
        "source_gib": round(source_bytes / 1024**3, 3),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.dry_run:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subset_metadata_path = resolve("ai/stt/data/processed/child_metadata_colab_subset.csv")
    subset_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    child_sample.to_csv(subset_metadata_path, index=False, encoding="utf-8")

    with tarfile.open(output_path, "w") as archive:
        archive.add(subset_metadata_path, arcname=ARCHIVE_CHILD_METADATA)
        archive.add(asd_metadata_path, arcname=ARCHIVE_ASD_METADATA)
        for source, arcname in tqdm(child_files + asd_files, desc="archive"):
            archive.add(source, arcname=arcname, recursive=False)

        manifest = json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8")
        info = tarfile.TarInfo("archive_manifest.json")
        info.size = len(manifest)
        archive.addfile(info, fileobj=io.BytesIO(manifest))

    print(f"wrote {output_path} ({output_path.stat().st_size / 1024**3:.3f} GiB)")


if __name__ == "__main__":
    main()
