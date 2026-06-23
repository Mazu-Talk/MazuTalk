# 마주톡 Frontend

자폐 스펙트럼 아동을 위한 AI 역할극 사회성 훈련 웹앱의 프론트엔드.
React + Vite + Tailwind + Zustand 로 구현했으며, 아동 친화형(큰 버튼·단순 UI·낮은 자극) UI를 따른다.

## 실행

```bash
npm install
npm run dev        # 개발 서버 (http://localhost:5173)
npm run build      # 타입체크 + 프로덕션 빌드
npm run typecheck  # 타입체크만
```

## 실제 백엔드 연결 (기본값)

기본 설정은 FastAPI 백엔드의 `/api/v1` REST·WebSocket API를 사용한다.

- **STT**: `MediaRecorder`로 녹음한 오디오를 `/api/v1/stt/pipeline`에 업로드
- **LLM**: `AI_SERVICE_URL`이 없으면 백엔드 규칙 기반 응답, 있으면 외부 LLM 사용
- **TTS**: 백엔드 `audio_url` 재생, 생성 실패 시 브라우저 SpeechSynthesis로 대체
- **텍스트 대체 입력**: `/api/v1/sessions/{session_id}/ws` 이벤트 계약 사용

## 백엔드 없이 동작

백엔드(FastAPI)가 아직 없어도 전체 흐름을 시연할 수 있도록 **mock 모드**가 기본 활성화되어 있다.

- **STT**: 브라우저 Web Speech API (`useSpeechRecognition`). 미지원 브라우저는 텍스트 입력으로 자동 대체.
- **LLM/감정/난이도**: 규칙 기반 mock 엔진(`api/mockEngine.ts`) — `ai/prompts/RP_system_prompt.md` 원칙을 흉내.
- **TTS**: 브라우저 SpeechSynthesis (`useTextToSpeech`).
- **리포트**: 대화 로그로부터 클라이언트에서 계산(`lib/report.ts`).

백엔드 없이 프론트 UI만 시연할 때 환경변수로 전환한다.

```bash
# .env.local
VITE_USE_MOCK=true
```

`api/client.ts`(REST)와 `api/websocket.ts`(WebSocket)는 ARCHITECTURE.md §8 의 시그니처를 그대로 따르므로,
Docker Compose는 기본적으로 실제 백엔드 모드로 실행된다.

## 구조

```
src/
├── api/            # 통신 계층: REST(client), WebSocket, mock 엔진, 설정
├── stores/         # Zustand 상태: appStore(라우팅), sessionStore(세션 상태머신)
├── hooks/          # useSpeechRecognition(STT), useTextToSpeech(TTS)
├── pages/          # Home, ScenarioSelect, RolePlay, Report
├── components/     # common(Button/Card/Modal), layout(AppLayout)
├── features/
│   ├── scenario-learning/  # ScenarioCard
│   ├── voice-interaction/  # Avatar, MicButton
│   ├── chatbot/            # ChatBubble
│   └── feedback/           # ReportView (참여도 게이지/감정 추이/막대 그래프)
├── data/           # 시나리오 데이터셋
├── constants/      # 감정·난이도·기술 라벨
├── lib/            # report 계산, cn 헬퍼
└── types/          # 도메인/WS 타입
```

## 화면 흐름

`Home → 시나리오 선택 → 역할극(아바타 + 음성 대화) → 학습 리포트`

세션 상태(`sessionStore`)는 `idle → listening → thinking → speaking` 단계를 순환하며,
이 단계가 아바타 표정(ARCHITECTURE §5.8)과 마이크 활성 상태를 결정한다.
