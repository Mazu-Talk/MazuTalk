# Docker Usage

MazuTalk frontend/backend를 로컬 설치 없이 Docker Compose로 실행하는 방법입니다.

## 1. 실행

프로젝트 루트에서 실행합니다.

```bash
docker compose up --build
```

접속 주소:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Backend Docs: http://localhost:8000/docs

## 2. 종료

```bash
docker compose down
```

## 3. 주요 환경변수

`.env` 파일을 만들면 기본값을 덮어쓸 수 있습니다.

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK=false
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
AI_SERVICE_URL=

STT_MODEL=/app/models/stt
STT_MODEL_HOST_PATH=./ai/stt/models/faster-whisper-medium-child-lora-int8
STT_FALLBACK_MODEL=medium
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_BEAM_SIZE=3
SESSION_DB_PATH=:memory:
```

STT 기본 모델은 아동 발화로 학습한 LoRA를 병합한 Faster-Whisper int8 모델입니다. 모델 로드/추론 실패, 빈 결과, 비정상적으로 긴 결과, 문자 반복 hallucination이 감지되면 기본 Faster-Whisper `medium`으로 fallback합니다.

변환 모델은 Git에 포함하지 않습니다. 실행 전에 아래 폴더가 있어야 합니다.

```text
ai/stt/models/faster-whisper-medium-child-lora-int8/
├── model.bin
├── config.json
├── tokenizer.json
└── vocabulary.json
```

다른 위치에 저장했다면 `.env`의 `STT_MODEL_HOST_PATH`를 해당 폴더로 변경합니다.

## 4. Backend API

신규 API는 `/api/v1` prefix를 사용합니다. 기존 실험용 경로 호환을 위해 `/api` prefix도 일부 유지합니다.

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/health` | 서버 상태 확인 |
| POST | `/api/v1/speech/analyze` | STT 텍스트 기반 발화 속도, 반복 표현, 응답 지연 분석 |
| POST | `/api/v1/dialogue/stt-to-llm` | STT 결과와 발화 분석 결과를 LLM 모듈로 전달 |
| POST | `/api/v1/stt/pipeline` | 업로드 음성 파일을 STT 처리한 뒤 분석 및 LLM 전달 |
| GET | `/api/v1/sessions/{session_id}/logs` | 세션별 turn 로그 조회 |
| WS | `/api/v1/sessions/{session_id}/ws` | transcript 기반 실시간 세션 turn 처리 |
| POST | `/api/v1/tts` | 텍스트를 음성 URL로 변환 |
| GET | `/api/v1/audio/{filename}` | 생성된 TTS 음성 파일 조회 |

## 5. 세션 로그

세션 로그는 SQLite in-memory DB에 저장됩니다.

```text
SESSION_DB_PATH=:memory:
```

따라서 서버 프로세스가 살아있는 동안만 세션/turn 로그가 유지되고, 컨테이너를 재시작하거나 서버를 종료하면 기록은 사라집니다. 결과보고서 생성처럼 한 세션 안에서 임시로 누적해야 하는 데이터에 사용합니다.

## 6. 전체 파이프라인 데모

1. `docker compose up --build`를 실행합니다.
2. http://localhost:5173 에 접속합니다.
3. 역할극 세션에 진입하고 마이크 권한을 허용합니다.
4. 짧은 문장을 말한 뒤 녹음을 종료합니다.
5. 화면에서 인식 문장과 LLM 답변을 확인하고 TTS 재생을 듣습니다.
6. http://localhost:8000/docs 또는 세션 로그 API에서 분석 결과를 확인합니다.

`AI_SERVICE_URL`이 비어 있으면 백엔드 규칙 기반 LLM fallback을 사용합니다. MeloTTS를 사용할 수 없으면 프론트엔드가 브라우저 음성 합성으로 답변을 재생합니다.

## 7. 모델 warm-up

학습 모델과 fallback `medium`은 첫 요청에서 로드 시간이 발생할 수 있습니다. 회의나 데모 전에 `/api/v1/stt/pipeline`을 한 번 호출해 warm-up 해두면 이후 요청이 더 안정적입니다. CPU 실행은 한 발화에 수십 초가 걸릴 수 있으므로 실제 운영/시연 환경은 NVIDIA GPU와 `STT_DEVICE=cuda`, `STT_COMPUTE_TYPE=float16`을 권장합니다.

## 8. 로그 확인

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## 9. 문제 해결

컨테이너 상태 확인:

```bash
docker compose ps
```

이미지 재빌드:

```bash
docker compose build --no-cache
```

백엔드 health check:

```bash
curl http://localhost:8000/health
```
