from dataclasses import dataclass
from datetime import datetime

from starlette.concurrency import run_in_threadpool

from app.schemas.speech import LlmModuleResponse, SpeechAnalysisRequest, SpeechAnalysisResponse
from app.services.llm_client import LlmClient
from app.services.session_store import append_turn, read_session, read_turns
from app.services.speech_analysis import analyze_speech
from app.services.scenario_catalog import get_scenario_context
from app.services.tts_service import try_generate_tts
from app.services.vision_fusion import avatar_state_for, fuse_emotion


@dataclass
class DialogueTurnResult:
    analysis: SpeechAnalysisResponse
    llm: LlmModuleResponse
    audio_file_id: str | None
    emotion: str
    avatar_state: str


async def process_transcript(
    *,
    session_id: str,
    turn_id: str,
    transcript: str,
    duration_seconds: float | None = None,
    response_requested_at: datetime | None = None,
    response_started_at: datetime | None = None,
    stt_model: str | None = None,
    stt_time_seconds: float | None = None,
    facial_emotion: str | None = None,
) -> DialogueTurnResult:
    analysis = analyze_speech(
        SpeechAnalysisRequest(
            transcript=transcript,
            duration_seconds=duration_seconds,
            response_requested_at=response_requested_at,
            response_started_at=response_started_at,
        )
    )
    # 표정(YOLOv8)·음성 분석을 융합한 최종 감정
    emotion = fuse_emotion(analysis.flags, facial_emotion)

    # LLM 프롬프트에 비전 컨텍스트(감정/표정) 주입
    child_profile = session_context(session_id)
    child_profile.update({"facial_emotion": facial_emotion or "unknown", "fused_emotion": emotion})

    llm = await LlmClient().respond(
        session_id=session_id,
        transcript=analysis.transcript,
        analysis=analysis,
        conversation_history=conversation_history(session_id),
        child_profile=child_profile,
    )
    append_turn(
        session_id=session_id,
        turn_id=turn_id,
        transcript=analysis.transcript,
        analysis=analysis,
        llm=llm,
        stt_model=stt_model,
        stt_time_seconds=stt_time_seconds,
    )
    audio_file_id = await run_in_threadpool(
        try_generate_tts,
        llm.therapist_reply,
        1.1,
    )
    return DialogueTurnResult(
        analysis=analysis,
        llm=llm,
        audio_file_id=audio_file_id,
        emotion=emotion,
        avatar_state=avatar_state_for(emotion),
    )


def conversation_history(session_id: str) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for turn in read_turns(session_id):
        history.append({"role": "user", "content": turn.transcript})
        history.append({"role": "assistant", "content": turn.llm.therapist_reply})
    return history


def session_context(session_id: str) -> dict[str, str]:
    session = read_session(session_id)
    if session is None:
        return {}
    context = {"child_id": session.child_id, "scenario_id": session.scenario_id}
    context.update(get_scenario_context(session.scenario_id))
    return context
