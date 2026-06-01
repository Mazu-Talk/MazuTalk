"""Compare Whisper and Faster-Whisper STT results with normalized Korean CER.

Example:
    python ai/stt/scripts/compare_stt.py
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WHISPER = "ai/stt/results/whisper_result.csv"
DEFAULT_FASTER_WHISPER = "ai/stt/results/faster_whisper_result.csv"
DEFAULT_OUTPUT = "ai/stt/results/stt_compare_result.csv"

FIELDNAMES = [
    "file_name",
    "ground_truth",
    "whisper_text",
    "faster_whisper_text",
    "whisper_cer",
    "faster_whisper_cer",
    "whisper_time_sec",
    "faster_whisper_time_sec",
]

PUNCTUATION_RE = re.compile(r"""[\s,\.?!'"`"“”‘’\(\)\[\]\{\}]""")


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def csv_path(path: str | Path) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def normalize_text(text: str | None) -> str:
    return PUNCTUATION_RE.sub("", (text or "").strip())


def levenshtein_distance(source: str, target: str) -> int:
    if source == target:
        return 0
    if not source:
        return len(target)
    if not target:
        return len(source)

    previous = list(range(len(target) + 1))
    for i, source_char in enumerate(source, start=1):
        current = [i]
        for j, target_char in enumerate(target, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (source_char != target_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def cer(reference: str, prediction: str) -> float:
    normalized_ref = normalize_text(reference)
    normalized_pred = normalize_text(prediction)
    if not normalized_ref:
        return 0.0 if not normalized_pred else 1.0
    return levenshtein_distance(normalized_ref, normalized_pred) / len(normalized_ref)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Whisper and Faster-Whisper results by CER and time.")
    parser.add_argument("--whisper", default=DEFAULT_WHISPER)
    parser.add_argument("--faster-whisper", default=DEFAULT_FASTER_WHISPER)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def read_csv(path: Path, first_command: str) -> list[dict[str, str]]:
    if not path.exists():
        print(f"Result file not found: {csv_path(path)}", file=sys.stderr)
        print("Run this first:", file=sys.stderr)
        print(f"  {first_command}", file=sys.stderr)
        raise SystemExit(1)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def parse_float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def main() -> None:
    args = parse_args()
    whisper_path = resolve_path(args.whisper)
    faster_path = resolve_path(args.faster_whisper)
    output_path = resolve_path(args.output)

    whisper_rows = read_csv(
        whisper_path,
        "python ai/stt/scripts/run_whisper.py --metadata ai/data/processed/stt/metadata.csv --limit 50",
    )
    faster_rows = read_csv(
        faster_path,
        "python ai/stt/scripts/run_faster_whisper.py --metadata ai/data/processed/stt/metadata.csv --limit 50",
    )

    whisper_by_file = {row.get("file_name", ""): row for row in whisper_rows if row.get("file_name")}
    faster_by_file = {row.get("file_name", ""): row for row in faster_rows if row.get("file_name")}
    common_files = sorted(set(whisper_by_file) & set(faster_by_file))
    if args.limit is not None:
        common_files = common_files[: args.limit]

    rows: list[dict[str, str]] = []
    whisper_cers: list[float] = []
    faster_cers: list[float] = []
    whisper_times: list[float] = []
    faster_times: list[float] = []

    for file_name in common_files:
        whisper_row = whisper_by_file[file_name]
        faster_row = faster_by_file[file_name]
        ground_truth = whisper_row.get("ground_truth") or faster_row.get("ground_truth", "")
        whisper_text = whisper_row.get("whisper_text", "")
        faster_text = faster_row.get("faster_whisper_text", "")
        whisper_cer = cer(ground_truth, whisper_text)
        faster_cer = cer(ground_truth, faster_text)
        whisper_time = parse_float(whisper_row.get("whisper_time_sec"))
        faster_time = parse_float(faster_row.get("faster_whisper_time_sec"))

        whisper_cers.append(whisper_cer)
        faster_cers.append(faster_cer)
        whisper_times.append(whisper_time)
        faster_times.append(faster_time)
        rows.append(
            {
                "file_name": file_name,
                "ground_truth": ground_truth,
                "whisper_text": whisper_text,
                "faster_whisper_text": faster_text,
                "whisper_cer": f"{whisper_cer:.6f}",
                "faster_whisper_cer": f"{faster_cer:.6f}",
                "whisper_time_sec": f"{whisper_time:.3f}",
                "faster_whisper_time_sec": f"{faster_time:.3f}",
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Compared files: {len(rows)}")
    print(f"Average Whisper CER: {mean(whisper_cers):.6f}")
    print(f"Average Faster-Whisper CER: {mean(faster_cers):.6f}")
    print(f"Average Whisper time sec: {mean(whisper_times):.3f}")
    print(f"Average Faster-Whisper time sec: {mean(faster_times):.3f}")
    print(f"Saved comparison: {csv_path(output_path)}")


if __name__ == "__main__":
    main()
