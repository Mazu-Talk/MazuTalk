# MazuTalk

AI 롤플레잉 기반 자폐아동 언어 대화 치료 시뮬레이션

## Docker 실행

프론트엔드와 백엔드를 한 번에 실행합니다.

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

프론트엔드는 기본적으로 실제 FastAPI 백엔드에 연결됩니다. 백엔드 없이 UI만 시연하려면 `VITE_USE_MOCK=true`를 사용합니다. `AI_SERVICE_URL`이 비어 있으면 백엔드 내부 기본 응답 모듈을 사용합니다.

- `POST /api/v1/speech/analyze`: 발화 속도, 반복 표현, 응답 지연 분석
- `POST /api/v1/dialogue/stt-to-llm`: STT 결과 분석 후 LLM 응답 생성
- `POST /api/v1/stt/pipeline`: 음성 업로드 후 STT → 발화 분석 → LLM 전달
- `POST /api/v1/sessions`: 역할극 세션 생성
- `POST /api/v1/sessions/{session_id}/end`: 세션 종료
- `GET /api/v1/sessions/{session_id}/logs`: 세션 turn 로그 조회

`/api/v1/stt/pipeline`은 아동 발화 LoRA Faster-Whisper 모델을 우선 사용하고, 실패하거나 비정상 출력이 감지되면 기본 Faster-Whisper `medium`으로 fallback합니다. 이후 발화 분석, LLM, TTS까지 처리하며 MeloTTS 생성이 실패하면 프론트엔드가 브라우저 TTS로 대체합니다.

세션 turn 로그는 서버 실행 중에만 유지되는 SQLite in-memory DB에 저장됩니다.

자세한 Docker 실행 방법은 [docs/docker.md](docs/docker.md)를 참고하세요.
