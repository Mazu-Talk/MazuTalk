"""E2E 파이프라인 테스트 — 4개 모듈이 실제 사용자 흐름 안에서 연결되는지 검증.

흐름: 세션 시작 → 시나리오 → 음성 입력 → STT → 발화특성 → 표정/시선 융합
      → LLM 입력 payload 구성 → LLM 응답 → 응답 텍스트 → TTS → 아바타 상태
      → 상호작용 로그 저장 → (리포트용) 로그 조회 → 다음 턴/세션.

모듈 매핑:
  M1 ASD Speech Recognition  : STT double + speech_analysis(실코드) 발화특성
  M2 Role-Play-Interaction    : vision_fusion(실코드) + llm payload 구성/파싱(실코드)
  M3 Character Voice & Avatar : TTS double + emotion/avatar_state 응답
  M4 Learning Report          : session_store 상호작용 로그 수집/저장 (분석·리포트는 프런트 Vitest)

heavy 외부 의존성(Whisper/MeloTTS/Ollama)만 결정론적 double 로 대체한다.
"""

import httpx
import pytest

import sample_data as S
from conftest import create_session, post_audio_turn, set_stt, set_tts


# ════════════════════════════════════════════════════════════
# Happy Path
# ════════════════════════════════════════════════════════════
def test_happy_path_full_pipeline(client, monkeypatch, llm_double):
    """정상 음성+표정 입력 → STT→특성추출→융합→LLM→TTS→아바타→로그저장 전 구간."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch, S.TTS_AUDIO_ID)
    session = create_session(client, S.SCENARIO_ID)

    res = post_audio_turn(
        client, session["session_id"], turn_id="1",
        duration_seconds=1.5, facial_emotion=S.FACIAL_EMOTION_HAPPY,
    )
    assert res.status_code == 200, res.text
    body = res.json()

    # M1: 발화 텍스트 + 발화 특성 데이터 생성
    assert body["transcript"] == S.TRANSCRIPT_NORMAL
    analysis = body["analysis"]
    assert analysis["word_count"] == 4
    assert analysis["pace"]["label"] in {"slow", "normal", "fast"}
    assert "coaching_tips" in analysis and len(analysis["coaching_tips"]) >= 1
    assert body["stt_model"].startswith("faster-whisper-")

    # M2: LLM 입력 payload 가 올바르게 구성됨 (시나리오/감정/입력/히스토리)
    payload = llm_double["payloads"][-1]
    assert payload["scenario"]["id"] == S.SCENARIO_ID
    assert payload["scenario"]["location"] == "놀이터"          # scenario_catalog grounding
    assert payload["scenario"]["target_skill"] == "greeting"
    assert payload["difficulty"] == "low"
    assert payload["child_input"] == S.TRANSCRIPT_NORMAL
    assert payload["emotion_state"] == "happy"                  # 표정(happy) 융합 결과
    assert payload["conversation_history"] == []               # 첫 턴 → 히스토리 없음

    # M2: LLM 응답 텍스트가 응답에 반영됨 (RP child_message → therapist_reply)
    assert body["llm"]["therapist_reply"] == S.RP_RESPONSE["child_message"]
    assert body["llm"]["model_name"] == "mazutalk"

    # M3: TTS 음성 결과 + 아바타 응답 데이터 생성
    assert body["audio_url"].endswith(f"/api/v1/audio/{S.TTS_AUDIO_ID}.wav")
    assert body["emotion"] == "happy"
    assert body["avatar_state"] in {"speaking", "encouraging"}

    # M4: 상호작용 로그 저장 (보호자/치료사 리포트용 데이터 수집)
    logs = client.get(f"/api/v1/sessions/{session['session_id']}/logs").json()
    assert len(logs["turns"]) == 1
    turn = logs["turns"][0]
    assert turn["transcript"] == S.TRANSCRIPT_NORMAL
    assert turn["llm"]["therapist_reply"] == S.RP_RESPONSE["child_message"]
    assert turn["analysis"]["word_count"] == 4


def test_websocket_text_path_carries_facial_emotion(client, monkeypatch, llm_double):
    """브라우저 STT(텍스트) WS 경로도 표정을 LLM 으로 전달하고 공용 이벤트를 방출."""
    set_tts(monkeypatch, None)
    session = create_session(client, S.SCENARIO_ID)
    with client.websocket_connect(f"/api/v1/sessions/{session['session_id']}/ws") as ws:
        ws.send_json({
            "type": "end_utterance",
            "session_id": session["session_id"],
            "turn_id": 1,
            "payload": {"text": S.TRANSCRIPT_NORMAL, "duration_seconds": 1.5,
                        "response_time_ms": 500, "facial_emotion": S.FACIAL_EMOTION_HAPPY},
        })
        events = [ws.receive_json() for _ in range(3)]

    assert [e["type"] for e in events] == ["stt_result", "avatar_state", "ai_response"]
    ai = events[2]["payload"]
    assert ai["text"] == S.RP_RESPONSE["child_message"]
    assert ai["emotion"] == "happy"            # 표정 융합 반영
    assert ai["turn_id"] == 1
    # LLM payload 에 표정/입력 전달됨
    assert llm_double["payloads"][-1]["emotion_state"] == "happy"
    assert llm_double["payloads"][-1]["child_input"] == S.TRANSCRIPT_NORMAL


def test_speech_features_repetition_detected_flows_to_llm(client, monkeypatch, llm_double):
    """M1 발화특성(반복) 추출 → observed_features 로 LLM 입력에 반영."""
    set_stt(monkeypatch, S.TRANSCRIPT_REPEAT)
    set_tts(monkeypatch)
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"], duration_seconds=1.5)

    body = res.json()
    assert "repetition_detected" in body["analysis"]["flags"]
    assert len(body["analysis"]["repeated_expressions"]) >= 1
    # 발화 특성이 LLM 입력 observed_features 로 전달됨
    assert "repeated_phrase" in llm_double["payloads"][-1]["observed_features"]


def test_response_latency_feature_drives_emotion(client, monkeypatch, llm_double):
    """M1 응답 지연(>4s) → 행동기반 감정(anxious)으로 융합되어 LLM/응답에 반영."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(
        client, session["session_id"], duration_seconds=1.5,
        response_requested_at="2026-01-01T00:00:00+00:00",
        response_started_at="2026-01-01T00:00:05+00:00",  # 5초 지연
    )
    body = res.json()
    assert "response_latency_delayed" in body["analysis"]["flags"]
    assert body["emotion"] == "anxious"                       # 음성 행동신호 우선
    assert llm_double["payloads"][-1]["emotion_state"] == "anxious"


