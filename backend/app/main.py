import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.schemas.speech import (
    SpeechAnalysisRequest,
    SpeechAnalysisResponse,
    SttPipelineResponse,
    SttToLlmRequest,
    SttToLlmResponse,
)
from app.services.llm_client import LlmClient
from app.services.speech_analysis import analyze_speech
from app.services.stt_service import transcribe_audio

app = FastAPI(title="MazuTalk API")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/speech/analyze", response_model=SpeechAnalysisResponse)
def analyze_speech_endpoint(payload: SpeechAnalysisRequest):
    return analyze_speech(payload)


@app.post("/api/dialogue/stt-to-llm", response_model=SttToLlmResponse)
async def stt_to_llm(payload: SttToLlmRequest):
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
    return SttToLlmResponse(
        session_id=payload.session_id,
        analysis=analysis,
        llm=llm,
    )


@app.post("/api/stt/pipeline", response_model=SttPipelineResponse)
async def transcribe_and_continue_dialogue(
    audio: UploadFile = File(...),
    session_id: str = Form(default="demo-session"),
    duration_seconds: float | None = Form(default=None),
    response_requested_at: datetime | None = Form(default=None),
    response_started_at: datetime | None = Form(default=None),
):
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
        return SttPipelineResponse(
            session_id=session_id,
            transcript=analysis.transcript,
            stt_model=stt.model_name,
            stt_time_seconds=stt.elapsed_seconds,
            analysis=analysis,
            llm=llm,
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
