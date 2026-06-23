from fastapi import APIRouter

from app.schemas.speech import SpeechAnalysisRequest, SpeechAnalysisResponse
from app.services.speech_analysis import analyze_speech

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("/analyze", response_model=SpeechAnalysisResponse)
def analyze_speech_endpoint(payload: SpeechAnalysisRequest):
    return analyze_speech(payload)
