"""E2E 테스트용 결정론적 fixture 데이터.

실제 모델/외부 API(Whisper·MeloTTS·Ollama)는 test double 로 대체하되,
모듈 간 데이터 계약(입력/출력 schema)은 프로덕션과 동일하게 유지한다.
"""

import json

# ── 샘플 음성 입력 (STT 는 mock 이므로 내용은 비-실오디오 바이트면 충분) ──
SAMPLE_AUDIO_BYTES = b"RIFF$\x00\x00\x00WAVEfmt test-audio-bytes"

# ── 샘플 인식 텍스트 (STT double 이 반환할 transcript) ──
TRANSCRIPT_NORMAL = "나도 같이 놀고 싶어"
TRANSCRIPT_REPEAT = "공 공 공 공"          # repetition_detected 유발
TRANSCRIPT_SHORT = "응"                     # 너무 짧은/의미 적은 발화
TRANSCRIPT_EMPTY = ""                        # 빈 인식 결과

# ── 샘플 시나리오 (scenario_catalog 에 존재하는 id) ──
SCENARIO_ID = "playground_greeting"          # 놀이터/greeting/low
SCENARIO_UNKNOWN = "nonexistent-scenario"    # 카탈로그에 없음 → unknown 처리

# ── 샘플 감정/시선/랜드마크 데이터 (프런트 비전 모듈 산출물) ──
FACIAL_EMOTION_SAD = "sad"                   # → 융합 시 frustrated
FACIAL_EMOTION_HAPPY = "happy"
EMOTION_SAMPLE = {"label": "sad", "confidence": 0.82, "timestamp": 1_700_000_000_000}
GAZE_SAMPLES = [
    {"direction": "center", "irisPos": 0.50, "timestamp": 1_700_000_000_000},
    {"direction": "center", "irisPos": 0.52, "timestamp": 1_700_000_001_000},
    {"direction": "left", "irisPos": 0.70, "timestamp": 1_700_000_002_000},
    {"direction": "right", "irisPos": 0.30, "timestamp": 1_700_000_003_000},
]

# ── 샘플 대화 히스토리 ──
HISTORY_EMPTY: list[dict] = []
HISTORY_ACCUMULATED = [
    {"role": "user", "content": "안녕"},
    {"role": "assistant", "content": "안녕! 나는 미래야. 너도 같이 놀래?"},
]

# ── 샘플 LLM 응답 (Ollama double 이 반환할 RP 출력 JSON) ──
RP_RESPONSE = {
    "child_message": "좋아! 같이 술래잡기 하자. 너가 술래 할래?",
    "avatar_expression": "happy",
    "tts_style": {"speed": "normal", "tone": "cheerful", "pause_after_ms": 300},
    "detected": {
        "emotion": "happy",
        "social_skill": "joining_play",
        "utterance_type": "appropriate_response",
        "engagement": "high",
    },
    "coaching": {
        "strategy": "praise",
        "next_goal": "역할을 정해서 말해보기",
        "difficulty_next": "low",
        "reason": "시도를 칭찬하고 다음 행동을 제안",
    },
    "report_event": {
        "turn_success": True,
        "child_attempt_observed": True,
        "response_length": "sentence",
        "conversation_continued": True,
        "notes_for_guardian": "친구 놀이에 적극적으로 참여하려 했어요.",
    },
    "safety": {"risk_flag": "none", "requires_adult_attention": False},
}
RP_RESPONSE_JSON = json.dumps(RP_RESPONSE, ensure_ascii=False)
RP_RESPONSE_EMPTY_MESSAGE = json.dumps({"child_message": "", "coaching": {}}, ensure_ascii=False)
RP_RESPONSE_INVALID = "이건 JSON 이 아니라 그냥 텍스트"

# ── 샘플 TTS 결과 (MeloTTS double 이 반환할 file id) ──
TTS_AUDIO_ID = "test-audio-0001"
