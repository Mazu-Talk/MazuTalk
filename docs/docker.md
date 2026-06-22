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
CORS_ORIGINS=http://localhost:5173
AI_SERVICE_URL=

STT_MODEL=medium
STT_FALLBACK_MODEL=small
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
SESSION_DB_PATH=:memory:
```

STT 기본 모델은 정확도 우선으로 `medium`을 사용합니다. 모델 로드나 추론에 실패하면 `small`로 fallback하도록 구성합니다.

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

## 6. 모델 warm-up

Faster-Whisper `medium`은 첫 요청에서 모델 다운로드/로드가 발생할 수 있습니다. 회의나 데모 전에 `/api/v1/stt/pipeline`을 한 번 호출해 warm-up 해두면 이후 요청이 더 안정적입니다.

## 7. 로그 확인

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## 8. 문제 해결

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
