# backend/app/api/v1/tts.py
# [역할] FastAPI 엔드포인트 담당
# React(프론트)에서 텍스트를 보내면 audio_url을 반환해줌
# 실제 변환 로직은 tts_service.py의 generate_tts()가 처리

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 같은 팀 서비스 파일에서 핵심 함수 가져오기
from app.services.tts_service import generate_tts

# app 대신 APIRouter 사용
# → backend/app/main.py에 부품처럼 꽂을 수 있는 구조
router = APIRouter()

# React에서 보내는 요청 형식 정의
# { "text": "안녕!", "speed": 0.8 } 이런 JSON을 받음
class TTSRequest(BaseModel):
    text: str           # 변환할 텍스트
    speed: float = 0.8  # 말하는 속도 (기본값 0.8)

# ─────────────────────────────────────────────
# POST /tts
# React → 텍스트 전송 → audio_url 반환
# ─────────────────────────────────────────────
@router.post("/tts")
def tts(request: TTSRequest):
    # tts_service.py에서 음성 파일 생성 후 file_id 받아옴
    file_id = generate_tts(request.text, request.speed)

    # file_id로 접근 가능한 URL 조합해서 반환
    # React는 이 URL로 음성을 재생함
    return {
        "audio_url": f"http://localhost:8000/audio/{file_id}.wav",
        "text": request.text
    }

# ─────────────────────────────────────────────
# GET /audio/{filename}
# audio_url로 실제 음성 파일에 접근하는 엔드포인트
# (React의 <audio src="URL"> 이 여기로 요청을 보냄)
# ─────────────────────────────────────────────
@router.get("/audio/{filename}")
def get_audio(filename: str):
    return FileResponse(
        path=f"output_audio/{filename}",
        media_type="audio/wav"
    )