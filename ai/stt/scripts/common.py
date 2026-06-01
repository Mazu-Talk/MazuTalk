from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import jiwer
import pandas as pd
import soundfile as sf


STT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STT_ROOT.parents[1]


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def display_path(path: str | Path, absolute: bool = False) -> str:
    path = Path(path).resolve()
    if absolute:
        return str(path)
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def ensure_parent(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def read_metadata(path: str | Path) -> pd.DataFrame:
    path = resolve_path(path)
    if not path.exists():
        raise FileNotFoundError(f"metadata file not found: {path}")
    df = pd.read_csv(path)
    required = {"audio_path", "text"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"metadata is missing required columns: {missing}")
    return df


def audio_duration_sec(path: str | Path) -> float:
    info = sf.info(str(resolve_path(path)))
    return round(float(info.frames) / float(info.samplerate), 3)


def normalize_text(text: object) -> str:
    if pd.isna(text):
        return ""
    text = str(text).lower()
    text = re.sub(r"[\[\]\(\)\{\}\"'`.,!?;:~\-_/\\|@#$%^&*+=<>]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compact_for_cer(text: object) -> str:
    return normalize_text(text).replace(" ", "")


def safe_cer(reference: object, prediction: object, normalized: bool = False) -> float | None:
    if normalized:
        reference = compact_for_cer(reference)
        prediction = compact_for_cer(prediction)
    else:
        reference = "" if pd.isna(reference) else str(reference)
        prediction = "" if pd.isna(prediction) else str(prediction)

    if not reference:
        return None
    return float(jiwer.cer(reference, prediction))


def corpus_cer(references: Iterable[object], predictions: Iterable[object], normalized: bool = False) -> float | None:
    refs: list[str] = []
    preds: list[str] = []
    for ref, pred in zip(references, predictions):
        if normalized:
            ref_text = compact_for_cer(ref)
            pred_text = compact_for_cer(pred)
        else:
            ref_text = "" if pd.isna(ref) else str(ref)
            pred_text = "" if pd.isna(pred) else str(pred)
        if ref_text:
            refs.append(ref_text)
            preds.append(pred_text)

    if not refs:
        return None
    return float(jiwer.cer(refs, preds))


def iter_split(df: pd.DataFrame, split: str | None, limit: int | None) -> pd.DataFrame:
    if split and "split" in df.columns:
        df = df[df["split"] == split]
    if limit is not None:
        df = df.head(limit)
    return df.reset_index(drop=True)

