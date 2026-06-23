import { useEffect, useRef, useState } from 'react'
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition'
import { cn } from '@/lib/cn'

interface MicButtonProps {
  disabled?: boolean
  /** 인식/입력된 발화 텍스트 전달 */
  onResult: (text: string) => void
  /** 마이크 청취 상태 변화 (아바타 listening 연동) */
  onListeningChange?: (listening: boolean) => void
}

/**
 * 음성 입력 버튼 (FR-002).
 * - 누르면 청취 시작, 다시 누르면 종료 후 인식 결과 전달.
 * - STT 미지원/실패 시 텍스트 입력으로 대체 (NFR-006 마우스만으로 사용 가능).
 */
export function MicButton({ disabled, onResult, onListeningChange }: MicButtonProps) {
  const { supported, listening, transcript, interim, error, start, stop, reset } =
    useSpeechRecognition('ko-KR')

  const [typing, setTyping] = useState(false)
  const [draft, setDraft] = useState('')
  const submittedRef = useRef(false)

  // 청취 상태를 부모(아바타)에 알림
  useEffect(() => {
    onListeningChange?.(listening)
  }, [listening, onListeningChange])

  // 인식이 끝나고(transcript 확정) 청취가 멈추면 결과 제출
  useEffect(() => {
    if (!listening && transcript && !submittedRef.current) {
      submittedRef.current = true
      onResult(transcript.trim())
      reset()
    }
  }, [listening, transcript, onResult, reset])

  // STT 오류 시 자동으로 텍스트 입력 모드로 전환
  useEffect(() => {
    if (error) setTyping(true)
  }, [error])

  const handleMicClick = () => {
    if (disabled) return
    if (listening) {
      stop()
    } else {
      submittedRef.current = false
      start()
    }
  }

  const submitDraft = () => {
    const text = draft.trim()
    if (!text) return
    onResult(text)
    setDraft('')
  }

  // 텍스트 입력 대체 UI
  if (!supported || typing) {
    return (
      <div className="w-full max-w-xl mx-auto flex flex-col items-center gap-3">
        <form
          className="w-full flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            submitDraft()
          }}
        >
          <input
            autoFocus
            value={draft}
            disabled={disabled}
            onChange={(e) => setDraft(e.target.value)}
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
            ? 'bg-brand-100 text-brand-300 cursor-not-allowed'
            : listening
              ? 'bg-emotion-frustrated text-white'
              : 'bg-brand-500 text-white hover:bg-brand-600',
        )}
      >
        {listening && !disabled && (
          <span className="absolute inset-0 rounded-full bg-emotion-frustrated/50 animate-pulse-ring" />
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
