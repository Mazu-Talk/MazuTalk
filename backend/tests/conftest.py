"""E2E 테스트 공용 fixture 및 test double.

설계 원칙:
- 실제 파이프라인 코드(speech_analysis · vision_fusion · dialogue_pipeline ·
  llm_client 의 payload 구성/파싱 · session_store)는 그대로 실행한다.
- 무거운 외부 의존성만 결정론적으로 대체한다:
    * STT(faster-whisper)  → transcribe_audio double
    * TTS(MeloTTS)         → try_generate_tts double
    * LLM(Ollama /api/chat)→ LlmClient._chat double  (입력 payload 는 실코드가 구성)
- DB(sqlite in-memory)는 테스트마다 초기화한다.
"""

import json
from contextlib import closing

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import dialogue_pipeline, session_store
from app.services.stt_service import SttResult

import sample_data as S


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_session_db():
    """각 테스트마다 세션 DB 연결을 새로 만들어 격리한다(:memory:)."""
    if session_store._CONNECTION is not None:
        session_store._CONNECTION.close()
    session_store._CONNECTION = None
    yield
    if session_store._CONNECTION is not None:
        with closing(session_store._CONNECTION):
            pass
    session_store._CONNECTION = None


# ── STT double ─────────────────────────────────────────────
def set_stt(monkeypatch, transcript: str, *, raises: Exception | None = None) -> None:
    def fake_transcribe(_path):
        if raises:
            raise raises
        return SttResult(
            transcript=transcript,
            model_name="faster-whisper-medium-child-lora-int8",
            elapsed_seconds=0.12,
        )

    monkeypatch.setattr("app.api.v1.stt.transcribe_audio", fake_transcribe)


# ── TTS double ─────────────────────────────────────────────
def set_tts(monkeypatch, audio_id: str | None = S.TTS_AUDIO_ID) -> None:
    monkeypatch.setattr(dialogue_pipeline, "try_generate_tts", lambda _text, _speed: audio_id)


# ── LLM(Ollama) double ─────────────────────────────────────
@pytest.fixture
def llm_double(monkeypatch):
    """LlmClient._chat 를 대체. 실제 build_user_content(payload 구성)는 그대로 실행되고,
    구성된 payload 를 기록해 검증에 쓴다. response/error 를 바꿔 엣지케이스를 만든다."""
    state: dict = {"payloads": [], "response": None, "error": None}

    async def fake_chat(_self, user_content: str) -> str:
        state["payloads"].append(json.loads(user_content))
        if state["error"] is not None:
            raise state["error"]
        return state["response"] if state["response"] is not None else S.RP_RESPONSE_JSON

    monkeypatch.setenv("OLLAMA_URL", "http://test-ollama:11434")
    monkeypatch.setenv("LLM_MODEL", "mazutalk")
    monkeypatch.setattr("app.services.llm_client.LlmClient._chat", fake_chat)
    return state


# ── 헬퍼: 세션 생성 / 파이프라인 호출 ───────────────────────
def create_session(client: TestClient, scenario_id: str = S.SCENARIO_ID, child_id: str = "child-001") -> dict:
    res = client.post("/api/v1/sessions", json={"scenario_id": scenario_id, "child_id": child_id})
    assert res.status_code == 201, res.text
    return res.json()


def post_audio_turn(
    client: TestClient,
    session_id: str,
    *,
    turn_id: str = "1",
    duration_seconds: float = 1.5,
    facial_emotion: str | None = None,
    response_requested_at: str | None = None,
    response_started_at: str | None = None,
):
    data = {"session_id": session_id, "turn_id": turn_id, "duration_seconds": str(duration_seconds)}
    if facial_emotion is not None:
        data["facial_emotion"] = facial_emotion
    if response_requested_at is not None:
        data["response_requested_at"] = response_requested_at
    if response_started_at is not None:
        data["response_started_at"] = response_started_at
    return client.post(
        "/api/v1/stt/pipeline",
        data=data,
        files={"audio": ("turn.webm", S.SAMPLE_AUDIO_BYTES, "audio/webm")},
    )
