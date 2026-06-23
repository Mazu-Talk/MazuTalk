import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 브라우저 STT 훅 (Web Speech API, 한국어).
 * FR-002(음성 입력) / FR-003(음성 인식)을 백엔드 없이 충족한다.
 *
 * 지원하지 않는 브라우저에서는 supported=false 를 반환하고,
 * 호출부는 텍스트 입력 대체 경로(MicButton 의 fallback)를 사용한다.
 */
export interface SpeechRecognitionState {
  supported: boolean
  listening: boolean
  /** 확정된 최종 인식 텍스트 */
  transcript: string
  /** 인식 중 임시 텍스트 */
  interim: string
  error: string | null
}

export interface UseSpeechRecognition extends SpeechRecognitionState {
  start: () => void
  stop: () => void
  reset: () => void
}

function getRecognitionCtor(): typeof SpeechRecognition | undefined {
  if (typeof window === 'undefined') return undefined
  return window.SpeechRecognition ?? window.webkitSpeechRecognition
}

export function useSpeechRecognition(lang = 'ko-KR'): UseSpeechRecognition {
  const Ctor = getRecognitionCtor()
  const supported = Boolean(Ctor)

  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)

  const recognitionRef = useRef<SpeechRecognition | null>(null)

  useEffect(() => {
    if (!Ctor) return
    const recognition = new Ctor()
    recognition.lang = lang
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setListening(true)
      setError(null)
    }
    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        const text = result[0]?.transcript ?? ''
        if (result.isFinal) finalText += text
        else interimText += text
      }
      if (finalText) setTranscript((prev) => (prev + finalText).trim())
      setInterim(interimText)
    }
    recognition.onerror = (event) => {
      // 'no-speech' / 'aborted' 는 사용자 흐름상 흔하므로 조용히 처리
      if (event.error !== 'no-speech' && event.error !== 'aborted') {
        setError(event.error)
      }
      setListening(false)
    }
    recognition.onend = () => {
      setListening(false)
      setInterim('')
    }

    recognitionRef.current = recognition
    return () => {
      recognition.onresult = null
      recognition.onerror = null
      recognition.onend = null
      recognition.onstart = null
      try {
        recognition.abort()
      } catch {
        /* noop */
      }
      recognitionRef.current = null
    }
  }, [Ctor, lang])

  const start = useCallback(() => {
    const recognition = recognitionRef.current
    if (!recognition || listening) return
    setTranscript('')
    setInterim('')
    try {
      recognition.start()
    } catch {
      /* 이미 시작된 경우 무시 */
    }
  }, [listening])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  const reset = useCallback(() => {
    setTranscript('')
    setInterim('')
    setError(null)
  }, [])

  return { supported, listening, transcript, interim, error, start, stop, reset }
}
