from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas.speech import (
    SessionLogResponse,
    SpeechAnalysisRequest,
    SttToLlmResponse,
    WebSocketTurnRequest,
)
from app.services.llm_client import LlmClient
from app.services.session_store import append_turn, new_turn_id, read_turns
from app.services.speech_analysis import analyze_speech

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}/logs", response_model=SessionLogResponse)
def get_session_logs(session_id: str):
    return SessionLogResponse(session_id=session_id, turns=read_turns(session_id))


@router.websocket("/{session_id}/ws")
async def session_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            payload = WebSocketTurnRequest(**data)
            turn_id = payload.turn_id or new_turn_id()
            analysis = analyze_speech(
                SpeechAnalysisRequest(
                    transcript=payload.transcript,
                    duration_seconds=payload.duration_seconds,
                    response_requested_at=payload.response_requested_at,
                    response_started_at=payload.response_started_at,
                )
            )
            llm = await LlmClient().respond(
                session_id=session_id,
                transcript=analysis.transcript,
                analysis=analysis,
                conversation_history=[],
                child_profile={},
            )
            append_turn(
                session_id=session_id,
                turn_id=turn_id,
                transcript=analysis.transcript,
                analysis=analysis,
                llm=llm,
            )
            response = SttToLlmResponse(
                session_id=session_id,
                turn_id=turn_id,
                analysis=analysis,
                llm=llm,
            )
            await websocket.send_json(response.dict())
    except WebSocketDisconnect:
        return
