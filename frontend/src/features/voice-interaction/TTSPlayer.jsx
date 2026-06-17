// frontend/src/features/voice-interaction/TTSPlayer.jsx
// [역할] TTS 기능을 담당하는 React 컴포넌트
// 텍스트 입력 → FastAPI /tts 요청 → 음성 자동 재생

import { useState, useRef } from "react";
import useAvatarStore from "../store/avatarStore";

function TTSPlayer() {
  // ── 상태(state) 정의 ──────────────────────────────
  const [text, setText] = useState("안녕! 나 미래야. 같이 놀자!"); // 텍스트 입력창 내용
  const [isLoading, setIsLoading] = useState(false);               // 변환 중 여부 (버튼 비활성화용)
  const [audioUrl, setAudioUrl] = useState(null);                  // 받아온 음성 URL 저장

  // 단일 오디오 인스턴스 관리 (중첩 재생 방지)
  const audioRef = useRef(null);

  // Zustand에서 값 바꾸는 함수 가져오기
  const setVolume = useAvatarStore((state) => state.setVolume);
  const setIsPlaying = useAvatarStore((state) => state.setIsPlaying);
  const setAvatarState = useAvatarStore((state) => state.setAvatarState);

  // ── TTS 요청 함수 ─────────────────────────────────
  const handleTTS = async () => {
    setIsLoading(true); // 버튼 "변환 중..."으로 변경

    try {
      // FastAPI POST /tts 로 텍스트 전송
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, speed: 0.8 }),
      });

      // 응답에서 audio_url 추출
      const data = await response.json();
      setAudioUrl(data.audio_url);

      // 기존 재생 중인 오디오 정지 (중첩 재생 방지)
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }

      // ── Web Audio API로 음성 재생 + 볼륨 추출 ──
      const audioContext = new AudioContext();
      const audioElement = new Audio(data.audio_url);
      audioElement.crossOrigin = "anonymous";
      audioRef.current = audioElement; // ref에 저장

      // 볼륨 분석기 연결
      const source = audioContext.createMediaElementSource(audioElement);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyser.connect(audioContext.destination);

      // 자동재생 예외처리
      try {
        await audioElement.play();
        setIsPlaying(true); // Zustand에 재생 중 저장
        setAvatarState("speaking");
      } catch (e) {
        console.warn("자동재생 차단됨:", e);
      }

      // 매 프레임마다 볼륨 값 추출 → Zustand에 저장
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateVolume = () => {
        if (audioElement.paused || audioElement.ended) {
          setVolume(0);        // 재생 끝나면 볼륨 0
          setIsPlaying(false); // Zustand에 재생 종료 저장
          setAvatarState("waiting");
          return;
        }
        analyser.getByteFrequencyData(dataArray);

        // 평균 볼륨 계산 (0~1 사이 값으로 변환)
        const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
        setVolume(avg / 128); // Zustand에 볼륨 저장

        requestAnimationFrame(updateVolume); // 다음 프레임에도 반복
      };
      updateVolume();

    } catch (error) {
      // 서버가 꺼져있거나 네트워크 오류 시 콘솔에 출력
      console.error("TTS 오류:", error);
    } finally {
      setIsLoading(false); // 성공/실패 상관없이 버튼 다시 활성화
    }
  };

  // ── 화면 렌더링 ───────────────────────────────────
  return (
    <div>
      <h2>TTS 테스트</h2>

      {/* 텍스트 입력창 - onChange로 text 상태 실시간 업데이트 */}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        cols={40}
      />

      <br />

      {/* 변환 버튼 - 변환 중일 때 클릭 비활성화 */}
      <button onClick={handleTTS} disabled={isLoading}>
        {isLoading ? "변환 중..." : "음성으로 변환"}
      </button>

      {/* audioUrl이 있을 때만 표시 (처음엔 null이라 숨겨져 있음) */}
      {audioUrl && (
        <div>
          <p>audio_url: {audioUrl}</p>
          {/* 수동 재생 컨트롤러 (자동재생 외에 직접 재생/정지 가능) */}
          <audio controls src={audioUrl} />
        </div>
      )}
    </div>
  );
}

export default TTSPlayer;