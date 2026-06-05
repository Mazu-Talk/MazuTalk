// frontend/src/features/voice-interaction/TTSPlayer.jsx
// [역할] TTS 기능을 담당하는 React 컴포넌트
// 텍스트 입력 → FastAPI /tts 요청 → 음성 자동 재생

import { useState } from "react";

function TTSPlayer() {
  // ── 상태(state) 정의 ──────────────────────────────
  const [text, setText] = useState("안녕! 나 미래야. 같이 놀자!"); // 텍스트 입력창 내용
  const [isLoading, setIsLoading] = useState(false);               // 변환 중 여부 (버튼 비활성화용)
  const [audioUrl, setAudioUrl] = useState(null);                  // 받아온 음성 URL 저장

  // ── TTS 요청 함수 ─────────────────────────────────
  const handleTTS = async () => {
    setIsLoading(true); // 버튼 "변환 중..."으로 변경

    try {
      // FastAPI POST /tts 로 텍스트 전송
      const response = await fetch("http://localhost:8000/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, speed: 0.8 }),
      });

      // 응답에서 audio_url 추출
      // 예: { "audio_url": "http://localhost:8000/audio/abc123.wav", "text": "..." }
      const data = await response.json();
      setAudioUrl(data.audio_url); // URL 상태에 저장 (하단 <audio> 태그에 표시됨)

      // 받은 URL로 음성 자동 재생
      const audio = new Audio(data.audio_url);
      audio.play();

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