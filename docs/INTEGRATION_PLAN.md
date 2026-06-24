# MazuTalk 통합 오케스트레이션 계획 (Integration Plan)

> 목표: STT · TTS · LLM · 표정(YOLOv8) · 시선(MediaPipe) 5개 모델을 하나의
> 서비스로 유기적으로 연결하고, 소스 파일을 역할별로 일관되게 배치한다.
> 배포 단위: `docker compose up` 한 번으로 frontend + backend + ollama 기동.

## 현재 상태 진단 (2026-06-24)

- **TS 앱(실동작)**: `App.tsx → pages → MicButton → /stt/pipeline →
  STT→speech_analysis→LLM→TTS`. emotion은 음성 flag로 추정(`infer_emotion`).
- **JS 비전(죽은 코드)**: `EmotionDetector.jsx`(YOLOv8), `MediaPipeGaze.jsx`(시선),
  `TTSPlayer.jsx`, `AvatarViewer.jsx`(VRM)가 별도 `store/sessionStore.js`에
  연결되어 있고 **App에 미마운트 · 의존성 미설치 · 일부 import 경로 파손**.
- **LLM 미서빙**: `LlmClient`는 `AI_SERVICE_URL` 호출이지만 기본값 비어 있고
  서버가 없어 항상 규칙기반 fallback. `ai/models/model-f16.gguf`(7.5GB) 미사용.

## 목표 아키텍처

```
frontend (Vite)
  ├ voice-interaction : VRM Avatar · MicButton · TTS
  ├ emotion-detection : YOLOv8 best.onnx (브라우저 추론)
  └ gaze-tracking     : MediaPipe FaceLandmarker
        → 모든 결과 stores/sessionStore.ts (단일 스토어)
backend (FastAPI 오케스트레이터)
  STT → speech_analysis → vision_fusion(음성⊕표정) → LLM → TTS
  + session/report (시선·감정 로그 포함)
ollama (사이드카) : model-f16.gguf → /api/chat
```

## 실행 단계 & 진행 체크리스트

### P1 · 토대 정리 (프론트 일원화)  ✅ 완료
- [x] `stores/sessionStore.ts`에 비전 상태/액션 추가(facialEmotion, emotionLog,
      gazeLog, lipSyncVolume, set/add/reset)
- [x] `types/domain.ts`에 비전 타입 추가(VisionEmotion, GazeDirection,
      EmotionSample, GazeSample)
- [x] `EmotionDetector.jsx → emotion-detection/EmotionDetector.tsx` (단일 스토어)
- [x] `MediaPipeGaze.jsx → gaze-tracking/GazeTracker.tsx`
- [x] `package.json` 의존성 추가: onnxruntime-web, @mediapipe/tasks-vision,
      three, @pixiv/three-vrm (+ @types/three)
- [~] 잔여 `store/sessionStore.js` · `AvatarViewer.jsx` · `TTSPlayer.jsx`는
      VRM 스택 변환과 함께 P2에서 정리 (현재 미마운트라 빌드 무해)
- [ ] `npm install` 후 `npm run typecheck`로 검증 (다음 단계 진입 전 필요)

### P2 · 비전 융합 (멀티모달 파이프라인)  ✅ 완료
- [x] RolePlayPage에 표정(EmotionDetector)·시선(GazeTracker) 마운트 + VRM 아바타 채택
- [x] `VRMAvatar.tsx`(표정→아바타 표정 미러링) + `useLipSyncAudio`(TTS 볼륨→입모양)
- [x] 발화 제출 시 표정 스냅샷 동봉(store.facialEmotion→ws/FormData→backend)
- [x] backend `services/vision_fusion.py`: 음성감정 ⊕ 표정감정 → 최종 emotion
- [x] LLM child_profile에 facial_emotion/fused_emotion 주입(P3에서 프롬프트 활용)
- [x] 죽은 파일 정리: AvatarViewer.jsx·TTSPlayer.jsx·store/sessionStore.js 제거
- [x] 검증: frontend `tsc --noEmit` + `vite build` 통과, backend `py_compile` 통과

### P2.5 · 수동 QA 피드백 반영  ✅ 완료
- [x] #5 ONNX `no available backend`: wasm이 index.html로 응답되던 문제 →
      `ort.env.wasm.wasmPaths`=CDN(1.27.0) + `numThreads=1` 고정
