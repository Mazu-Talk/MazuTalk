// frontend/src/features/emotion-detection/EmotionDetector.jsx
// [역할] YOLOv8 ONNX 모델 기반 실시간 표정 감정 분류 컴포넌트
// 웹캠 영상 → ONNX 모델 추론 → 감정 분류 결과 → sessionStore에 저장

import { useEffect, useRef, useState } from "react";
import * as ort from "onnxruntime-web";
import useSessionStore from "../../store/sessionStore";

// 감정 클래스 순서 (Roboflow 학습 시 알파벳 순으로 정렬됨)
const CLASSES = ["happy", "neutral", "sad", "surprised"];

function EmotionDetector() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const sessionRef = useRef(null);   // ONNX 세션
  const animFrameRef = useRef(null); // 애니메이션 프레임 ID
  const [status, setStatus] = useState("초기화 중...");
  const [scores, setScores] = useState([]);

  // Zustand에 감정 저장
  const setEmotion = useSessionStore((state) => state.setEmotion);

  useEffect(() => {
    const init = async () => {
      try {
        // ONNX 모델 로드
        setStatus("모델 로드 중...");
        sessionRef.current = await ort.InferenceSession.create("/best.onnx");
        setStatus("모델 로드 완료! 웹캠 시작 중...");

        // 웹캠 시작
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play();
        };

        setStatus("웹캠 실행 중 - 표정 감지 중...");

        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");

        const detect = async () => {
          if (videoRef.current && videoRef.current.readyState >= 2) {
            // 웹캠 영상 → 224x224 캔버스에 그리기
            ctx.drawImage(videoRef.current, 0, 0, 224, 224);

            // 이미지 → ONNX 텐서 변환
            const imageData = ctx.getImageData(0, 0, 224, 224);
            const tensor = preprocessImage(imageData);

            // 추론 실행
            const feeds = { [sessionRef.current.inputNames[0]]: tensor };
            const results = await sessionRef.current.run(feeds);
            const output = results[sessionRef.current.outputNames[0]].data;

            // softmax 적용 → 확률값으로 변환
            const softmaxScores = softmax(Array.from(output));
            const maxIdx = softmaxScores.indexOf(Math.max(...softmaxScores));
            const dominantEmotion = CLASSES[maxIdx];
            const confidence = softmaxScores[maxIdx];

            // 신뢰도 50% 이상일 때만 감정 업데이트
            if (confidence > 0.5) {
              // YOLOv8 클래스명 → sessionStore 감정명으로 변환
              const emotionMap = {
                happy: "joyful",
                sad: "sad",
                surprised: "surprised",
                neutral: "neutral",
              };
              setEmotion(emotionMap[dominantEmotion]);
            }

            setScores(softmaxScores.map((s, i) => ({
              label: CLASSES[i],
              score: s,
            })));
          }
          animFrameRef.current = requestAnimationFrame(detect);
        };
        detect();

      } catch (error) {
        setStatus(`오류: ${error.message}`);
      }
    };

    init();

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (videoRef.current?.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  // 이미지 데이터 → ONNX 텐서 변환 (CHW 형식, 0~1 정규화)
  const preprocessImage = (imageData) => {
    const { data, width, height } = imageData;
    const float32 = new Float32Array(3 * width * height);

    for (let i = 0; i < width * height; i++) {
      float32[i] = data[i * 4] / 255.0;                      // R
      float32[i + width * height] = data[i * 4 + 1] / 255.0; // G
      float32[i + 2 * width * height] = data[i * 4 + 2] / 255.0; // B
    }

    return new ort.Tensor("float32", float32, [1, 3, height, width]);
  };

  // Softmax 함수
  const softmax = (arr) => {
    const max = Math.max(...arr);
    const exp = arr.map(x => Math.exp(x - max));
    const sum = exp.reduce((a, b) => a + b, 0);
    return exp.map(x => x / sum);
  };

  return (
    <div>
      <h2>표정 감정 분류</h2>
      <p>상태: {status}</p>

      {/* 웹캠 화면 표시 */}
      <video
        ref={videoRef}
        width={320}
        height={240}
        style={{ borderRadius: 8 }}
        autoPlay
        muted
      />

      {/* 전처리용 캔버스 (숨김) */}
      <canvas ref={canvasRef} width={224} height={224} style={{ display: "none" }} />

      {/* 감정별 점수 */}
      <div>
        <h3>감정 점수</h3>
        {scores.map((s) => (
          <div key={s.label} style={{ marginBottom: 4 }}>
            <span>{s.label}: {(s.score * 100).toFixed(1)}%</span>
            <div style={{
              width: `${s.score * 200}px`,
              height: 8,
              background: "#4a90e2",
              borderRadius: 4,
            }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default EmotionDetector;