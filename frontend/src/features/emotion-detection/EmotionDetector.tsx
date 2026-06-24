// frontend/src/features/emotion-detection/EmotionDetector.tsx
// [역할] YOLOv8 ONNX(best.onnx) 기반 실시간 표정 감정 분류 컴포넌트.
// 웹캠 영상 → ONNX 추론 → 감정 분류 → 단일 sessionStore(facialEmotion/emotionLog)에 반영.
// RolePlay 화면에 마운트되어 음성 파이프라인과 표정 신호를 융합한다.

import { useEffect, useRef, useState } from 'react'
import * as ort from 'onnxruntime-web'
import { useSessionStore } from '@/stores/sessionStore'
import { acquireWebcam, releaseWebcam } from '@/lib/webcam'
import type { VisionEmotion } from '@/types/domain'

// WASM 백엔드 안정화: 번들러가 해시한 .wasm 대신 CDN에서 직접 로드(버전 고정),
// threaded wasm은 cross-origin isolation을 요구하므로 단일 스레드로 강제.
// (이 설정이 없으면 dev 서버가 .wasm 대신 index.html을 반환해 'no available backend' 발생)
ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.27.0/dist/'
ort.env.wasm.numThreads = 1

// 감정 클래스 순서 (Roboflow 학습 시 알파벳 순으로 정렬됨)
const CLASSES: VisionEmotion[] = ['happy', 'neutral', 'sad', 'surprised']

// 감정 로그 누적 간격 (매 프레임 저장은 과다 → 1초마다)
const LOG_INTERVAL_MS = 1000
const INPUT_SIZE = 224
const CONFIDENCE_THRESHOLD = 0.5

interface EmotionDetectorProps {
  /** 디버그용 점수 막대 표시 여부 (기본 false: 데모에서는 숨김) */
  showScores?: boolean
  className?: string
}

export function EmotionDetector({ showScores = false, className }: EmotionDetectorProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const sessionRef = useRef<ort.InferenceSession | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const lastLogTimeRef = useRef(0)
  const isMountedRef = useRef(true)

  const [status, setStatus] = useState('초기화 중...')
  const [scores, setScores] = useState<{ label: VisionEmotion; score: number }[]>([])

  const setFacialEmotion = useSessionStore((s) => s.setFacialEmotion)
  const addEmotionSample = useSessionStore((s) => s.addEmotionSample)

  useEffect(() => {
    isMountedRef.current = true

    const init = async () => {
      try {
        setStatus('모델 로드 중...')
        sessionRef.current = await ort.InferenceSession.create('/best.onnx')

        const stream = await acquireWebcam()
        const video = videoRef.current
        if (!video) return
        video.srcObject = stream
        video.onloadedmetadata = () => void video.play()
        setStatus('표정 감지 중')

        const canvas = canvasRef.current
        const ctx = canvas?.getContext('2d')
        if (!canvas || !ctx) return

        const detect = async () => {
          const session = sessionRef.current
          if (video.readyState >= 2 && session) {
            ctx.drawImage(video, 0, 0, INPUT_SIZE, INPUT_SIZE)
            const imageData = ctx.getImageData(0, 0, INPUT_SIZE, INPUT_SIZE)
            const tensor = preprocessImage(imageData)

            const feeds = { [session.inputNames[0]]: tensor }
            const results = await session.run(feeds)
            const output = results[session.outputNames[0]].data as Float32Array
            const softmaxScores = softmax(Array.from(output))

            const maxIdx = softmaxScores.indexOf(Math.max(...softmaxScores))
            const dominantEmotion = CLASSES[maxIdx]
            const confidence = softmaxScores[maxIdx]

            if (confidence > CONFIDENCE_THRESHOLD && isMountedRef.current) {
              setFacialEmotion(dominantEmotion)
              const now = Date.now()
              if (now - lastLogTimeRef.current >= LOG_INTERVAL_MS) {
                lastLogTimeRef.current = now
                addEmotionSample({
                  label: dominantEmotion,
                  confidence: parseFloat(confidence.toFixed(3)),
                  timestamp: now,
                })
              }
            }

            if (isMountedRef.current && showScores) {
              setScores(softmaxScores.map((score, i) => ({ label: CLASSES[i], score })))
            }
          }
          if (isMountedRef.current) {
            animFrameRef.current = requestAnimationFrame(detect)
          }
        }
        void detect()
      } catch (error) {
        if (isMountedRef.current) {
          setStatus(`오류: ${(error as Error).message}`)
        }
      }
    }

    void init()

    return () => {
      isMountedRef.current = false
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      if (videoRef.current) videoRef.current.srcObject = null
      releaseWebcam()
    }
  }, [setFacialEmotion, addEmotionSample, showScores])

  return (
    <div className={className}>
      <video ref={videoRef} width={160} height={120} autoPlay muted playsInline
        style={{ borderRadius: 8 }} />
      <canvas ref={canvasRef} width={INPUT_SIZE} height={INPUT_SIZE} style={{ display: 'none' }} />
      <p className="text-xs text-brand-400">{status}</p>
      {showScores &&
        scores.map((s) => (
          <div key={s.label} className="text-xs text-brand-500">
            {s.label}: {(s.score * 100).toFixed(1)}%
          </div>
        ))}
    </div>
  )
}

/** 이미지 데이터 → ONNX 텐서 (CHW, 0~1 정규화) */
function preprocessImage(imageData: ImageData): ort.Tensor {
  const { data, width, height } = imageData
  const float32 = new Float32Array(3 * width * height)
  for (let i = 0; i < width * height; i++) {
    float32[i] = data[i * 4] / 255.0 // R
    float32[i + width * height] = data[i * 4 + 1] / 255.0 // G
    float32[i + 2 * width * height] = data[i * 4 + 2] / 255.0 // B
  }
  return new ort.Tensor('float32', float32, [1, 3, height, width])
}

/** Softmax */
function softmax(arr: number[]): number[] {
  const max = Math.max(...arr)
  const exp = arr.map((x) => Math.exp(x - max))
  const sum = exp.reduce((a, b) => a + b, 0)
  return exp.map((x) => x / sum)
}

export default EmotionDetector
