// frontend/src/features/gaze-tracking/GazeTracker.tsx
// [역할] MediaPipe FaceLandmarker 기반 실시간 시선 추적 컴포넌트.
// 웹캠 → 홍채 위치 분석 → 시선 방향 판별 → 단일 sessionStore(gazeLog)에 누적.
// 리포트의 gaze_summary(정면 집중도)는 이 로그로부터 계산된다.

import { useEffect, useRef, useState } from 'react'
import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision'
import { useSessionStore } from '@/stores/sessionStore'
import { acquireWebcam, releaseWebcam } from '@/lib/webcam'
import type { GazeDirection } from '@/types/domain'

const LOG_INTERVAL_MS = 1000

// CDN 경로는 환경변수로 덮어쓸 수 있다(폐쇄망 self-host 대비).
const env = import.meta.env as Record<string, string | undefined>
const WASM_BASE =
  env.VITE_MEDIAPIPE_WASM ??
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
const MODEL_URL =
  env.VITE_FACE_LANDMARKER_MODEL ??
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'

interface GazeTrackerProps {
  /** 랜드마크 시각화 캔버스 표시 여부 (기본 false) */
  showCanvas?: boolean
  className?: string
}

export function GazeTracker({ showCanvas = false, className }: GazeTrackerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const animFrameRef = useRef<number | null>(null)
  const lastLogTimeRef = useRef(0)
  const isMountedRef = useRef(true)

  const [status, setStatus] = useState('초기화 중...')
  const addGazeSample = useSessionStore((s) => s.addGazeSample)

  useEffect(() => {
    isMountedRef.current = true
    let faceLandmarker: FaceLandmarker | null = null

    const init = async () => {
      try {
        const vision = await FilesetResolver.forVisionTasks(WASM_BASE)
        faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: MODEL_URL },
          runningMode: 'VIDEO',
          numFaces: 1,
          outputFaceBlendshapes: false,
        })

        const stream = await acquireWebcam()
        const video = videoRef.current
        if (!video) return
        video.srcObject = stream
        video.onloadedmetadata = () => void video.play()
        setStatus('시선 추적 중')

        const detect = () => {
          if (video.readyState >= 2 && faceLandmarker) {
            const results = faceLandmarker.detectForVideo(video, performance.now())
            if (results.faceLandmarks.length > 0) {
              const landmarks = results.faceLandmarks[0]
              // 왼쪽 홍채(468), 눈 안쪽(33), 바깥쪽(133)으로 홍채 상대위치 계산
              const leftIris = landmarks[468]
              const leftEyeInner = landmarks[33]
              const leftEyeOuter = landmarks[133]

              if (leftIris && leftEyeOuter && leftEyeInner) {
                const eyeWidth = Math.abs(leftEyeOuter.x - leftEyeInner.x)
                const irisPos = (leftIris.x - leftEyeInner.x) / eyeWidth

                let direction: GazeDirection = 'center'
                if (irisPos < 0.35) direction = 'right'
                else if (irisPos > 0.65) direction = 'left'

                const now = Date.now()
                if (now - lastLogTimeRef.current >= LOG_INTERVAL_MS) {
                  lastLogTimeRef.current = now
                  addGazeSample({
                    direction,
                    irisPos: parseFloat(irisPos.toFixed(3)),
                    timestamp: now,
                  })
                }
              }
            }
          }
          if (isMountedRef.current) {
            animFrameRef.current = requestAnimationFrame(detect)
          }
        }
        detect()
      } catch (error) {
        if (isMountedRef.current) setStatus(`오류: ${(error as Error).message}`)
      }
    }

    void init()

    return () => {
      isMountedRef.current = false
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      faceLandmarker?.close()
      if (videoRef.current) videoRef.current.srcObject = null
      releaseWebcam()
    }
  }, [addGazeSample])

  return (
    <div className={className}>
      <video
        ref={videoRef}
        width={160}
        height={120}
        autoPlay
        muted
        playsInline
        style={{ display: showCanvas ? 'block' : 'none', borderRadius: 8 }}
      />
      <p className="text-xs text-brand-400">{status}</p>
    </div>
  )
}

export default GazeTracker
