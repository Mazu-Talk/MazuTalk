// frontend/src/hooks/useLipSyncAudio.ts
// [역할] 백엔드 TTS(audio_url)를 Web Audio로 재생하면서 실시간 볼륨을 추출해
// sessionStore.lipSyncVolume에 흘려보낸다 → VRM 아바타 입 모양 동기화.

import { useCallback, useRef } from 'react'
import { useSessionStore } from '@/stores/sessionStore'

export function useLipSyncAudio() {
  const setLipSyncVolume = useSessionStore((s) => s.setLipSyncVolume)
  const ctxRef = useRef<AudioContext | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const rafRef = useRef<number | null>(null)

  const stop = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = null
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setLipSyncVolume(0)
  }, [setLipSyncVolume])

  const play = useCallback(
    (url: string, opts?: { onEnd?: () => void }) => {
      stop()
      const ctx = ctxRef.current ?? new AudioContext()
      ctxRef.current = ctx
      void ctx.resume()

      const audio = new Audio(url)
      audio.crossOrigin = 'anonymous'
      audioRef.current = audio

      const source = ctx.createMediaElementSource(audio)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyser.connect(ctx.destination)

      const data = new Uint8Array(analyser.frequencyBinCount)
      const tick = () => {
        if (audio.paused || audio.ended) {
          setLipSyncVolume(0)
          return
        }
        analyser.getByteFrequencyData(data)
        const avg = data.reduce((a, b) => a + b, 0) / data.length
        setLipSyncVolume(avg / 128)
        rafRef.current = requestAnimationFrame(tick)
      }

      const end = () => {
        setLipSyncVolume(0)
        opts?.onEnd?.()
      }
      audio.onended = end
      audio.onerror = end
      void audio
        .play()
        .then(() => tick())
        .catch(end)
    },
    [setLipSyncVolume, stop],
  )

  return { play, stop }
}
