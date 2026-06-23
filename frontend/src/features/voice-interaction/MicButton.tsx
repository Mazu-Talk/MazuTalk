import { useEffect, useMemo, useRef, useState } from 'react'
import { USE_MOCK } from '@/api/config'
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition'
import { cn } from '@/lib/cn'

export type MicResult =
  | { kind: 'text'; text: string }
  | { kind: 'audio'; audio: Blob; durationSeconds: number }

interface MicButtonProps {
  disabled?: boolean
  onResult: (result: MicResult) => void
  onListeningChange?: (listening: boolean) => void
}

export function MicButton({ disabled, onResult, onListeningChange }: MicButtonProps) {
  const speech = useSpeechRecognition('ko-KR')
  const [recording, setRecording] = useState(false)
  const [typing, setTyping] = useState(false)
  const [draft, setDraft] = useState('')
  const [recorderError, setRecorderError] = useState<string | null>(null)
  const submittedRef = useRef(false)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startedAtRef = useRef(0)

  const mediaRecorderSupported =
    typeof navigator !== 'undefined' &&
    Boolean(navigator.mediaDevices?.getUserMedia) &&
    typeof MediaRecorder !== 'undefined'
  const supported = USE_MOCK ? speech.supported : mediaRecorderSupported
  const listening = USE_MOCK ? speech.listening : recording
  const interim = USE_MOCK ? speech.interim : ''
  const error = USE_MOCK ? speech.error : recorderError

  const preferredMimeType = useMemo(() => {
    if (typeof MediaRecorder === 'undefined') return undefined
    return ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'].find(
      (type) => MediaRecorder.isTypeSupported(type),
    )
  }, [])

  useEffect(() => {
    onListeningChange?.(listening)
  }, [listening, onListeningChange])

  useEffect(() => {
    if (
      USE_MOCK &&
      !speech.listening &&
      speech.transcript &&
      !submittedRef.current
    ) {
      submittedRef.current = true
      onResult({ kind: 'text', text: speech.transcript.trim() })
      speech.reset()
    }
  }, [onResult, speech])

  useEffect(() => {
    if (error) setTyping(true)
  }, [error])

  useEffect(() => {
    return () => {
      const recorder = recorderRef.current
      if (recorder?.state === 'recording') recorder.stop()
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  const startBackendRecording = async () => {
    try {
      setRecorderError(null)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const recorder = preferredMimeType
        ? new MediaRecorder(stream, { mimeType: preferredMimeType })
        : new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onerror = () => {
        setRecorderError('microphone-recording-failed')
        setRecording(false)
      }
      recorder.onstop = () => {
        const durationSeconds = Math.max((Date.now() - startedAtRef.current) / 1000, 0.1)
        const audio = new Blob(chunksRef.current, {
          type: recorder.mimeType || preferredMimeType || 'audio/webm',
        })
        stream.getTracks().forEach((track) => track.stop())
        streamRef.current = null
        recorderRef.current = null
        setRecording(false)
        if (audio.size > 0) onResult({ kind: 'audio', audio, durationSeconds })
        else setRecorderError('empty-recording')
      }
      startedAtRef.current = Date.now()
      recorder.start(250)
      setRecording(true)
    } catch {
      setRecorderError('microphone-permission-denied')
      setTyping(true)
    }
  }

  const handleMicClick = () => {
    if (disabled) return
    if (USE_MOCK) {
      if (speech.listening) speech.stop()
      else {
        submittedRef.current = false
        speech.start()
      }
      return
    }

    if (recording) recorderRef.current?.stop()
    else void startBackendRecording()
  }

  const submitDraft = () => {
    const text = draft.trim()
    if (!text) return
    onResult({ kind: 'text', text })
    setDraft('')
  }

  if (!supported || typing) {
    return (
      <div className="mx-auto flex w-full max-w-xl flex-col items-center gap-3">
        <form
          className="flex w-full gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            submitDraft()
          }}
        >
          <input
            autoFocus
            value={draft}
            disabled={disabled}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="여기에 말을 적어줘"
            className="flex-1 rounded-2xl border-2 border-brand-200 bg-white px-5 py-4 text-xl text-brand-800 placeholder:text-brand-300 focus:border-brand-400 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={disabled || !draft.trim()}
            className="rounded-2xl bg-brand-500 px-6 py-4 text-xl font-bold text-white shadow-soft active:scale-95 disabled:opacity-40"
          >
            말하기
          </button>
        </form>
        {supported && (
          <button
            onClick={() => setTyping(false)}
            className="text-base text-brand-500 underline underline-offset-4"
          >
            🎤 목소리로 말할래요
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        onClick={handleMicClick}
        disabled={disabled}
        aria-pressed={listening}
        aria-label={listening ? '말하기 끝내기' : '마이크 켜고 말하기'}
        className={cn(
          'relative grid place-items-center rounded-full transition-all duration-150',
          'h-28 w-28 text-5xl shadow-soft active:scale-90 focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-300',
          disabled
            ? 'cursor-not-allowed bg-brand-100 text-brand-300'
            : listening
              ? 'bg-emotion-frustrated text-white'
              : 'bg-brand-500 text-white hover:bg-brand-600',
        )}
      >
        {listening && !disabled && (
          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-emotion-frustrated/50" />
        )}
        <span aria-hidden>{listening ? '⏹️' : '🎤'}</span>
      </button>
      <p className="h-7 text-lg text-brand-600">
        {disabled
          ? '잠깐 기다려줘'
          : listening
            ? interim || '듣고 있어...'
            : '버튼을 누르고 말해봐'}
      </p>
      {!listening && !disabled && (
        <button
          onClick={() => setTyping(true)}
          className="text-base text-brand-500 underline underline-offset-4"
        >
          ⌨️ 글로 쓸래요
        </button>
      )}
    </div>
  )
}
