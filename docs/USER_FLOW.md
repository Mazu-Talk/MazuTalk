# MazuTalk 전체 사용자 플로우 (USER_FLOW)

ASD 아동 사회성 대화 연습 서비스의 단일 세션 전체 흐름과 4개 모듈의 연결 구조.

## 시스템 모듈 ↔ 코드 매핑

| 모듈 | 책임 | 구현 위치 |
|------|------|-----------|
| **M1 ASD Speech Recognition** | 음성 입력·STT·발화특성 추출 | `backend/app/services/stt_service.py`(faster-whisper, LoRA 튜닝 모델 + medium fallback), `speech_analysis.py` |
| **M2 Role-Play-Interaction** | 표정·시선 융합 + LLM 입력구성 + 응답생성 | 프런트 `features/emotion-detection`·`gaze-tracking`, 백엔드 `vision_fusion.py`·`llm_client.py`(Ollama/Qwen3 Q4)·`dialogue_pipeline.py`·`scenario_catalog.py` |
| **M3 Character Voice & Avatar** | TTS 음성합성 + 3D 아바타 표현 | 백엔드 `tts_service.py`(MeloTTS), 프런트 `VRMAvatar.tsx`·`useLipSyncAudio.ts` |
| **M4 Learning Report** | 상호작용 수집·분석·리포트 | 백엔드 `session_store.py`(turn_logs), 프런트 `lib/report.ts`·`ReportView.tsx` |

## 전체 플로우 (단계별 입력 / 처리 / 출력)

| # | 단계 | 입력 | 처리 | 출력 | 모듈 |
|---|------|------|------|------|------|
| 1 | 세션 시작 | 시나리오 선택 | `POST /api/v1/sessions` → sqlite 세션 생성 | `session_id` | M4 |
| 2 | 시나리오 로드 | `scenario_id` | `scenario_catalog` 컨텍스트(장소·난이도·목표) | 시나리오 컨텍스트 | M2 |
| 3 | 음성 발화 입력 | 마이크 오디오(webm) | MediaRecorder 녹음 | audio blob | M1 |
| 4 | 음성 인식 | audio blob | faster-whisper(child-LoRA, int8) → 실패 시 medium fallback | transcript | M1 |
| 5 | 발화 특성 추출 | transcript + duration + latency | `analyze_speech`: 발화길이·반복·응답지연·말속도 | `analysis`(flags, pace, repeated, latency) | M1 |
| 6 | 표정/시선 입력 | 웹캠 프레임 | YOLOv8(best.onnx) 표정분류 + MediaPipe 홍채/시선 | `facial_emotion`, `gazeLog` | M2 |
| 7 | 감정 융합 | speech flags + facial_emotion | `vision_fusion.fuse_emotion`(행동신호 우선, 중립시 표정) | `fused_emotion` | M2 |
| 8 | LLM 입력 구성 | transcript + 시나리오 + 히스토리 + 감정/특성 | `llm_client.build_user_content` → RP 입력 JSON | LLM payload | M2 |
| 9 | LLM 응답 생성 | LLM payload + RP 시스템프롬프트 | Ollama `/api/chat`(Qwen3 Q4, format=json) | RP 출력 JSON(child_message …) | M2 |
| 10 | 응답 텍스트 표시 | RP 출력 | `parse_llm_output` → `therapist_reply` | 응답 텍스트(말풍선) | M2/M3 |
| 11 | TTS 합성 | therapist_reply | MeloTTS(KR) → wav | `audio_url` | M3 |
| 12 | 음성 출력 | audio_url | `useLipSyncAudio`: Web Audio 재생 + 볼륨 추출 | 재생 + `lipSyncVolume` | M3 |
| 13 | 아바타 응답 | emotion + lipSyncVolume + avatar_state | VRM 표정/제스처/입모양 | 3D 아바타 표현 | M3 |
| 14 | 상호작용 저장 | transcript + analysis + llm | `append_turn` → turn_logs | 저장된 턴 | M4 |
| 15 | 리포트 생성 | turns + gazeLog | `buildReport`: 참여도·감정추이·정면집중도 | `Report` | M4 |
| 16 | 보호자 리포트 | Report | `ReportView` 시각화(게이지·타임라인) | 리포트 화면 | M4 |
| 17 | 피드백/다음 진행 | 종료 상태 | `endSession`(completed/interrupted) → 다음 시나리오 | 세션 상태 저장 | M4 |

## 모듈 간 데이터 계약 (핵심 연결점)

```
M1 transcript+analysis ─┐
                        ├─► M2 build_user_content(payload) ─► LLM ─► therapist_reply ─► M3 TTS+Avatar
M2 facial_emotion ──────┤        (vision_fusion: 음성 ⊕ 표정 = emotion)
M2 gazeLog ─────────────┘
M1~M3 turn_logs(append_turn) ─► M4 buildReport(turns, gazeLog) ─► Report ─► 다음 시나리오
```

## 전송 경로 (2가지, 동일 파이프라인)

- **오디오 경로**: `POST /api/v1/stt/pipeline` (multipart: audio + facial_emotion + latency) → 백엔드 STT 포함 전 구간.
- **텍스트 경로(브라우저 STT)**: WebSocket `/api/v1/sessions/{id}/ws` `end_utterance`(text + facial_emotion) → STT 우회, 동일 분석·융합·LLM·TTS.
- 둘 다 `dialogue_pipeline.process_transcript`로 수렴하여 동일한 모듈 계약을 사용한다.
