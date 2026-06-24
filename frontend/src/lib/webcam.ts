// frontend/src/lib/webcam.ts
// [역할] 웹캠 단일 스트림 공유 매니저.
// 표정(EmotionDetector)·시선(GazeTracker)이 카메라를 각각 열면 이중 점유가 되므로,
// 하나의 MediaStream을 ref-count로 공유한다. 여러 <video>가 같은 스트림을 srcObject로 쓸 수 있다.

let streamPromise: Promise<MediaStream> | null = null
let refCount = 0

/** 공유 웹캠 스트림 확보 (없으면 1회 getUserMedia). 사용 후 반드시 release. */
export function acquireWebcam(): Promise<MediaStream> {
  refCount += 1
  if (!streamPromise) {
    streamPromise = navigator.mediaDevices.getUserMedia({ video: true })
  }
  return streamPromise
}

/** 사용 종료. 마지막 사용자가 놓으면 트랙을 정지하고 스트림을 해제한다. */
export function releaseWebcam(): void {
  refCount = Math.max(0, refCount - 1)
  if (refCount === 0 && streamPromise) {
    const pending = streamPromise
    streamPromise = null
    void pending.then((s) => s.getTracks().forEach((t) => t.stop())).catch(() => {})
  }
}
