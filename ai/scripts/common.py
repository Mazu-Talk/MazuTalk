"""MazuTalk post-training 공용 모듈.

SoT(`ai/prompts/RP_system_prompt.md`, `ai/schemas/scenario_schema.json`)에서
파생한 enum/contract, 시나리오 -> 런타임 입력 변환, Ollama 클라이언트,
출력 JSON 스키마, 금지표현, 코칭 전략 기대맵을 한곳에 모은다.

모든 post-training 스크립트는 이 모듈을 import 한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import urllib.error
import urllib.request


# --------------------------------------------------------------------------
# 경로
# --------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]
AI_DIR = ROOT_DIR / "ai"
# SoT: 행동 원칙의 최종 기준 (전문)
PROMPT_PATH = AI_DIR / "prompts" / "RP_system_prompt.md"
# 런타임/학습/서빙에 실제로 쓰는 축약 system prompt (SoT 파생).
# 4B 모델은 전문 프롬프트에서 degenerate 하므로 축약본을 일관 사용한다(train/serve skew 방지).
RUNTIME_PROMPT_PATH = AI_DIR / "prompts" / "RP_system_prompt_runtime.md"
SCENARIO_SCHEMA_PATH = AI_DIR / "schemas" / "scenario_schema.json"
SCENARIO_DIR = AI_DIR / "data" / "scenarios"
PROCESSED_DIR = AI_DIR / "data" / "processed"
CONFIG_DIR = AI_DIR / "configs"


# --------------------------------------------------------------------------
# SoT enum (RP_system_prompt.md 기준)
# --------------------------------------------------------------------------

EMOTION_STATES = [
    "happy", "neutral", "anxious", "confused", "frustrated", "shy", "unknown",
]

UTTERANCE_TYPES = [
    "appropriate_response", "partial_response", "no_response",
    "echolalia", "off_topic", "non_linguistic", "unclear",
]

OBSERVED_FEATURE_KEYS = [
    "long_pause", "echolalia", "off_topic", "non_linguistic_sound", "repeated_phrase",
]

AVATAR_EXPRESSIONS = [
    "neutral", "happy", "gentle", "concerned", "encouraging", "playful",
]

TTS_SPEEDS = ["slow", "normal"]
TTS_TONES = ["warm", "calm", "cheerful"]

ENGAGEMENT_LEVELS = ["high", "medium", "low", "unknown"]

COACHING_STRATEGIES = [
    "natural_response", "praise", "choice_prompt", "model_sentence",
    "gentle_redirect", "simplify_question", "emotion_labeling",
    "repair_prompt", "close_session",
]

DIFFICULTIES = ["low", "medium", "high"]

RISK_FLAGS = [
    "none", "distress", "aggression", "self_harm", "abuse", "medical", "privacy",
]
RISK_FLAGS_NONZERO = [f for f in RISK_FLAGS if f != "none"]

SOCIAL_SKILLS = [
    "greeting", "self_introduction", "asking_question", "answering_question",
    "emotion_expression", "emotion_recognition", "requesting_help",
    "joining_play", "suggesting_play", "turn_taking", "sharing", "refusal",
    "apology", "conflict_resolution", "conversation_continuation", "goodbye",
    "unknown",
]

RESPONSE_LENGTHS = ["none", "single_word", "short_phrase", "sentence"]


# --------------------------------------------------------------------------
# 시나리오 -> 런타임 입력 변환 매핑 (계획서 §3 기준)
# --------------------------------------------------------------------------

DIFFICULTY_MAP = {"easy": "low", "medium": "medium", "hard": "high"}

PLACE_MAP = {
    "playground": "놀이터",
    "kindergarten_classroom": "유치원 교실",
    "kindergarten_playroom": "유치원 놀이방",
    "kindergarten_art_room": "유치원 미술실",
}


# --------------------------------------------------------------------------
# 금지 표현 (RP_system_prompt.md §4 나쁜 예 / §13 사용 금지 / 계획서 §5.1 G)
# child_message 에 등장하면 위반으로 본다. 일상어와 겹치는 표현은 제외.
# --------------------------------------------------------------------------

FORBIDDEN_PHRASES = [
    "틀렸어", "틀린 말", "왜 못", "왜 대답을 안", "왜 안 해", "제대로 말해",
    "다시 제대로", "그렇게 말하면 안", "사회성이 부족", "이상해",
    "친구들이 싫어", "친구가 싫어", "진단", "치료 효과", "비정상", "정상이 아",
    "너는 문제", "실패했",
]


# --------------------------------------------------------------------------
# 감정/발화 상태별 기대 코칭 전략 (계획서 §5.1 E)
# --------------------------------------------------------------------------

EXPECTED_STRATEGY: dict[str, list[str]] = {
    "happy": ["natural_response", "praise"],
    "neutral": ["natural_response", "praise"],
    "no_response": ["choice_prompt", "simplify_question", "model_sentence"],
    "anxious": ["simplify_question", "choice_prompt", "praise"],
    "confused": ["simplify_question", "model_sentence"],
    "frustrated": ["emotion_labeling", "repair_prompt", "choice_prompt"],
    "shy": ["model_sentence", "praise", "choice_prompt"],
    "off_topic": ["gentle_redirect"],
    "echolalia": ["choice_prompt", "gentle_redirect"],
}


# --------------------------------------------------------------------------
# 출력 JSON 스키마 (RP_system_prompt.md §7)
# --------------------------------------------------------------------------

OUTPUT_REQUIRED_FIELDS = [
    "child_message", "avatar_expression", "tts_style",
    "detected", "coaching", "report_event", "safety",
]


def build_output_schema() -> dict[str, Any]:
    """모델 출력 검증용 JSON Schema (Draft 2020-12)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": OUTPUT_REQUIRED_FIELDS,
        "properties": {
            "child_message": {"type": "string", "minLength": 1},
            "avatar_expression": {"enum": AVATAR_EXPRESSIONS},
            "tts_style": {
                "type": "object",
                "required": ["speed", "tone", "pause_after_ms"],
                "properties": {
                    "speed": {"enum": TTS_SPEEDS},
                    "tone": {"enum": TTS_TONES},
                    "pause_after_ms": {"type": "number"},
                },
            },
            "detected": {
                "type": "object",
                "required": ["emotion", "social_skill", "utterance_type", "engagement"],
                "properties": {
                    "emotion": {"enum": EMOTION_STATES},
                    "social_skill": {"enum": SOCIAL_SKILLS},
                    "utterance_type": {"enum": UTTERANCE_TYPES},
                    "engagement": {"enum": ENGAGEMENT_LEVELS},
                },
            },
            "coaching": {
                "type": "object",
                "required": ["strategy", "next_goal", "difficulty_next", "reason"],
                "properties": {
                    "strategy": {"enum": COACHING_STRATEGIES},
                    "next_goal": {"type": "string"},
                    "difficulty_next": {"enum": DIFFICULTIES},
                    "reason": {"type": "string"},
                },
            },
            "report_event": {
                "type": "object",
                "required": [
                    "turn_success", "child_attempt_observed",
                    "response_length", "conversation_continued", "notes_for_guardian",
                ],
                "properties": {
                    "turn_success": {"type": "boolean"},
                    "child_attempt_observed": {"type": "boolean"},
                    "response_length": {"enum": RESPONSE_LENGTHS},
                    "conversation_continued": {"type": "boolean"},
                    "notes_for_guardian": {"type": "string"},
                },
            },
            "safety": {
                "type": "object",
                "required": ["risk_flag", "requires_adult_attention"],
                "properties": {
                    "risk_flag": {"enum": RISK_FLAGS},
                    "requires_adult_attention": {"type": "boolean"},
                },
            },
        },
    }


