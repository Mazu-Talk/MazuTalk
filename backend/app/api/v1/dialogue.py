from fastapi import APIRouter

from app.schemas.speech import SttToLlmRequest, SttToLlmResponse
from app.services.llm_client import LlmClient
from app.services.session_store import append_turn, new_turn_id
from app.services.speech_analysis import analyze_speech

router = APIRouter(prefix="/dialogue", tags=["dialogue"])


@router.post("/stt-to-llm", response_model=SttToLlmResponse)
async def stt_to_llm(payload: SttToLlmRequest):
    turn_id = payload.turn_id or new_turn_id()
    analysis = analyze_speech(payload.stt_result)
    llm = await LlmClient().respond(
        session_id=payload.session_id,
        transcript=analysis.transcript,
        analysis=analysis,
        conversation_history=[
            message.dict() for message in payload.conversation_history
        ],
        child_profile=payload.child_profile,
    )
    append_turn(
        session_id=payload.session_id,
        turn_id=turn_id,
        transcript=analysis.transcript,
        analysis=analysis,
        llm=llm,
    )
    return SttToLlmResponse(
        session_id=payload.session_id,
        turn_id=turn_id,
        analysis=analysis,
        llm=llm,
    )
