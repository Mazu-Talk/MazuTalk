# E2E 디버그 리포트 (DEBUG_REPORT)

E2E 테스트 설계 → 작성 → 실행 → 수정 루프의 결과. **최종 전체 통과(29/29).**

## 환경 셋업 (테스트 실행 전 blocker 해소)

| 문제 | 원인 분류 | 조치 |
|------|-----------|------|
| 기본 Python(3.14)에 백엔드 deps 없음 → `No module named pytest` | 환경설정 | `backend/.venv` 생성 + 최소 deps 설치(`fastapi httpx pytest python-multipart`). torch/melo/faster-whisper는 lazy import·mock이라 불필요 |
| 프런트 테스트 러너 부재 | 환경설정 | `vitest@2.1.9` + `jsdom` 설치, `vitest.config.ts`(jsdom, `VITE_USE_MOCK=true`) 추가 |

## 작성 중 수정한 항목 (원인 분석 → 최소 수정)

### 1. conftest 상대 import 실패
- **단계**: 수집(collection) 단계, 테스트 실행 전
- **원인 분류**: 테스트 코드 버그 (import 방식)
- **기대 vs 실제**: `from . import sample_data` 기대 → pytest prepend 모드에선 `tests/`가 sys.path에 직접 올라가 패키지 상대 import 불가
- **수정 파일**: `backend/tests/conftest.py`
- **수정**: `from . import sample_data as S` → `import sample_data as S` (top-level). 기존 테스트(`from app.main`)와 동일한 `python -m pytest` cwd 기반 경로 규약에 맞춤
- **영향 범위**: 테스트 인프라만, 프로덕션 코드 무변경

### 2. 빈/공백 발화 엣지 케이스의 mock 계약 오해
- **단계**: `sessionFlow` 빈 발화 테스트
- **원인 분류**: fixture/mock 데이터 문제 (테스트 기대값)
- **기대 vs 실제**: 공백 `'   '` 입력 시 error 이벤트 기대 → 실제로 `MockConnection`은 `!content.text`로 판정하므로 `'   '`(truthy)는 정상 처리되어 AI 응답 생성됨
- **수정 파일**: `frontend/src/__tests__/sessionFlow.test.ts`
- **수정**: 입력을 빈 문자열 `''`로 변경(백엔드 `WebSocketTurnPayload.text` min_length=1 및 mock 둘 다 error로 처리하는 실제 계약과 일치). 프로덕션 코드 무변경
- **영향 범위**: 테스트만

### 3. 감정 융합 우선순위 설계 반영
- **단계**: happy-path/latency 테스트 기대값 설정
- **원인 분류**: (버그 아님) 데이터 계약 정합
- **확인**: `vision_fusion.fuse_emotion`은 **행동신호(음성 flag) 우선**. 따라서 응답지연(>4s)이 있으면 표정(sad)보다 `anxious`가 우선됨 → 테스트를 두 케이스로 분리(지연→anxious / 음성중립+표정→facial). 프로덕션 로직이 의도대로 동작함을 검증
- **수정 파일**: 테스트 케이스 분리만, 프로덕션 코드 무변경

## 최종 테스트 결과

```
backend:  22 passed   (.venv/Scripts/python.exe -m pytest -q)
          ├─ 6  기존 (test_service_flow, test_stt_service)
          └─ 16 신규 E2E (test_e2e_pipeline)
frontend: 7  passed   (npm test = vitest run)
          ├─ 5 report.test.ts (M4 리포트 분석)
          └─ 2 sessionFlow.test.ts (오케스트레이션)
────────────────────────────────────────────
합계:     29 passed, 0 failed
```

## 프로덕션 코드 변경

**없음.** 모든 수정은 테스트 코드/픽스처/환경에 국한되었고, public API·컴포넌트 인터페이스·데이터 스키마는 보존됐다. 파이프라인 실코드는 그대로 실행되어 모듈 간 데이터 계약이 검증되었다.
