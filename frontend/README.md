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

## 백엔드 없이 동작 (기본값)

백엔드(FastAPI)가 아직 없어도 전체 흐름을 시연할 수 있도록 **mock 모드**가 기본 활성화되어 있다.

- **STT**: 브라우저 Web Speech API (`useSpeechRecognition`). 미지원 브라우저는 텍스트 입력으로 자동 대체.
- **LLM/감정/난이도**: 규칙 기반 mock 엔진(`api/mockEngine.ts`) — `ai/prompts/RP_system_prompt.md` 원칙을 흉내.
- **TTS**: 브라우저 SpeechSynthesis (`useTextToSpeech`).
- **리포트**: 대화 로그로부터 클라이언트에서 계산(`lib/report.ts`).

실제 백엔드 연결 시 환경변수로 전환한다.

```bash
# .env.local
VITE_USE_MOCK=false
VITE_API_BASE=/api
VITE_WS_BASE=ws://localhost:8000/ws
```

`api/client.ts`(REST)와 `api/websocket.ts`(WebSocket)는 ARCHITECTURE.md §8 의 시그니처를 그대로 따르므로,
백엔드가 준비되면 코드 변경 없이 플래그만 끄면 된다.

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