- [x] #1 아바타 표정: 웹캠 표정 대신 `currentEmotion`(LLM 응답 감정)→VRM 표정
- [x] #2/#4a 정면 집중도: `buildReport`가 `gazeLog`로 `gaze_summary` 계산
- [x] #3 립싱크: 발화 중(phase=speaking) 볼륨 데이터 없으면 합성 입모양 폴백
- [x] #4b 리포트 레이아웃: 참여도+정면집중도 게이지 한 행, 3지표 하단 전체 행
- [x] #6 장소별 배경: VRM 씬에 location→그라데이션 배경(+이미지 자동 교체)
- [x] 보강: 표정·시선 단일 웹캠 스트림 공유(`lib/webcam.ts`)로 카메라 이중 점유 제거
- [x] 검증: `tsc --noEmit` + `vite build` 통과

### P2.6 · 리소스 위치 정리  ✅ 완료
- [x] VRM(`김하은/김하준.vrm`) `public/` → `src/assets/avatars/` (Vite `?url` 번들,
      `AVATAR_URLS` 맵, `*.vrm?url` 타입 선언 추가)
- [x] 배경 이미지: `src/assets/backgrounds/`에서 `import.meta.glob` 자동 수집
      (시나리오별 고유 파일명 매핑)
- [x] ONNX(`best.onnx`) `public/` → `ai/models/` (모델 단일 출처).
      브라우저 로드를 위해 `vite-plugin-static-copy`로 dev 서빙·빌드 시
      `/best.onnx`로 복사 (dev curl 검증: 200·5.6MB·protobuf)
- [x] 안정화: ErrorBoundary 추가 + VRMAvatar 셋업 try/catch 격리(빈 화면 방지)

### P3 · LLM 실서빙 (Ollama 사이드카)  ✅ 완료
- [x] docker-compose `ollama` 서비스 + GGUF/Modelfile/entrypoint 마운트 + `ollama_data` 볼륨
- [x] `ollama/Modelfile`(FROM gguf + params) + `ollama/entrypoint.sh`(serve→`ollama create mazutalk`)
- [x] `llm_client.py` Ollama `/api/chat` 어댑터: RP 시스템 프롬프트(단일 출처 마운트) +
      RP 입력 JSON(scenario/difficulty/emotion_state/observed_features/history) +
      `format:json`·`think:false`·temp0.7/top_p0.8/top_k20 → 출력 JSON 파싱(child_message→
      therapist_reply, coaching.next_goal→next_prompt). 실패 시 규칙기반 fallback 유지
- [x] `scenario_catalog.py`로 백엔드에 시나리오 컨텍스트(난이도·목표) grounding
- [x] env: OLLAMA_URL, LLM_MODEL, RP_PROMPT_PATH, AI_SERVICE_TIMEOUT(120)
- [x] 검증: py_compile, compose config, 파싱 스모크 테스트 통과
- [ ] 미검증(실행 필요): 7.5GB 모델 실제 추론(요구: `docker compose up --build` + CPU 로드)

### P3.5 · CPU 데모용 양자화  ✅ 완료
- [x] `model-f16.gguf`(7.5GB) → `model-q4_k_m.gguf`(2.3GB) 로컬 `llama-quantize` 변환
      (llama.cpp b9781 win-cpu-x64, Q4_K_M, 4.95 BPW, GGUF 검증)
- [x] Ollama Modelfile `FROM model-q4_k_m.gguf` + compose 마운트 Q4로 교체
- [x] f16 은 고정밀 기준으로 보존
- 주의: 첫 quantize 시 Bash 파이프가 쓰기를 절단 → PowerShell 재실행으로 해결

### 통합 상태: STT→분석→비전융합→**LLM(Ollama, Q4)**→TTS 전 구간 단일 compose로 연결됨.

### P4 · 리포트 융합 & 마무리  ⬜
- [ ] 종료 시 gaze_summary·표정 타임라인 리포트 반영(report.ts)
- [ ] 비전 로그 백엔드 영속화 엔드포인트
- [ ] 엔드투엔드 점검 + README/docs 갱신

## 결정 로그
- LLM 서빙: **Ollama 사이드카 컨테이너** (사용자 승인 2026-06-24)
- 비전 통합 범위: **파이프라인 + 리포트 완전 융합** (승인)
- 프론트 정리: **TypeScript 완전 통합** (승인)
- 아바타 스택: VRM 정식 채택 권장 (오케스트레이터 제안, 거부 가능)
