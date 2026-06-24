# MazuTalk E2E 테스트 계획 (E2E_TEST_PLAN)

## 테스트 범위

단순 화면 렌더링이 아니라 **4개 모듈이 실제 사용자 흐름 안에서 데이터로 연결되는지**를 검증한다.

| 레이어 | 도구 | 위치 | 검증 대상 |
|--------|------|------|-----------|
| 백엔드 파이프라인 | **pytest + FastAPI TestClient** | `backend/tests/test_e2e_pipeline.py` | M1 STT/특성 → M2 융합/LLM payload·파싱 → M3 TTS/아바타상태 → M4 로그저장 (REST + WebSocket 양 경로) |
| 프런트 오케스트레이션 | **Vitest + jsdom** | `frontend/src/__tests__/` | 세션→발화→응답이벤트→턴갱신→비전수집→리포트→다음 시나리오, M4 리포트 분석 |

> 실제 파이프라인 코드(`speech_analysis`·`vision_fusion`·`dialogue_pipeline`·`llm_client`의 payload 구성/파싱·`session_store`·`report.ts`·`sessionStore`)는 **그대로 실행**한다. 무거운 외부 의존성만 결정론적 double 로 대체한다.

## 실행 명령어

```bash
# 백엔드 (venv: backend/.venv, 최소 deps: fastapi httpx pytest python-multipart)
cd backend && .venv/Scripts/python.exe -m pytest -q

# 프런트
cd frontend && npm test          # = vitest run
```

## 테스트 케이스 목록

### Happy Path (정상 흐름)
| 테스트 | 검증 |
|--------|------|
| `test_happy_path_full_pipeline` | 음성+표정 입력 → transcript·발화특성·시나리오grounding·감정융합·LLM payload·응답텍스트·audio_url·아바타상태·로그저장 **전 구간 연결** |
| `test_websocket_text_path_carries_facial_emotion` | 브라우저STT(텍스트) WS 경로도 표정 전달 + 공용 이벤트(stt_result/avatar_state/ai_response) |
| `test_speech_features_repetition_detected_flows_to_llm` | M1 반복 특성 → LLM `observed_features` 반영 |
| `test_response_latency_feature_drives_emotion` | M1 응답지연(>4s) → 행동기반 감정(anxious) 융합 |
| `test_facial_emotion_overrides_when_speech_neutral` | 음성 중립 시 표정(sad→frustrated)이 감정 결정 |
| `test_history_accumulates_across_turns` | 후속 턴 누적 히스토리가 LLM 입력에 포함 + 로그 누적 |
| `sessionFlow: 세션→발화→응답→비전→리포트→다음` | 클라이언트 전체 오케스트레이션 + gaze_summary·감정타임라인 리포트 + 다음 시나리오 |
| `report: 핵심 지표 / gaze_summary / completed` | M4 분석(참여도·감정추이·우세감정·정면집중도) |

### Failure / Edge Case
| 테스트 | 케이스 |
|--------|--------|
| `test_empty_transcript_is_handled_gracefully` | 빈 음성 인식 결과 |
| `test_short_meaningless_utterance_still_responds` | 너무 짧은/의미 적은 발화 |
| `test_llm_failure_falls_back_to_rule_model` | LLM(Ollama) 호출 실패 → 규칙기반 fallback |
| `test_llm_empty_message_falls_back` | LLM 빈 응답 |
| `test_llm_invalid_json_falls_back` | LLM 비-JSON 출력 |
| `test_tts_failure_returns_text_only` | TTS 생성 실패 → 텍스트만 |
| `test_missing_facial_emotion_uses_speech_only` | 표정 입력 누락 |
| `test_unknown_scenario_degrades_to_unknown_context` | 시나리오 컨텍스트 누락 |
| `test_session_interrupt_and_reentry` | 세션 중단 후 재진입(로그 분리) |
| `test_unknown_session_logs_are_empty` | 존재하지 않는 세션 조회 안전성 |
| `report: 시선 데이터 없음 / 아동발화 없음 / interrupted` | 리포트 엣지 |
| `sessionFlow: 빈 발화 → error 이벤트` | 무발화/인식실패 계약 |

## 사용한 Fixture / Mock 목록

### Fixture (`backend/tests/sample_data.py`, `frontend/src/__tests__/fixtures.ts`)
- 샘플 음성 입력(`SAMPLE_AUDIO_BYTES`), 인식 텍스트(normal/repeat/short/empty)
- 샘플 감정/시선/랜드마크(`FACIAL_EMOTION_*`, `EMOTION_SAMPLE`, `GAZE_SAMPLES`/`SAMPLE_GAZE`)
- 샘플 시나리오(`playground_greeting` 등 catalog), 대화 히스토리(empty/accumulated)
- 샘플 LLM 응답(`RP_RESPONSE` 정상 / 빈메시지 / 비-JSON)
- 샘플 TTS 결과(`TTS_AUDIO_ID`), 샘플 리포트 입력(`SAMPLE_TURNS`)

### Mock / Test Double (어디가 mock인지 명시)
| 대상 | 실제 | 테스트 double | 위치 |
|------|------|--------------|------|
| STT | faster-whisper 추론 | `transcribe_audio` → 고정 `SttResult` | `conftest.set_stt` |
| TTS | MeloTTS wav 합성 | `try_generate_tts` → 고정 file id / None | `conftest.set_tts` |
| LLM | Ollama `/api/chat` HTTP | `LlmClient._chat` → 기록+고정 RP JSON | `conftest.llm_double` |
| STT/LLM/TTS(프런트) | 백엔드 WS/REST | `MockConnection`+`mockEngine`(USE_MOCK) | `api/websocket.ts` |

> **실코드로 유지(=mock 아님)**: 발화특성 분석, 감정 융합, LLM 입력 payload 구성·출력 파싱, 세션/턴 저장, 리포트 산식, 상태관리·이벤트 처리. 모듈 간 데이터 계약은 프로덕션과 동일하게 검증된다.

## 성공 기준 (전부 충족)

- [x] 세션 시작 가능 / 음성·fixture 정상 처리
- [x] 발화 텍스트 + 발화 특성 데이터 생성
- [x] 감정/시선/상태 특징(facial_emotion·gazeLog) 생성·전달
- [x] LLM 입력 payload 올바른 구성(시나리오·감정·입력·히스토리·특성)
- [x] LLM 응답 텍스트 생성 + UI/상태 반영
- [x] TTS 결과(audio_url) + 아바타 응답 데이터 생성
- [x] 상호작용 로그 저장 + Learning Report 생성 + 보호자 리포트 확인
- [x] 피드백/다음 시나리오 진행 상태 저장
- [x] 모든 주요 단계 에러 없이 종료 (+ 실패 경로는 graceful fallback)
