// frontend/src/store/sessionStore.js
// [역할] 컴포넌트 간 공유 데이터 저장소 (Zustand)

import { create } from "zustand";

const useSessionStore = create((set) => ({

  volume: 0,           // TTS 음성 재생 중 실시간 볼륨 값 (립싱크용)
  isPlaying: false,    // 현재 음성 재생 중인지 여부
  emotion: "neutral",  // 현재 감정 상태 (표정 전환용)
  character: "하은",   // 현재 선택된 캐릭터 ('하은' / '하준')
  avatarState: "idle", // 아바타 상태 (idle / speaking / waiting / greeting)

  // ── Learning Report용 로그 데이터 ────────────────
  emotionLog: [],      // 감정 로그 누적 [{ label, confidence, timestamp }]
  gazeLog: [],         // 시선 로그 누적 [{ direction, irisPos, timestamp }]


  // 추가 예정 (채민님)
  // + sttResult: "",          // STT 변환 텍스트
  // + responseTime: [],       // 반응 속도 로그

  // 추가 예정 (민지님)
  // + currentScenario: null,  // 현재 시나리오
  // + llmResponse: null,      // LLM 응답
  // + scenarioResult: {},     // 시나리오 진행 결과

  
  // ── 값을 바꾸는 함수들 ────────────────────────
  setVolume: (volume) => set({ volume }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setEmotion: (emotion) => set({ emotion }),
  setCharacter: (character) => set({ character }),
  setAvatarState: (avatarState) => set({ avatarState }),

  // 감정 로그 누적 함수
  addEmotionLog: (entry) => set((state) => ({
    emotionLog: [...state.emotionLog, entry],
  })),

  // 시선 로그 누적 함수
  addGazeLog: (entry) => set((state) => ({
    gazeLog: [...state.gazeLog, entry],
  })),

  // 세션 종료 시 로그 초기화
  resetLogs: () => set({ emotionLog: [], gazeLog: [] }),
}));

export default useSessionStore;