# 기능 명세서

# FD-01 사회성 훈련 시나리오

## 목적

상황별 사회성 학습 제공

## 입력

사용자 선택

## 출력

시나리오 로딩

## 화면

Scenario Selection Page

---

# FD-02 실시간 대화 세션

## 목적

AI와 역할극 수행

## 처리 흐름

사용자 음성
→ STT
→ 감정분석
→ LLM
→ TTS
→ 아바타 출력

## 입력

음성

## 출력

AI 음성 응답

---

# FD-03 감정 분석

## 목적

사용자 감정 추정

## 입력

STT 결과

## 출력

{
emotion: "anxious"
}

## 감정 목록

- anxious
- happy
- confused
- passive

---

# FD-04 대화 상태 관리

## 저장 정보

session_id

turn_id

scenario_id

emotion

conversation_history

difficulty_level

---

# FD-05 난이도 조절

## 목적

사용자 수준에 맞는 대화 제공

## 입력

- 응답 속도
- 발화 길이
- 감정 상태

## 출력

difficulty

- easy
- medium
- hard

---

# FD-06 아바타 인터랙션

## 상태

Listening

Speaking

Idle

Happy

Sad

Confused

## 이벤트

TTS 시작

TTS 종료

감정 변경

---

# FD-07 학습 리포트

## 목적

세션 결과 제공

## 데이터

- 총 대화 횟수
- 평균 응답시간
- 감정 변화
- 참여도

## 시각화

- 막대 그래프
- 감정 추이 그래프
- 참여도 게이지

---

# FD-08 보호자 대시보드

## 제공 정보

- 최근 학습 결과
- 감정 변화
- 시나리오별 성취도
- 반복 학습 이력

---

# FD-09 API 명세

## POST /stt

입력

audio_file

출력

{
"text":"안녕"
}

---

## POST /emotion

입력

{
"text":"안녕"
}

출력

{
"emotion":"happy"
}

---

## POST /chat

입력

{
"scenario_id":"greeting",
"history":[...],
"emotion":"happy"
}

출력

{
"response":"안녕 반가워"
}

---

## POST /tts

입력

{
"text":"안녕 반가워"
}

출력

audio_url

---

# FD-10 Learning Report 데이터 모델

Session

- session_id
- child_id
- scenario_id
- start_time
- end_time

Conversation

- turn_id
- speaker
- text
- emotion
- response_time

Report

- participation_score
- emotion_score
- completion_score
