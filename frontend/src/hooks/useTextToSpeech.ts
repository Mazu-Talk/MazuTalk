import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 브라우저 TTS 훅 (Web Speech Synthesis, 한국어).
 * FR-007(음성 출력)을 백엔드 TTS 없이 충족한다.
 *
 * 백엔드 TTS(audio_url)가 제공되면 RolePlayPage 에서 <audio> 재생을 우선 사용하고,
 * 없을 때 이 훅으로 합성 음성을 재생한다.
 */
export interface UseTextToSpeech {
  supported: boolean
  speaking: boolean
  speak: (text: string, opts?: { onStart?: () => void; onEnd?: () => void }) => void
  cancel: () => void
}

export function useTextToSpeech(lang = 'ko-KR'): UseTextToSpeech {
  const supported =
    typeof window !== 'undefined' && 'speechSynthesis' in window
  const [speaking, setSpeaking] = useState(false)
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null)

  useEffect(() => {
    if (!supported) return
    const pickVoice = () => {
      const voices = window.speechSynthesis.getVoices()
      voiceRef.current =
        voices.find((v) => v.lang === lang) ??
        voices.find((v) => v.lang.startsWith('ko')) ??
        null
    }
    pickVoice()
    window.speechSynthesis.onvoiceschanged = pickVoice
    return () => {
      window.speechSynthesis.onvoiceschanged = null
    }
  }, [supported, lang])

  const speak = useCallback<UseTextToSpeech['speak']>(
    (text, opts) => {
      if (!supported || !text.trim()) {
        opts?.onStart?.()
        opts?.onEnd?.()
        return
      }
      // 진행 중 음성 중단 후 새로 재생
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = lang
      if (voiceRef.current) utterance.voice = voiceRef.current
      // 아동 친화: 약간 느리고 살짝 높은 톤 (RP 프롬프트 tts_style: slow/warm)
      utterance.rate = 0.92
      utterance.pitch = 1.15
      utterance.onstart = () => {
        setSpeaking(true)
        opts?.onStart?.()
      }
      utterance.onend = () => {
        setSpeaking(false)
        opts?.onEnd?.()
      }
      utterance.onerror = () => {
        setSpeaking(false)
        opts?.onEnd?.()
      }
      window.speechSynthesis.speak(utterance)
    },
    [supported, lang],
  )

  const cancel = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  // 언마운트 시 음성 정리
  useEffect(() => {
    return () => {
      if (supported) window.speechSynthesis.cancel()
    }
  }, [supported])

  return { supported, speaking, speak, cancel }
}