# --------------------------------------------------------------------------
# IO 유틸
# --------------------------------------------------------------------------

def load_system_prompt(runtime: bool = True) -> str:
    """런타임/학습/서빙용 system prompt. runtime=False 면 SoT 전문."""
    path = RUNTIME_PROMPT_PATH if runtime and RUNTIME_PROMPT_PATH.exists() else PROMPT_PATH
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_scenarios() -> list[dict[str, Any]]:
    files = sorted(SCENARIO_DIR.rglob("*.json"))
    return [load_json(p) for p in files]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# --------------------------------------------------------------------------
# 시나리오 -> 런타임 입력 변환
# --------------------------------------------------------------------------

def scenario_to_runtime(
    scenario: dict[str, Any],
    *,
    target_skill: str,
    difficulty: str,
    emotion_state: str,
    child_input: str,
    observed_features: dict[str, bool] | None = None,
    child_age: int = 6,
) -> dict[str, Any]:
    """시나리오 파일 + turn 파라미터 -> RP_system_prompt §6 런타임 입력 JSON."""
    ctx = scenario.get("context", {})
    feats = {key: False for key in OBSERVED_FEATURE_KEYS}
    if observed_features:
        feats.update({k: v for k, v in observed_features.items() if k in feats})
    return {
        "child_age": child_age,
        "scenario": {
            "id": scenario.get("scenarioId", "unknown"),
            "location": PLACE_MAP.get(ctx.get("place", ""), ctx.get("place", "")),
            "situation": ctx.get("situation", ""),
            "ai_role": "peer_friend",
            "target_skill": target_skill,
            "goal": (scenario.get("learningGoal") or [""])[0],
        },
        "difficulty": difficulty,
        "emotion_state": emotion_state,
        "child_input": child_input,
        "observed_features": feats,
    }


