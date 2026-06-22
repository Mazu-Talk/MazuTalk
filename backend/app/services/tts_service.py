# backend/app/services/tts_service.py
# [역할] MeloTTS 핵심 변환 로직 담당
# tts.py(엔드포인트)에서 이 파일의 generate_tts()를 호출해서 사용
# 모델 로드처럼 무거운 작업은 여기서 한 번만 처리

import os
import uuid
import wave


# 음성 파일을 임시 저장할 폴더 생성 (없으면 자동으로 만들어줌)
os.makedirs("output_audio", exist_ok=True)

model = None
speaker_id = None


def get_model():
    global model, speaker_id
    import threading

    if not hasattr(get_model, "_lock"):
        get_model._lock = threading.Lock()

    with get_model._lock:
        if model is None:
            from melo.api import TTS

            model = TTS(language="KR", device="auto")
            speaker_id = model.hps.data.spk2id["KR"]
    return model, speaker_id


def generate_tts(text: str, speed: float = 1.1) -> str:
    # 파일 이름 중복 방지를 위해 uuid로 고유한 ID 생성
    # (예: "3f2a1b4c-...")
    file_id = str(uuid.uuid4())
    filename = f"output_audio/{file_id}.wav"

    try:
        tts_model, tts_speaker_id = get_model()
        tts_model.tts_to_file(
            text=text,
            speaker_id=tts_speaker_id,
            output_path=filename,
            speed=speed,
        )
    except ImportError:
        write_silent_wav(filename)

    # 파일 경로 대신 file_id만 반환
    # (실제 URL은 tts.py에서 조합)
    return file_id


def write_silent_wav(filename: str, sample_rate: int = 16000, duration_seconds: float = 0.3) -> None:
    frame_count = int(sample_rate * duration_seconds)
    with wave.open(filename, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
