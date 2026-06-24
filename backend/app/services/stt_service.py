import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TUNED_MODEL = "ai/stt/models/faster-whisper-medium-child-lora-int8"


@dataclass
class SttResult:
    transcript: str
    model_name: str
    elapsed_seconds: float
    fallback_used: bool = False
    fallback_reason: str | None = None


class SttFallbackRequired(RuntimeError):
    pass


_MODELS: dict[tuple[str, str, str], object] = {}
_MODEL_LOCK = threading.Lock()


def transcribe_audio(audio_path: Path) -> SttResult:
    model_name = resolve_model_reference(os.getenv("STT_MODEL", DEFAULT_TUNED_MODEL))
    fallback_model_name = resolve_model_reference(os.getenv("STT_FALLBACK_MODEL", "medium"))
    device = os.getenv("STT_DEVICE", "cpu")
    compute_type = os.getenv("STT_COMPUTE_TYPE", "int8")
    beam_size = int(os.getenv("STT_BEAM_SIZE", "3"))
    started = time.perf_counter()

    try:
        transcript = transcribe_with_model(
            audio_path,
            model_name=model_name,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
        )
        quality_issue = transcript_quality_issue(transcript)
        if quality_issue:
            raise SttFallbackRequired(quality_issue)
        return SttResult(
            transcript=transcript,
            model_name=model_label(model_name),
            elapsed_seconds=round(time.perf_counter() - started, 3),
        )
    except Exception as exc:
        if not fallback_model_name or fallback_model_name == model_name:
            raise
        reason = str(exc) if isinstance(exc, SttFallbackRequired) else f"primary_{type(exc).__name__}"
        logger.warning(
            "Primary STT failed; using fallback model",
            extra={"primary_model": model_name, "fallback_model": fallback_model_name, "reason": reason},
        )
        transcript = transcribe_with_model(
            audio_path,
            model_name=fallback_model_name,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
        )
        if not transcript.strip():
            raise RuntimeError("STT fallback returned an empty transcript") from exc
        return SttResult(
            transcript=transcript,
            model_name=model_label(fallback_model_name),
            elapsed_seconds=round(time.perf_counter() - started, 3),
            fallback_used=True,
            fallback_reason=reason,
        )


def transcribe_with_model(
    audio_path: Path,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    beam_size: int,
) -> str:
    model = load_model(model_name=model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        str(audio_path),
        language="ko",
        beam_size=beam_size,
        temperature=0,
        condition_on_previous_text=False,
    )
    return "".join(segment.text for segment in segments).strip()


def transcript_quality_issue(transcript: str) -> str | None:
    normalized = transcript.strip()
    if not normalized:
        return "empty_transcript"
    max_chars = int(os.getenv("STT_MAX_TRANSCRIPT_CHARS", "180"))
    if len(normalized) > max_chars:
        return "transcript_too_long"
    max_repeat = int(os.getenv("STT_MAX_CHAR_REPEAT", "8"))
    if re.search(rf"(.)\1{{{max_repeat - 1},}}", normalized):
        return "character_repetition_detected"
    return None


def resolve_model_reference(model_name: str) -> str:
    candidate = Path(model_name).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    repo_candidate = REPO_ROOT / candidate
    if repo_candidate.exists():
        return str(repo_candidate.resolve())
    return model_name


def model_label(model_name: str) -> str:
    candidate = Path(model_name)
    name = candidate.name if candidate.is_absolute() or candidate.exists() else model_name
    return name if name.startswith("faster-whisper-") else f"faster-whisper-{name}"


def load_model(model_name: str, device: str, compute_type: str):
    model_key = (model_name, device, compute_type)
    with _MODEL_LOCK:
        if model_key not in _MODELS:
            from faster_whisper import WhisperModel

            _MODELS[model_key] = WhisperModel(model_name, device=device, compute_type=compute_type)

    return _MODELS[model_key]


def clear_model_cache() -> None:
    _MODELS.clear()
