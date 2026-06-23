import logging
import os
import threading
import uuid
from pathlib import Path


logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(os.getenv("TTS_OUTPUT_DIR", "output_audio")).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_model = None
_speaker_id = None
_model_lock = threading.Lock()


class TtsUnavailableError(RuntimeError):
    pass


def get_model():
    global _model, _speaker_id
    with _model_lock:
        if _model is None:
            try:
                from melo.api import TTS
            except ImportError as exc:
                raise TtsUnavailableError(
                    "MeloTTS is not installed. Install the backend TTS dependencies."
                ) from exc

            _model = TTS(language="KR", device=os.getenv("TTS_DEVICE", "auto"))
            _speaker_id = _model.hps.data.spk2id["KR"]
    return _model, _speaker_id


def generate_tts(text: str, speed: float = 1.1) -> str:
    if not text.strip():
        raise ValueError("TTS text must not be empty")

    file_id = str(uuid.uuid4())
    output_path = OUTPUT_DIR / f"{file_id}.wav"
    tts_model, speaker_id = get_model()
    tts_model.tts_to_file(
        text=text,
        speaker_id=speaker_id,
        output_path=str(output_path),
        speed=speed,
    )
    return file_id


def try_generate_tts(text: str, speed: float = 1.1) -> str | None:
    """Generate speech when MeloTTS is healthy; let the frontend use browser TTS otherwise."""
    try:
        return generate_tts(text, speed)
    except Exception:
        logger.exception("TTS generation failed; returning a text-only response")
        return None


def get_audio_path(filename: str) -> Path | None:
    safe_name = Path(filename).name
    candidate = OUTPUT_DIR / safe_name
    if candidate.suffix.lower() != ".wav" or not candidate.is_file():
        return None
    return candidate
