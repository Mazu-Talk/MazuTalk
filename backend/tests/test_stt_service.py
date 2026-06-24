from pathlib import Path
from types import SimpleNamespace

from app.services import stt_service


class FakeModel:
    def __init__(self, *, transcript: str = "", error: Exception | None = None):
        self.transcript = transcript
        self.error = error

    def transcribe(self, *_args, **_kwargs):
        if self.error:
            raise self.error
        return iter([SimpleNamespace(text=self.transcript)]), SimpleNamespace(language="ko")


def setup_function():
    stt_service.clear_model_cache()


def test_primary_child_model_is_used(monkeypatch):
    monkeypatch.setenv("STT_MODEL", "child-model")
    monkeypatch.setenv("STT_FALLBACK_MODEL", "medium")
    monkeypatch.setattr(
        stt_service,
        "load_model",
        lambda model_name, device, compute_type: FakeModel(transcript="안녕하세요"),
    )

    result = stt_service.transcribe_audio(Path("sample.wav"))

    assert result.transcript == "안녕하세요"
    assert result.model_name == "faster-whisper-child-model"
    assert result.fallback_used is False
    assert result.fallback_reason is None


def test_inference_error_falls_back_to_medium(monkeypatch):
    monkeypatch.setenv("STT_MODEL", "child-model")
    monkeypatch.setenv("STT_FALLBACK_MODEL", "medium")
    models = {
        "child-model": FakeModel(error=RuntimeError("primary failed")),
        "medium": FakeModel(transcript="대체 인식 결과"),
    }
    monkeypatch.setattr(
        stt_service,
        "load_model",
        lambda model_name, device, compute_type: models[model_name],
    )

    result = stt_service.transcribe_audio(Path("sample.wav"))

    assert result.transcript == "대체 인식 결과"
    assert result.model_name == "faster-whisper-medium"
    assert result.fallback_used is True
    assert result.fallback_reason == "primary_RuntimeError"


def test_repetition_hallucination_falls_back_to_medium(monkeypatch):
    monkeypatch.setenv("STT_MODEL", "child-model")
    monkeypatch.setenv("STT_FALLBACK_MODEL", "medium")
    models = {
        "child-model": FakeModel(transcript="쭈" + "우" * 20),
        "medium": FakeModel(transcript="삼"),
    }
    monkeypatch.setattr(
        stt_service,
        "load_model",
        lambda model_name, device, compute_type: models[model_name],
    )

    result = stt_service.transcribe_audio(Path("sample.wav"))

    assert result.transcript == "삼"
    assert result.fallback_used is True
    assert result.fallback_reason == "character_repetition_detected"
