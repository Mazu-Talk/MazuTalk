"""표정(YOLOv8)·음성 분석 감정을 하나의 최종 감정으로 융합한다.

- 음성 분석 flag(`infer_emotion`)는 행동 신호(응답 지연·반복·말 속도)에 강하다.
- 표정 분류(facial_emotion)는 즉각적인 정서 표현(happy/sad/surprised)에 강하다.

융합 원칙: 행동 신호가 비중립이면 그것을 우선(신뢰도 높음)하고,
중립일 때만 표정 신호로 채운다. 둘 다 없으면 'neutral'.
"""

# YOLOv8 표정 클래스 → 도메인 감정(Emotion) 매핑
FACIAL_TO_EMOTION = {
    "happy": "happy",
    "neutral": "neutral",
    "sad": "frustrated",   # 속상함
    "surprised": "confused",
}


def infer_speech_emotion(flags: list[str]) -> str:
    """음성 분석 flag 기반 감정 추정 (기존 dialogue_pipeline.infer_emotion 이전)."""
    if "response_latency_delayed" in flags:
        return "anxious"
    if "repetition_detected" in flags:
        return "confused"
    if "speech_rate_slow" in flags:
        return "shy"
    return "neutral"


def map_facial_emotion(facial_emotion: str | None) -> str:
    if not facial_emotion:
        return "neutral"
    return FACIAL_TO_EMOTION.get(facial_emotion.strip().lower(), "neutral")


def fuse_emotion(flags: list[str], facial_emotion: str | None) -> str:
    """행동(음성) 신호 우선, 중립이면 표정 신호로 보완."""
    speech_emotion = infer_speech_emotion(flags)
    if speech_emotion != "neutral":
        return speech_emotion
    return map_facial_emotion(facial_emotion)


def avatar_state_for(emotion: str) -> str:
    if emotion in {"anxious", "confused", "shy", "frustrated"}:
        return "encouraging"
    return "speaking"
