import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.schemas.speech import SpeechAnalysisRequest, SttPipelineResponse
from app.services.llm_client import LlmClient
from app.services.session_store import append_turn, new_turn_id
from app.services.speech_analysis import analyze_speech
from app.services.stt_service import transcribe_audio

router = APIRouter(prefix="/stt", tags=["stt"])


@router.post("/pipeline", response_model=SttPipelineResponse)
async def transcribe_and_continue_dialogue(
    audio: UploadFile = File(...),
    session_id: str = Form(default="demo-session"),
    turn_id: str | None = Form(default=None),
    duration_seconds: float | None = Form(default=None),
    response_requested_at: datetime | None = Form(default=None),
    response_started_at: datetime | None = Form(default=None),
):
    current_turn_id = turn_id or new_turn_id()
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(await audio.read())

        stt = transcribe_audio(temp_path)
        stt_payload = SpeechAnalysisRequest(
            transcript=stt.transcript or " ",
            duration_seconds=duration_seconds,
            response_requested_at=response_requested_at,
            response_started_at=response_started_at,
        )
        analysis = analyze_speech(stt_payload)
        llm = await LlmClient().respond(
            session_id=session_id,
            transcript=analysis.transcript,
            analysis=analysis,
            conversation_history=[],
            child_profile={},
        )
        append_turn(
            session_id=session_id,
            turn_id=current_turn_id,
            transcript=analysis.transcript,
            analysis=analysis,
            llm=llm,
            stt_model=stt.model_name,
            stt_time_seconds=stt.elapsed_seconds,
        )
        return SttPipelineResponse(
            session_id=session_id,
            turn_id=current_turn_id,
            transcript=analysis.transcript,
            stt_model=stt.model_name,
            stt_time_seconds=stt.elapsed_seconds,
            analysis=analysis,
            llm=llm,
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