# --------------------------------------------------------------------------
# Ollama 클라이언트 (stdlib만 사용)
# --------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"


# Qwen3 비-thinking 권장 샘플링값. greedy(temp 0)는 반복 degenerate 를 유발하므로
# 평가에서는 temp>0 + 고정 seed 로 재현성을 확보한다.
DEFAULT_SEED = 42


def ollama_chat(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    top_p: float = 0.8,
    top_k: int = 20,
    presence_penalty: float | None = None,
    seed: int | None = DEFAULT_SEED,
    num_predict: int = 1024,
    think: bool = False,
    force_json: bool = False,
    timeout: int = 300,
) -> str:
    """Ollama /api/chat 호출. assistant content(문자열) 반환.

    Qwen3 계열 thinking 비활성화를 위해 think=false 를 보낸다.
    모델이 thinking 미지원이면 해당 필드 없이 1회 재시도한다.
    force_json=True 면 Ollama format="json" 강제(서빙용). baseline 측정에서는
    모델의 실제 형식 준수율을 보기 위해 기본 False.
    """
    options: dict[str, Any] = {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "num_predict": num_predict,
    }
    if presence_penalty is not None:
        options["presence_penalty"] = presence_penalty
    if seed is not None:
        options["seed"] = seed
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": options,
    }
    if force_json:
        payload["format"] = "json"

    def _post(body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_URL, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        result = _post(payload)
    except urllib.error.HTTPError as exc:
        # thinking 미지원 모델 등 -> think 필드 제거 후 재시도
        payload.pop("think", None)
        try:
            result = _post(payload)
        except urllib.error.HTTPError as exc2:
            raise RuntimeError(f"Ollama HTTPError: {exc2.code} {exc2.read()!r}") from exc

    return result.get("message", {}).get("content", "")


# --------------------------------------------------------------------------
# OpenAI 클라이언트 (teacher 용) — OPENAI_API_KEY 환경변수 필요
# --------------------------------------------------------------------------

def openai_chat(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    seed: int | None = DEFAULT_SEED,
    max_tokens: int = 1024,
    force_json: bool = True,
    timeout: int = 120,
) -> str:
    """OpenAI Chat Completions 호출. assistant content(문자열) 반환.

    force_json=True 면 response_format=json_object 로 JSON 출력을 강제한다
    (teacher 데이터 품질·파싱 안정성 ↑). seed 고정으로 재현성 확보.
    `openai` 패키지와 OPENAI_API_KEY 가 필요하다.
    """
    from openai import OpenAI  # 지연 import (로컬 baseline 경로엔 불필요)

    client = OpenAI(timeout=timeout)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        kwargs["seed"] = seed
    if force_json:
        # response_format=json_object 사용 시 프롬프트에 'json' 토큰이 있어야 함
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def teacher_generate(
    backend: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_new: int = 1024,
    seed: int | None = DEFAULT_SEED,
) -> str:
    """teacher 백엔드 디스패처. backend in {'ollama','openai'}."""
    if backend == "openai":
        return openai_chat(model, messages, temperature=temperature,
                           max_tokens=max_new, seed=seed)
    return ollama_chat(model, messages, temperature=temperature,
                       num_predict=max_new, think=False, seed=seed)


# 백엔드별 기본 teacher 모델
DEFAULT_TEACHER = {"ollama": "qwen3.5:4b", "openai": "gpt-4o-mini"}


# --------------------------------------------------------------------------
# 출력 파싱/검증
# --------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_QUESTION_RE = re.compile(r"[?？]")


def strip_thinking(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


def extract_json(text: str) -> dict[str, Any] | None:
    """모델 출력에서 JSON 객체를 추출. 실패 시 None."""
    cleaned = strip_thinking(text)
    # 1) 통째로 파싱 시도
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 2) 코드펜스 제거 후 첫 { ... } 블록
    cleaned = cleaned.replace("```json", "").replace("```", "")
    match = _JSON_BLOCK_RE.search(cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def count_questions(text: str) -> int:
    return len(_QUESTION_RE.findall(text))


def count_sentences(text: str) -> int:
    parts = [p for p in re.split(r"[.!?。！？\n]+", text.strip()) if p.strip()]
    return len(parts)


def find_forbidden(text: str) -> list[str]:
    return [p for p in FORBIDDEN_PHRASES if p in text]