def test_facial_emotion_overrides_when_speech_neutral(client, monkeypatch, llm_double):
    """음성신호가 중립이면 표정(sad→frustrated)이 최종 감정을 결정."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"], facial_emotion=S.FACIAL_EMOTION_SAD)
    body = res.json()
    assert body["emotion"] == "frustrated"                    # sad → frustrated 매핑
    assert body["avatar_state"] == "encouraging"


def test_history_accumulates_across_turns(client, monkeypatch, llm_double):
    """후속 세션: 대화 히스토리가 누적되어 LLM 입력에 포함되고 로그가 쌓인다."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    session = create_session(client, S.SCENARIO_ID)
    sid = session["session_id"]

    post_audio_turn(client, sid, turn_id="1")
    assert llm_double["payloads"][-1]["conversation_history"] == []   # 첫 턴

    post_audio_turn(client, sid, turn_id="2")
    history = llm_double["payloads"][-1]["conversation_history"]      # 둘째 턴
    assert len(history) == 2
    assert history[0]["role"] == "user" and history[0]["content"] == S.TRANSCRIPT_NORMAL
    assert history[1]["role"] == "assistant"

    logs = client.get(f"/api/v1/sessions/{sid}/logs").json()
    assert len(logs["turns"]) == 2


# ════════════════════════════════════════════════════════════
# Failure / Edge Cases
# ════════════════════════════════════════════════════════════
def test_empty_transcript_is_handled_gracefully(client, monkeypatch, llm_double):
    """빈 음성 인식 결과여도 파이프라인이 에러 없이 응답을 반환한다."""
    set_stt(monkeypatch, S.TRANSCRIPT_EMPTY)
    set_tts(monkeypatch)
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"])
    assert res.status_code == 200
    assert res.json()["llm"]["therapist_reply"]


