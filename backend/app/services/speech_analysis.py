import re
from collections import Counter

from app.schemas.speech import (
    RepeatedExpression,
    ResponseLatency,
    SpeechAnalysisRequest,
    SpeechAnalysisResponse,
    SpeechPace,
)

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
KOREAN_SYLLABLE_RE = re.compile(r"[가-힣]")
FILLER_WORDS = {"음", "어", "아", "그", "저", "막", "이제", "그러니까", "뭐지"}


def analyze_speech(payload: SpeechAnalysisRequest) -> SpeechAnalysisResponse:
    transcript = normalize_space(payload.transcript)
    tokens = tokenize(transcript)
    duration = resolve_duration_seconds(payload)
    word_count = len(tokens)
    syllable_count = len(KOREAN_SYLLABLE_RE.findall(transcript))
    words_per_minute = round(word_count / duration * 60, 2) if duration > 0 else 0
    syllables_per_second = round(syllable_count / duration, 2) if duration > 0 else 0

    repeated_expressions = detect_repeated_expressions(tokens)
    repetition_score = calculate_repetition_score(tokens, repeated_expressions)
    latency = calculate_response_latency(payload)
    pace_label = label_pace(words_per_minute)

    flags = build_flags(pace_label, repeated_expressions, repetition_score, latency)
    coaching_tips = build_coaching_tips(flags)

    return SpeechAnalysisResponse(
        transcript=transcript,
        duration_seconds=round(duration, 2),
        word_count=word_count,
        syllable_count=syllable_count,
        pace=SpeechPace(
            words_per_minute=words_per_minute,
            syllables_per_second=syllables_per_second,
            label=pace_label,
        ),
        repeated_expressions=repeated_expressions,
        repetition_score=repetition_score,
        response_latency=latency,
        flags=flags,
        coaching_tips=coaching_tips,
    )


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def resolve_duration_seconds(payload: SpeechAnalysisRequest) -> float:
    if payload.duration_seconds:
        return payload.duration_seconds

    if payload.utterance_started_at and payload.utterance_ended_at:
        duration = (payload.utterance_ended_at - payload.utterance_started_at).total_seconds()
        if duration > 0:
            return duration

    segment_bounds = [
        (segment.start_seconds, segment.end_seconds)
        for segment in payload.segments
        if segment.start_seconds is not None and segment.end_seconds is not None
    ]
    if segment_bounds:
        start = min(bound[0] for bound in segment_bounds if bound[0] is not None)
        end = max(bound[1] for bound in segment_bounds if bound[1] is not None)
        if end > start:
            return end - start

    tokens = tokenize(payload.transcript)
    return max(len(tokens) * 0.45, 1.0)


def detect_repeated_expressions(tokens: list[str]) -> list[RepeatedExpression]:
    repeated: dict[tuple[str, str], RepeatedExpression] = {}

    for token, count in Counter(tokens).items():
        if count >= 3 or (token in FILLER_WORDS and count >= 2):
            repeated[("word", token)] = RepeatedExpression(
                expression=token,
                count=count,
                type="filler" if token in FILLER_WORDS else "word",
            )

    for index in range(1, len(tokens)):
        if tokens[index] == tokens[index - 1]:
            token = tokens[index]
            current = repeated.get(("consecutive", token))
            repeated[("consecutive", token)] = RepeatedExpression(
                expression=token,
                count=(current.count + 1 if current else 2),
                type="consecutive",
            )

    for size in (2, 3):
        grams = [" ".join(tokens[i : i + size]) for i in range(0, len(tokens) - size + 1)]
        for gram, count in Counter(grams).items():
            if count >= 2 and len(set(gram.split())) > 1:
                repeated[("phrase", gram)] = RepeatedExpression(
                    expression=gram,
                    count=count,
                    type="phrase",
                )

    return sorted(repeated.values(), key=lambda item: (-item.count, item.expression))[:10]


def calculate_repetition_score(tokens: list[str], repeated: list[RepeatedExpression]) -> float:
    if not tokens:
        return 0.0

    repeated_weight = 0
    for item in repeated:
        expression_length = len(item.expression.split())
        repeated_weight += item.count * expression_length

    return round(min(repeated_weight / len(tokens), 1.0), 2)


def calculate_response_latency(payload: SpeechAnalysisRequest) -> ResponseLatency:
    if not payload.response_requested_at or not payload.response_started_at:
        return ResponseLatency(seconds=None, label="unknown")

    seconds = (payload.response_started_at - payload.response_requested_at).total_seconds()
    if seconds < 0:
        return ResponseLatency(seconds=None, label="invalid")
    if seconds <= 1.5:
        label = "quick"
    elif seconds <= 4:
        label = "normal"
    else:
        label = "delayed"
    return ResponseLatency(seconds=round(seconds, 2), label=label)


def label_pace(words_per_minute: float) -> str:
    if words_per_minute < 70:
        return "slow"
    if words_per_minute > 160:
        return "fast"
    return "normal"


def build_flags(
    pace_label: str,
    repeated: list[RepeatedExpression],
    repetition_score: float,
    latency: ResponseLatency,
) -> list[str]:
    flags: list[str] = []
    if pace_label == "fast":
        flags.append("speech_rate_fast")
    elif pace_label == "slow":
        flags.append("speech_rate_slow")
    if repeated and repetition_score >= 0.25:
        flags.append("repetition_detected")
    if latency.label == "delayed":
        flags.append("response_latency_delayed")
    return flags


def build_coaching_tips(flags: list[str]) -> list[str]:
    tips: list[str] = []
    if "speech_rate_fast" in flags:
        tips.append("말이 빨라졌어요. 짧은 문장으로 다시 말하도록 유도해 주세요.")
    if "speech_rate_slow" in flags:
        tips.append("응답 속도가 느립니다. 충분히 기다린 뒤 선택지를 하나씩 제시해 주세요.")
    if "repetition_detected" in flags:
        tips.append("반복 표현이 보여요. 같은 뜻의 다른 표현을 모델링해 주세요.")
    if "response_latency_delayed" in flags:
        tips.append("응답 지연이 길어요. 질문을 더 구체적이고 짧게 바꿔 주세요.")
    if not tips:
        tips.append("현재 발화 흐름은 안정적입니다. 자연스럽게 다음 대화를 이어가세요.")
    return tips
