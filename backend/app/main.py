import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.dialogue import router as dialogue_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.speech import router as speech_router
from app.api.v1.stt import router as stt_router
from app.api.v1.tts import router as tts_router

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


app.include_router(speech_router, prefix="/api/v1")
app.include_router(dialogue_router, prefix="/api/v1")
app.include_router(stt_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(tts_router, prefix="/api/v1")

# Backward-compatible routes for the current frontend/API experiments.
app.include_router(speech_router, prefix="/api", tags=["compat"])
app.include_router(dialogue_router, prefix="/api", tags=["compat"])
app.include_router(stt_router, prefix="/api", tags=["compat"])
app.include_router(sessions_router, prefix="/api", tags=["compat"])
app.include_router(tts_router, tags=["compat"])
