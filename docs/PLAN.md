# PLAN.md

# 박민지 담당 작업 계획서

담당 영역

- Role-play Interaction Module
- Frontend UI
- Avatar Interaction

---

# EPIC 1. Role-play AI Core

목표

사회성 훈련용 대화 엔진 구축

---

## TASK-RP-001 시나리오 카테고리 정의

우선순위: P0

설명

MVP에서 사용할 사회성 훈련 주제를 정의한다.

산출물

```text
docs/scenarios/scenario-categories.md
```

포함 내용

- 인사하기
- 감정 표현하기
- 도움 요청하기
- 갈등 해결하기

완료 조건

- 최소 4개 시나리오 정의
- 난이도 정의

예상 PR 크기

XS

---

## TASK-RP-002 시나리오 데이터 스키마 정의

우선순위: P0

설명

모든 시나리오가 동일 구조를 갖도록 JSON Schema 정의

산출물

```text
schemas/scenario.schema.json
```

완료 조건

- JSON Schema 작성
- 예제 데이터 작성

예상 PR 크기

XS

---

## TASK-RP-003 시나리오 데이터셋 작성

우선순위: P0

설명

초기 시나리오 JSON 생성

산출물

```text
data/scenarios/*.json
```

완료 조건

- 시나리오 20개 이상

예상 PR 크기

S

---

## TASK-RP-004 AI 캐릭터 정의

우선순위: P0

설명

Role-play에 사용할 캐릭터 정의

산출물

```text
data/characters/*.json
```

완료 조건

- 친구 캐릭터
- 선생님 캐릭터

예상 PR 크기

XS

---

## TASK-RP-005 시스템 프롬프트 설계

우선순위: P0

설명

Qwen3/KoGPT용 시스템 프롬프트 작성

산출물

```text
prompts/system_prompt.md
```

포함

- 치료 원칙
- 역할극 규칙
- 금지 응답

완료 조건

- Prompt v1 작성

예상 PR 크기

S

---

## TASK-RP-006 Safety Rule 정의

우선순위: P0

설명

금지 응답 규칙 설계

산출물

```text
prompts/safety_rules.yaml
```

완료 조건

- 차단 카테고리 정의
- 대체 응답 정의

예상 PR 크기

XS

---

## TASK-RP-007 LLM 응답 생성기 구현

우선순위: P1

설명

Prompt + Context 기반 응답 생성

산출물

```text
services/chat_service.py
```

완료 조건

- 단일 턴 대화 가능

예상 PR 크기

M

---

## TASK-RP-008 대화 이력 관리 구현

우선순위: P1

설명

History 기반 응답 생성

산출물

```text
services/conversation_manager.py
```

완료 조건

- Multi-turn 대화 가능

예상 PR 크기

M

---

## TASK-RP-009 감정 기반 난이도 조절

우선순위: P1

설명

감정 상태에 따라 응답 전략 변경

산출물

```text
services/difficulty_controller.py
```

완료 조건

- Easy
- Medium
- Hard

동작 확인

예상 PR 크기

M

---

## TASK-RP-010 Role-play API 구현

우선순위: P1

설명

Frontend에서 호출 가능한 API 제공

산출물

```text
api/chat.py
```

완료 조건

POST /chat 구현

예상 PR 크기

S

---

# EPIC 2. Frontend UI

목표

사용자가 AI와 상호작용할 수 있는 화면 제공

---

## TASK-FE-001 프로젝트 초기 세팅

우선순위: P0

산출물

```text
React
Vite
Tailwind
Zustand
```

완료 조건

- 개발 서버 실행

예상 PR 크기

XS

---

## TASK-FE-002 디자인 시스템 구축

우선순위: P0

산출물

```text
Button
Card
Modal
Layout
```

완료 조건

공통 컴포넌트 구축

예상 PR 크기

S

---

## TASK-FE-003 시나리오 선택 화면

우선순위: P0

산출물

```text
ScenarioSelectPage
```

완료 조건

시나리오 목록 표시

예상 PR 크기

S

---

## TASK-FE-004 대화 화면 UI

우선순위: P1

산출물

```text
RolePlayPage
```

완료 조건

- 대화 표시
- 입력 UI

예상 PR 크기

M

---

## TASK-FE-005 WebSocket 연동

우선순위: P1

산출물

```text
websocket.ts
```

완료 조건

실시간 이벤트 수신

예상 PR 크기

M

---

## TASK-FE-006 STT 결과 실시간 표시

우선순위: P1

완료 조건

사용자 발화 표시

예상 PR 크기

S

---

## TASK-FE-007 LLM 응답 실시간 표시

우선순위: P1

완료 조건

AI 응답 표시

예상 PR 크기

S

---

## TASK-FE-008 세션 상태 Store 구축

우선순위: P1

산출물

```text
sessionStore.ts
```

저장

- session_id
- history
- emotion
- scenario

예상 PR 크기

S

---

# EPIC 3. Avatar Interaction

목표

AI 캐릭터와의 상호작용 구현

---

## TASK-AV-001 Avatar 라이브러리 조사

우선순위: P0

산출물

```text
AvatarTechDecision.md
```

비교

- VRM
- ReadyPlayerMe
- Three.js

예상 PR 크기

XS

---

## TASK-AV-002 Avatar 렌더링 구현

우선순위: P1

산출물

```text
AvatarCanvas.tsx
```

완료 조건

캐릭터 표시

예상 PR 크기

M

---

## TASK-AV-003 Avatar 상태 머신 구현

우선순위: P1

상태

- idle
- listening
- thinking
- speaking

예상 PR 크기

M

---

## TASK-AV-004 음성 재생 상태 연동

우선순위: P1

설명

TTS 상태에 따라 Avatar 변화

예상 PR 크기

M

---

## TASK-AV-005 감정 표현 구현

우선순위: P2

상태

- happy
- confused
- anxious

예상 PR 크기

M

---

## TASK-AV-006 MediaPipe 시선 추적 실험

우선순위: P3

설명

연구성 기능

완료 조건

PoC 수준 구현

예상 PR 크기

L

---

# MVP 마일스톤

## M1 시나리오 엔진

- TASK-RP-001
- TASK-RP-002
- TASK-RP-003
- TASK-RP-004

---

## M2 대화 생성

- TASK-RP-005
- TASK-RP-006
- TASK-RP-007
- TASK-RP-008
- TASK-RP-009
- TASK-RP-010

---

## M3 사용자 화면

- TASK-FE-001
- TASK-FE-002
- TASK-FE-003
- TASK-FE-004
- TASK-FE-005
- TASK-FE-006
- TASK-FE-007
- TASK-FE-008

---

## M4 Avatar

- TASK-AV-001
- TASK-AV-002
- TASK-AV-003
- TASK-AV-004

---

## M5 고도화

- TASK-AV-005
- TASK-AV-006

```

```
