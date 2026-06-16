// frontend/src/store/avatarStore.js
// [역할] 컴포넌트 간 공유 데이터 저장소 (Zustand)

import { create } from "zustand";

const useAvatarStore = create((set) => ({


  volume: 0,           // TTS 음성 재생 중 실시간 볼륨 값 (립싱크용)
  isPlaying: false,    // 현재 음성 재생 중인지 여부
  emotion: "neutral",  // 현재 감정 상태 (표정 전환용)
  character: "하은",   // 현재 선택된 캐릭터 ('하은' / '하준')


  // 추가
  // + sttResult: "",    // STT로 변환된 아동 발화 텍스트

  // 추가
  // + currentScenario: null,  // 현재 진행 중인 시나리오
  // + llmResponse: null,      // LLM 응답 텍스트 + 감정 태그



  // ── 값을 바꾸는 함수들 ────────────────────────
  setVolume: (volume) => set({ volume }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setEmotion: (emotion) => set({ emotion }),
  setCharacter: (character) => set({ character }),
}));

export default useAvatarStore;