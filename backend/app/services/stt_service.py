import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SttResult:
    transcript: str
    model_name: str
    elapsed_seconds: float


_MODEL = None
_MODEL_KEY: tuple[str, str, str] | None = None


def transcribe_audio(audio_path: Path) -> SttResult:
    model_name = os.getenv("STT_MODEL", "medium")
    fallback_model_name = os.getenv("STT_FALLBACK_MODEL", "small")
    device = os.getenv("STT_DEVICE", "cpu")
    compute_type = os.getenv("STT_COMPUTE_TYPE", "int8")

    active_model_name = model_name
    try:
        model = load_model(model_name=model_name, device=device, compute_type=compute_type)
    except Exception:
        if not fallback_model_name or fallback_model_name == model_name:
            raise
        active_model_name = fallback_model_name
        model = load_model(model_name=fallback_model_name, device=device, compute_type=compute_type)

    started = time.perf_counter()
    segments, _ = model.transcribe(
        str(audio_path),
        language="ko",
        beam_size=5,
        temperature=0,
        condition_on_previous_text=False,
    )
    transcript = "".join(segment.text for segment in segments).strip()
    elapsed = time.perf_counter() - started

    return SttResult(
        transcript=transcript,
        model_name=f"faster-whisper-{active_model_name}",
        elapsed_seconds=round(elapsed, 3),
    )


def load_model(model_name: str, device: str, compute_type: str):
    global _MODEL, _MODEL_KEY

    model_key = (model_name, device, compute_type)
    if _MODEL is None or _MODEL_KEY != model_key:
        from faster_whisper import WhisperModel

        _MODEL = WhisperModel(model_name, device=device, compute_type=compute_type)
        _MODEL_KEY = model_key

    return _MODEL
