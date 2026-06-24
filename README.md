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

## 통합 구성 (frontend · backend · ollama)

`docker compose up --build` 시 3개 컨테이너가 함께 뜹니다.

| 컨테이너 | 역할 |
|----------|------|
| `MazuTalk-frontend` | React/Vite UI + 표정(YOLOv8)·시선(MediaPipe)·VRM 아바타 |
| `MazuTalk-backend` | FastAPI: STT → 발화분석 → 감정융합 → LLM → TTS → 세션/리포트 |
| `MazuTalk-ollama` | GGUF(Qwen3 Q4) LLM 서빙 (`/api/chat`) |

전체 흐름·모듈 연결은 [docs/USER_FLOW.md](docs/USER_FLOW.md), [docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md) 참고.

## 모델 파일 (git 미포함, 별도 준비)

대용량 모델 가중치는 GitHub 100MB 제한 때문에 git 에 포함하지 않습니다(`.gitignore`).
**없어도 `docker compose up` 은 정상 기동**하며 아래처럼 graceful degradation 됩니다.

| 파일 | 위치 | 부재 시 동작 |
|------|------|--------------|
| `model-q4_k_m.gguf` (LLM, ~2.3GB) | `ai/models/` | Ollama 등록 생략 → 백엔드 **규칙기반 fallback** 응답 |
| `model.bin` 등 (튜닝 STT) | `ai/stt/models/faster-whisper-medium-child-lora-int8/` | faster-whisper **`medium` 자동 다운로드**로 폴백 |
| `best.onnx` (표정), `*.vrm` (아바타) | git 포함 | — (바로 동작) |

> LLM 을 켜려면: `model-f16.gguf` 를 `ai/models/` 에 두고 로컬에서 `llama-quantize ... Q4_K_M` 로 `model-q4_k_m.gguf` 생성(README 하단 참고) 후 `docker compose up`. Ollama 호스트 포트는 네이티브 Ollama 충돌을 피해 `11435` 입니다.

## E2E 테스트

```bash
# 백엔드 파이프라인 (pytest + FastAPI TestClient)
cd backend
python -m venv .venv && .venv/Scripts/python.exe -m pip install fastapi httpx pytest python-multipart
.venv/Scripts/python.exe -m pytest -q          # 22 passed

# 프런트 오케스트레이션 + 리포트 (vitest)
cd frontend && npm install && npm test          # 7 passed
```

테스트 범위·케이스·mock 은 [docs/E2E_TEST_PLAN.md](docs/E2E_TEST_PLAN.md) 참고.
