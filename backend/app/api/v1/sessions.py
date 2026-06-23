from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.schemas.speech import (
    SessionCreateRequest,
    SessionEndRequest,
    SessionLogResponse,
    SessionResponse,
    WebSocketClientEvent,
)
from app.services.dialogue_pipeline import process_transcript
from app.services.session_store import (
    create_session,
    end_session,
    read_session,
    read_turns,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
def start_session(payload: SessionCreateRequest):
    return create_session(
        scenario_id=payload.scenario_id,
        child_id=payload.child_id,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str):
    session = read_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/end", response_model=SessionResponse)
def finish_session(session_id: str, payload: SessionEndRequest):
    session = end_session(session_id, payload.status)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{session_id}/logs", response_model=SessionLogResponse)
def get_session_logs(session_id: str):
    return SessionLogResponse(session_id=session_id, turns=read_turns(session_id))


@router.websocket("/{session_id}/ws")
async def session_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            try:
                event = WebSocketClientEvent(**data)
            except ValidationError as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {
                            "message": "잘못된 대화 메시지 형식입니다.",
                            "recoverable": True,
                            "details": exc.errors(),
                        },
                    }
                )
                continue

            await websocket.send_json(
                {
                    "type": "stt_result",
                    "payload": {"text": event.payload.text, "turn_id": event.turn_id},
                }
            )
            await websocket.send_json(
                {"type": "avatar_state", "payload": {"avatar_state": "thinking"}}
            )

            response_started_at = datetime.now(timezone.utc)
            response_requested_at = None
            if event.payload.response_time_ms is not None:
                response_requested_at = response_started_at - timedelta(
                    milliseconds=event.payload.response_time_ms
                )

            result = await process_transcript(
                session_id=session_id,
                turn_id=str(event.turn_id),
                transcript=event.payload.text,
                duration_seconds=event.payload.duration_seconds,
                response_requested_at=response_requested_at,
                response_started_at=response_started_at,
            )
            audio_url = None
            if result.audio_file_id:
                scheme = "https" if websocket.url.scheme == "wss" else "http"
                audio_url = (
                    f"{scheme}://{websocket.url.netloc}/api/v1/audio/"
                    f"{result.audio_file_id}.wav"
                )
            await websocket.send_json(
                {
                    "type": "ai_response",
                    "payload": {
                        "text": result.llm.therapist_reply,
                        "emotion": result.emotion,
                        "audio_url": audio_url,
                        "avatar_state": result.avatar_state,
                        "turn_id": event.turn_id,
                    },
                }
            )
    except WebSocketDisconnect:
        return
