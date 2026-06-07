# backend/app/api/v1/tts.py
# [역할] FastAPI 엔드포인트 담당
# React(프론트)에서 텍스트를 보내면 audio_url을 반환해줌
# 실제 변환 로직은 tts_service.py의 generate_tts()가 처리

import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.tts_service import generate_tts

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    speed: float = 0.8

# ─────────────────────────────────────────────
# POST /tts
# React → 텍스트 전송 → audio_url 반환
# ─────────────────────────────────────────────
@router.post("/tts")
def tts(request: TTSRequest, req: Request):
    file_id = generate_tts(request.text, request.speed)

    # 요청이 들어온 호스트의 base_url로 동적으로 URL 생성
    # → 로컬, Docker, 배포 환경 모두에서 올바른 URL 반환
    base_url = str(req.base_url).rstrip("/")
    return {
        "audio_url": f"{base_url}/audio/{file_id}.wav",
        "text": request.text
    }

# ─────────────────────────────────────────────
# GET /audio/{filename}
# audio_url로 실제 음성 파일에 접근하는 엔드포인트
# ─────────────────────────────────────────────
@router.get("/audio/{filename}")
def get_audio(filename: str):
    # 경로 이탈(Directory Traversal) 공격 방지
    safe_filename = os.path.basename(filename)
    file_path = os.path.join("output_audio", safe_filename)

    # 파일이 없을 경우 404 반환
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(path=file_path, media_type="audio/wav")