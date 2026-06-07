# backend/app/services/tts_service.py
# [역할] MeloTTS 핵심 로직 담당
# tts.py(엔드포인트)에서 이 파일의 generate_tts()를 호출해서 사용
# 모델 로드처럼 무거운 작업은 여기서 한 번만 처리

from melo.api import TTS
import uuid, os

# 음성 파일을 임시 저장할 폴더 생성 (없으면 자동으로 만들어줌)
os.makedirs("output_audio", exist_ok=True)

# 서버 시작할 때 딱 한 번만 모델 로드
# (요청마다 로드하면 매우 느려지기 때문)
model = TTS(language='KR', device='auto')
speaker_id = model.hps.data.spk2id['KR']  # 한국어 화자 ID

def generate_tts(text: str, speed: float = 0.8) -> str:
    """
    텍스트를 음성 파일로 변환하는 함수
    
    Args:
        text  : 변환할 텍스트 (예: "안녕! 나 미래야.")
        speed : 말하는 속도 (기본값 0.8 / 1.0이 보통 속도 / 낮을수록 느림)
    
    Returns:
        file_id : 생성된 음성 파일의 고유 ID (예: "abc123.wav"에서 "abc123" 부분)
                  → tts_v3.py에서 이 값으로 audio_url을 만듦
    """

    # 파일 이름 중복 방지를 위해 uuid로 고유한 ID 생성
    # (예: "3f2a1b4c-...")
    file_id = str(uuid.uuid4())
    filename = f"output_audio/{file_id}.wav"

    # MeloTTS로 텍스트 → 음성 파일 변환 후 저장
    model.tts_to_file(
        text=text,
        speaker_id=speaker_id,
        output_path=filename,
        speed=speed
    )

    # 파일 경로 대신 file_id만 반환
    # (실제 URL은 tts.py에서 조합)
    return file_id