def test_short_meaningless_utterance_still_responds(client, monkeypatch, llm_double):
    set_stt(monkeypatch, S.TRANSCRIPT_SHORT)
    set_tts(monkeypatch)
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"])
    assert res.status_code == 200
    assert res.json()["transcript"] == S.TRANSCRIPT_SHORT
    assert res.json()["llm"]["therapist_reply"]


def test_llm_failure_falls_back_to_rule_model(client, monkeypatch, llm_double):
    """LLM(Ollama) 호출 실패 → 규칙기반 fallback 으로 서비스 지속(텍스트 응답 보장)."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    llm_double["error"] = httpx.ConnectError("ollama down")
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"])
    body = res.json()
    assert res.status_code == 200
    assert body["llm"]["therapist_reply"]                       # 빈 응답 아님
    assert body["llm"]["model_name"] == "backend-fallback-rule-model"


def test_llm_empty_message_falls_back(client, monkeypatch, llm_double):
    """LLM 이 빈 child_message 를 주면 fallback 으로 대체."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    llm_double["response"] = S.RP_RESPONSE_EMPTY_MESSAGE
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"])
    assert res.json()["llm"]["model_name"] == "backend-fallback-rule-model"


def test_llm_invalid_json_falls_back(client, monkeypatch, llm_double):
    """LLM 출력이 JSON 이 아니면 fallback."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    llm_double["response"] = S.RP_RESPONSE_INVALID
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"])
    assert res.json()["llm"]["model_name"] == "backend-fallback-rule-model"


def test_tts_failure_returns_text_only(client, monkeypatch, llm_double):
    """TTS 생성 실패 → audio_url 은 없지만 텍스트 응답은 정상 제공."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch, None)                                  # TTS 실패 시뮬레이션
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"])
    body = res.json()
    assert res.status_code == 200
    assert body["audio_url"] is None
    assert body["llm"]["therapist_reply"]


def test_missing_facial_emotion_uses_speech_only(client, monkeypatch, llm_double):
    """감정 이미지(표정) 입력 누락 → 음성 분석만으로 감정 결정, 에러 없음."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    session = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, session["session_id"], facial_emotion=None)
    body = res.json()
    assert res.status_code == 200
    assert body["emotion"] == "neutral"                        # 표정 없음 + 음성 중립
    assert llm_double["payloads"][-1]["emotion_state"] == "neutral"


def test_unknown_scenario_degrades_to_unknown_context(client, monkeypatch, llm_double):
    """카탈로그에 없는 시나리오 → scenario 필드 unknown 으로 안전하게 처리."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    session = create_session(client, S.SCENARIO_UNKNOWN)
    res = post_audio_turn(client, session["session_id"])
    assert res.status_code == 200
    payload = llm_double["payloads"][-1]
    assert payload["scenario"]["location"] == "unknown"
    assert payload["difficulty"] == "unknown"


def test_session_interrupt_and_reentry(client, monkeypatch, llm_double):
    """세션 중단 후 재진입: 기존 세션 종료(interrupted) → 새 세션에서 정상 진행."""
    set_stt(monkeypatch, S.TRANSCRIPT_NORMAL)
    set_tts(monkeypatch)
    first = create_session(client, S.SCENARIO_ID)
    post_audio_turn(client, first["session_id"], turn_id="1")
    end = client.post(f"/api/v1/sessions/{first['session_id']}/end", json={"status": "interrupted"})
    assert end.status_code == 200 and end.json()["status"] == "interrupted"

    second = create_session(client, S.SCENARIO_ID)
    res = post_audio_turn(client, second["session_id"], turn_id="1")
    assert res.status_code == 200
    # 두 세션의 로그가 분리되어 저장됨
    assert len(client.get(f"/api/v1/sessions/{first['session_id']}/logs").json()["turns"]) == 1
    assert len(client.get(f"/api/v1/sessions/{second['session_id']}/logs").json()["turns"]) == 1


def test_unknown_session_logs_are_empty(client):
    """존재하지 않는 세션 로그 조회는 빈 목록(저장소 안전성)."""
    logs = client.get("/api/v1/sessions/session_does_not_exist/logs")
    assert logs.status_code == 200
    assert logs.json()["turns"] == []
