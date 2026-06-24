from contextlib import closing

from fastapi.testclient import TestClient

from app.main import app
from app.services import dialogue_pipeline, session_store
from app.services.stt_service import SttResult


client = TestClient(app)


def setup_function():
    if session_store._CONNECTION is not None:
        session_store._CONNECTION.close()
    session_store._CONNECTION = None


def teardown_function():
    if session_store._CONNECTION is not None:
        with closing(session_store._CONNECTION):
            pass
    session_store._CONNECTION = None


def create_test_session() -> dict:
    response = client.post(
        "/api/v1/sessions",
        json={"scenario_id": "greeting-001", "child_id": "child-001"},
    )
    assert response.status_code == 201
    return response.json()


def test_session_create_read_and_end():
    session = create_test_session()
    read_response = client.get(f"/api/v1/sessions/{session['session_id']}")
    assert read_response.status_code == 200
    assert read_response.json()["scenario_id"] == "greeting-001"
    end_response = client.post(
        f"/api/v1/sessions/{session['session_id']}/end",
        json={"status": "completed"},
    )
    assert end_response.status_code == 200
    assert end_response.json()["status"] == "completed"
    assert end_response.json()["ended_at"] is not None


def test_audio_pipeline_returns_stt_llm_and_tts_contract(monkeypatch):
    session = create_test_session()
    monkeypatch.setattr(
        "app.api.v1.stt.transcribe_audio",
        lambda _path: SttResult(
            transcript="안녕 같이 놀자",
            model_name="test-whisper",
            elapsed_seconds=0.12,
        ),
    )
    monkeypatch.setattr(
        dialogue_pipeline,
        "try_generate_tts",
        lambda _text, _speed: "test-audio-id",
    )
    response = client.post(
        "/api/v1/stt/pipeline",
        data={"session_id": session["session_id"], "turn_id": "2", "duration_seconds": "1.5"},
        files={"audio": ("turn.webm", b"test-audio", "audio/webm")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "안녕 같이 놀자"
    assert body["llm"]["therapist_reply"]
    assert body["audio_url"].endswith("/api/v1/audio/test-audio-id.wav")
    assert body["avatar_state"] == "speaking"


def test_websocket_uses_shared_event_envelope(monkeypatch):
    session = create_test_session()
    monkeypatch.setattr(dialogue_pipeline, "try_generate_tts", lambda _text, _speed: None)
    with client.websocket_connect(f"/api/v1/sessions/{session['session_id']}/ws") as websocket:
        websocket.send_json({
            "type": "end_utterance",
            "session_id": session["session_id"],
            "turn_id": 2,
            "payload": {"text": "안녕", "duration_seconds": 1.0, "response_time_ms": 500},
        })
        events = [websocket.receive_json() for _ in range(3)]
    assert [event["type"] for event in events] == ["stt_result", "avatar_state", "ai_response"]
    assert events[2]["payload"]["turn_id"] == 2
    assert events[2]["payload"]["audio_url"] is None
