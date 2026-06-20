// [역할] MediaPipe 기반 시선 추적 실험용 컴포넌트

import { useEffect, useRef, useState } from "react";
import { FaceLandmarker, FilesetResolver, DrawingUtils } from "@mediapipe/tasks-vision";

function MediaPipeTest() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [status, setStatus] = useState("초기화 중...");
  const [gazeResult, setGazeResult] = useState(null);

  useEffect(() => {
    let faceLandmarker;
    let animFrame;

    const init = async () => {
      try {
        const vision = await FilesetResolver.forVisionTasks(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
        );

        faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
          },
          runningMode: "VIDEO",
          numFaces: 1,
          outputFaceBlendshapes: false, // 표정 분석 비활성화
        });

        setStatus("모델 로드 완료! 웹캠 시작 중...");

        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play();
        };

        setStatus("웹캠 실행 중 - 시선 추적 중...");

        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        const drawingUtils = new DrawingUtils(ctx);

        const detect = () => {
          if (videoRef.current && videoRef.current.readyState >= 2) {
            const results = faceLandmarker.detectForVideo(
              videoRef.current,
              performance.now()
            );

            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);

            if (results.faceLandmarks.length > 0) {
              const landmarks = results.faceLandmarks[0];

              // 얼굴 랜드마크 그리기
              drawingUtils.drawConnectors(
                landmarks,
                FaceLandmarker.FACE_LANDMARKS_TESSELATION,
                { color: "#C0C0C070", lineWidth: 1 }
              );

              // ── 시선 추적 ──────────────────────────────
              const leftIris = landmarks[468];
              const leftEyeInner = landmarks[33];
              const leftEyeOuter = landmarks[133];

              if (leftIris && leftEyeOuter && leftEyeInner) {
                const eyeWidth = Math.abs(leftEyeOuter.x - leftEyeInner.x);
                const irisPos = (leftIris.x - leftEyeInner.x) / eyeWidth;

                let gazeDirection = "정면";
                if (irisPos < 0.35) gazeDirection = "오른쪽 ←";
                else if (irisPos > 0.65) gazeDirection = "왼쪽 →";

                setGazeResult(`시선: ${gazeDirection} (${irisPos.toFixed(2)})`);
              }

              // 홍채 표시
              [landmarks[468], landmarks[473]].forEach((iris) => {
                if (iris) {
                  ctx.beginPath();
                  ctx.arc(iris.x * canvas.width, iris.y * canvas.height, 5, 0, 2 * Math.PI);
                  ctx.fillStyle = "#00ff00";
                  ctx.fill();
                }
              });

            } else {
              setGazeResult("얼굴 감지 안 됨");
            }
          }
          animFrame = requestAnimationFrame(detect);
        };
        detect();

      } catch (error) {
        setStatus(`오류: ${error.message}`);
      }
    };

    init();

    return () => {
      if (animFrame) cancelAnimationFrame(animFrame);
      if (videoRef.current?.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  return (
    <div>
      <h2>MediaPipe 시선 추적 실험</h2>
      <p>상태: {status}</p>
      <p>{gazeResult ?? "대기 중"}</p>
      <div>
        <video ref={videoRef} style={{ display: "none" }} width={640} height={480} />
        <canvas ref={canvasRef} width={640} height={480} />
      </div>
    </div>
  );
}

export default MediaPipeTest;