import os
from typing import Any

import httpx

from app.schemas.speech import LlmModuleResponse, SpeechAnalysisResponse


class LlmClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("AI_SERVICE_URL", "").rstrip("/")
        self.timeout = float(os.getenv("AI_SERVICE_TIMEOUT", "15"))

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

        payload = {
            "session_id": session_id,
            "transcript": transcript,
            "analysis": analysis.dict(),
            "conversation_history": conversation_history,
            "child_profile": child_profile,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/v1/chat/respond", json=payload)
                response.raise_for_status()
                return LlmModuleResponse(**response.json())
        except (httpx.HTTPError, ValueError):
            return fallback_response(transcript, analysis)


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
