import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.schemas.speech import SttPipelineResponse
from app.services.dialogue_pipeline import process_transcript
from app.services.session_store import new_turn_id
from app.services.stt_service import transcribe_audio

router = APIRouter(prefix="/stt", tags=["stt"])


@router.post("/pipeline", response_model=SttPipelineResponse)
async def transcribe_and_continue_dialogue(
    request: Request,
    audio: UploadFile = File(...),
    session_id: str = Form(default="demo-session"),
    turn_id: str | None = Form(default=None),
    duration_seconds: float | None = Form(default=None),
    response_requested_at: datetime | None = Form(default=None),
    response_started_at: datetime | None = Form(default=None),
    facial_emotion: str | None = Form(default=None),
):
    current_turn_id = turn_id or new_turn_id()
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(await audio.read())

        stt = await run_in_threadpool(transcribe_audio, temp_path)
        result = await process_transcript(
            session_id=session_id,
            turn_id=current_turn_id,
            transcript=stt.transcript or " ",
            duration_seconds=duration_seconds,
            response_requested_at=response_requested_at,
            response_started_at=response_started_at,
            stt_model=stt.model_name,
            stt_time_seconds=stt.elapsed_seconds,
            facial_emotion=facial_emotion,
        )
        audio_url = None
        if result.audio_file_id:
            audio_url = (
                f"{str(request.base_url).rstrip('/')}/api/v1/audio/"
                f"{result.audio_file_id}.wav"
            )
        return SttPipelineResponse(
            session_id=session_id,
            turn_id=current_turn_id,
            transcript=result.analysis.transcript,
            stt_model=stt.model_name,
            stt_time_seconds=stt.elapsed_seconds,
            stt_fallback_used=stt.fallback_used,
            stt_fallback_reason=stt.fallback_reason,
            analysis=result.analysis,
            llm=result.llm,
            audio_url=audio_url,
            emotion=result.emotion,
            avatar_state=result.avatar_state,
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
