// frontend/src/features/voice-interaction/TTSPlayer.jsx
// [역할] TTS 재생 컴포넌트
// - sessionStore의 llmResponse 감지 → 자동재생 (실제 서비스)
// - llmResponse 없으면 입력창 표시 (개발/테스트 모드)

import { useState, useRef, useEffect } from "react";
import useSessionStore from "../../store/sessionStore";

function TTSPlayer() {
  // ── 개발 모드용 입력창 상태 ─────────────────────────
  const [inputText, setInputText] = useState("안녕, 나는 하준이야. 같이 놀자!");
  const [isLoading, setIsLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);

  const audioRef = useRef(null);

  // ── Zustand에서 읽기 ────────────────────────────────
  const llmResponse = useSessionStore((state) => state.llmResponse); // 추후 민지/채민이 저장
  const setVolume = useSessionStore((state) => state.setVolume);
  const setIsPlaying = useSessionStore((state) => state.setIsPlaying);
  const setAvatarState = useSessionStore((state) => state.setAvatarState);

  // ── llmResponse 변경 감지 → 자동재생 ───────────────
  // llmResponse가 null이 아닐 때만 실행 (store에 추가되면 자동으로 동작)
  useEffect(() => {
    if (llmResponse) {
      handleTTS(llmResponse);
    }
  }, [llmResponse]);

  // ── TTS 요청 함수 ───────────────────────────────────
  const handleTTS = async (targetText = inputText) => {
    setIsLoading(true);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: targetText, speed: 1.1 }),
      });

      const data = await response.json();
      setAudioUrl(data.audio_url);

      // 기존 재생 중인 오디오 정지 (중첩 재생 방지)
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }

      // ── Web Audio API로 음성 재생 + 볼륨 추출 ──────
      const audioContext = new AudioContext();
      const audioElement = new Audio(data.audio_url);
      audioElement.crossOrigin = "anonymous";
      audioRef.current = audioElement;

      // 볼륨 분석기 연결 → Zustand로 전달 → 아바타 립싱크에 사용
      const source = audioContext.createMediaElementSource(audioElement);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyser.connect(audioContext.destination);

      try {
        await audioElement.play();
        setIsPlaying(true);
        setAvatarState("speaking");
      } catch (e) {
        console.warn("자동재생 차단됨:", e);
      }

      // 매 프레임마다 볼륨 추출 → Zustand 저장 → 아바타 입모양 싱크
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateVolume = () => {
        if (audioElement.paused || audioElement.ended) {
          setVolume(0);
          setIsPlaying(false);
          setAvatarState("waiting");
          return;
        }
        analyser.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
        setVolume(avg / 128);
        requestAnimationFrame(updateVolume);
      };
      updateVolume();

    } catch (error) {
      console.error("TTS 오류:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // ── 렌더링 ──────────────────────────────────────────
  return (
    <div>
      {/* 개발/테스트 모드: llmResponse가 store에 없을 때만 입력창 표시 */}
      {!llmResponse && (
        <>
          <h2>TTS 테스트</h2>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            rows={3}
            cols={40}
          />
          <br />
          <button onClick={() => handleTTS()} disabled={isLoading}>
            {isLoading ? "변환 중..." : "음성으로 변환"}
          </button>
        </>
      )}

      {/* 실제 서비스 모드: 변환 중 표시 */}
      {llmResponse && isLoading && <p>음성 변환 중...</p>}

      {/* 개발 모드에서만 audio_url + 수동 컨트롤러 표시 */}
      {!llmResponse && audioUrl && (
        <div>
          <p>audio_url: {audioUrl}</p>
          <audio controls src={audioUrl} />
        </div>
      )}
    </div>
  );
}

export default TTSPlayer;
