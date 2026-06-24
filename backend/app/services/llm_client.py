"""LLM 클라이언트 — Ollama(/api/chat)로 마주톡 또래친구 모델을 호출한다.

- 시스템 프롬프트: ai/prompts/RP_system_prompt_runtime.md (단일 출처, 경로는 RP_PROMPT_PATH)
- 입력: RP 프롬프트가 정의한 JSON (scenario/difficulty/emotion_state/child_input/
  observed_features/conversation_history)
- 출력: RP 프롬프트가 정의한 JSON(child_message, coaching, detected, safety …)을
  파싱해 LlmModuleResponse 로 변환
- OLLAMA_URL 이 비어있거나 호출 실패 시 규칙기반 fallback (서비스 항상 응답 보장)
"""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import httpx

from app.schemas.speech import LlmModuleResponse, SpeechAnalysisResponse

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROMPT_PATH = REPO_ROOT / "ai" / "prompts" / "RP_system_prompt_runtime.md"

# speech_analysis flag → RP 프롬프트 observed_features 매핑
FLAG_TO_FEATURE = {
    "response_latency_delayed": "long_pause",
    "repetition_detected": "repeated_phrase",
}
# RP 프롬프트가 허용하는 emotion_state enum
EMOTION_STATES = {"happy", "neutral", "anxious", "confused", "frustrated", "shy"}

_MINIMAL_PROMPT = (
    "너는 마주톡의 또래 친구 역할 AI다. 5~8세 아동에게 항상 한국어로, 짧고 다정하게, "
    "한 번에 한 가지만 제안하며 응답한다. 반드시 child_message/coaching 필드를 가진 "
    "JSON 객체 하나로만 답한다."
)


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    path = Path(os.getenv("RP_PROMPT_PATH", str(DEFAULT_PROMPT_PATH)))
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("RP system prompt not found at %s; using minimal prompt", path)
        return _MINIMAL_PROMPT


class LlmClient:
    def __init__(self) -> None:
        # Ollama 서비스 주소. 비어있으면 규칙기반 fallback.
        self.base_url = (os.getenv("OLLAMA_URL") or os.getenv("AI_SERVICE_URL") or "").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "mazutalk")
        self.timeout = float(os.getenv("AI_SERVICE_TIMEOUT", "60"))

    async def respond(
        self,
        *,
        session_id: str,
        transcript: str,
        analysis: SpeechAnalysisResponse,
        conversation_history: list[dict[str, str]],
        child_profile: dict[str, Any],
    ) -> LlmModuleResponse:
        if not self.base_url:
            return fallback_response(transcript, analysis)

        user_content = build_user_content(transcript, analysis, conversation_history, child_profile)
        try:
            content = await self._chat(user_content)
            return parse_llm_output(content, self.model) or fallback_response(transcript, analysis)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("LLM call failed (%s); using rule-based fallback", exc)
            return fallback_response(transcript, analysis)

    async def _chat(self, user_content: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": load_system_prompt()},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "format": "json",  # 유효한 JSON 강제
            "think": False,  # Qwen3 thinking 비활성 (지원 안 하면 무시됨)
            "options": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "num_predict": 1024},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
        return body["message"]["content"]


def build_user_content(
    transcript: str,
    analysis: SpeechAnalysisResponse,
    conversation_history: list[dict[str, str]],
    child_profile: dict[str, Any],
) -> str:
    emotion = child_profile.get("fused_emotion") or "unknown"
    if emotion not in EMOTION_STATES:
        emotion = "unknown"
    observed = [FLAG_TO_FEATURE[flag] for flag in analysis.flags if flag in FLAG_TO_FEATURE]

    payload = {
        "scenario": {
            "id": child_profile.get("scenario_id", "unknown"),
            "location": child_profile.get("location", "unknown"),
            "situation": child_profile.get("situation", "unknown"),
            "ai_role": child_profile.get("ai_role", "peer_friend"),
            "target_skill": child_profile.get("target_skill", "unknown"),
            "goal": child_profile.get("goal", "unknown"),
        },
        "difficulty": child_profile.get("difficulty", "unknown"),
        "emotion_state": emotion,
        "child_input": transcript,
        "observed_features": observed,
        "conversation_history": conversation_history,
    }
    return json.dumps(payload, ensure_ascii=False)


def parse_llm_output(content: str, model_name: str) -> LlmModuleResponse | None:
    """RP 출력 JSON → LlmModuleResponse. 형식이 어긋나면 None(→ fallback)."""
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        logger.warning("LLM output was not valid JSON")
        return None
    if not isinstance(obj, dict):
        return None

    child_message = str(obj.get("child_message") or "").strip()
    if not child_message:
        return None

    coaching = obj.get("coaching") or {}
    next_prompt = str(coaching.get("next_goal") or "").strip()
    cues: list[str] = []
    if coaching.get("strategy"):
        cues.append(str(coaching["strategy"]))
    if coaching.get("reason"):
        cues.append(str(coaching["reason"]))

    return LlmModuleResponse(
        therapist_reply=child_message,
        next_prompt=next_prompt or "그 다음에는 어떤 일이 있었나요?",
        coaching_cues=cues,
        model_name=model_name,
    )


def fallback_response(transcript: str, analysis: SpeechAnalysisResponse) -> LlmModuleResponse:
    if "repetition_detected" in analysis.flags:
        therapist_reply = f"좋아요. 방금 '{transcript}'라고 말했네요. 같은 뜻으로 한 번 더 짧게 말해볼까요?"
        next_prompt = "이번에는 핵심 단어 하나를 골라서 말해 주세요."
    elif "speech_rate_fast" in analysis.flags:
        therapist_reply = "좋아요, 말하고 싶은 게 많았군요. 이번에는 천천히 한 문장으로 다시 말해볼까요?"
        next_prompt = "숨을 한 번 쉬고, 가장 중요한 말부터 해 주세요."
    elif "response_latency_delayed" in analysis.flags:
        therapist_reply = "기다려줘서 고마워요. 천천히 생각해도 괜찮아요."
        next_prompt = "좋아하는 것과 싫어하는 것 중 하나를 골라 말해 주세요."
    else:
        therapist_reply = f"잘 말했어요. '{transcript}'라고 이야기해 주었네요."
        next_prompt = "그 다음에는 어떤 일이 있었나요?"

    return LlmModuleResponse(
        therapist_reply=therapist_reply,
        next_prompt=next_prompt,
        coaching_cues=analysis.coaching_tips,
        model_name="backend-fallback-rule-model",
    )
