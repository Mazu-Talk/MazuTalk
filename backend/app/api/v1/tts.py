# backend/app/api/v1/tts.py
# [역할] TTS 관련 HTTP 엔드포인트 정의
# 프론트에서 텍스트를 보내면 audio_url 반환

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse # .wav 파일 직접 반환
from pydantic import BaseModel # 요청 Body 유효성 검사
from app.services.tts_service import TtsUnavailableError, generate_tts, get_audio_path

# 엔드포인트 묶음 (main.py에서 prefix /api/v1 로 등록)
router = APIRouter()

# POST /tts 요청 Body 스키마
class TTSRequest(BaseModel):
    text: str
    speed: float = 1.1


# POST /tts
# Body: { text, speed } → generate_tts()로 .wav 생성 → audio_url 반환
@router.post("/tts")
def tts(request: TTSRequest, req: Request):
    try:
        file_id = generate_tts(request.text, request.speed)
    except TtsUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # 요청이 들어온 호스트의 base_url로 동적으로 URL 생성
    base_url = str(req.base_url).rstrip("/")
    audio_prefix = "/api/v1/audio" if req.url.path.startswith("/api/v1/") else "/audio"
    return {
        "audio_url": f"{base_url}{audio_prefix}/{file_id}.wav",
        "text": request.text
    }


# GET /audio/{filename}
# audio_url 요청 수신 → output_audio/ 에서 파일 탐색 → .wav 스트리밍
@router.get("/audio/{filename}")
def get_audio(filename: str):
    file_path = get_audio_path(filename)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(path=str(file_path), media_type="audio/wav")
