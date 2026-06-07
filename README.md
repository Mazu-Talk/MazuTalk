# MazuTalk

AI 롤플레잉 기반 자폐아동 언어 대화 치료 시뮬레이션

## Docker 실행

프론트엔드와 백엔드를 한 번에 실행합니다.

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

백엔드는 STT 분석 API와 STT 결과를 LLM 모듈로 전달하는 API를 제공합니다. `AI_SERVICE_URL`이 비어 있으면 백엔드 내부 기본 응답 모듈을 사용하고, 나중에 별도 AI 서비스가 준비되면 해당 URL을 환경변수로 연결할 수 있습니다.

- `POST /api/speech/analyze`: 발화 속도, 반복 표현, 응답 지연 분석
- `POST /api/dialogue/stt-to-llm`: STT 결과 분석 후 LLM 응답 생성
