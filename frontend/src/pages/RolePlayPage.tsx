import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/stores/appStore'
import { useSessionStore } from '@/stores/sessionStore'
import { useTextToSpeech } from '@/hooks/useTextToSpeech'
import { Avatar } from '@/features/voice-interaction/Avatar'
import { MicButton } from '@/features/voice-interaction/MicButton'
import { ChatBubble } from '@/features/chatbot/ChatBubble'
import { Button } from '@/components/common/Button'
import { Modal } from '@/components/common/Modal'

export function RolePlayPage() {
  const navigate = useAppStore((s) => s.navigate)
  const {
    scenario,
    turns,
    phase,
    avatarState,
    suggestEnd,
    error,
    setListening,
    submitChildUtterance,
    notifySpeakingDone,
    endSession,
  } = useSessionStore()

  const { speak, cancel } = useTextToSpeech('ko-KR')

  const [showHistory, setShowHistory] = useState(false)
  const [showEndModal, setShowEndModal] = useState(false)

  const readyAtRef = useRef<number>(Date.now())
  const lastSpokenTurnRef = useRef<number>(-1)
  const scrollRef = useRef<HTMLDivElement>(null)

  // 시나리오 없이 직접 진입하면 선택 화면으로
  useEffect(() => {
    if (!scenario) navigate('scenario-select')
  }, [scenario, navigate])

  // 새 AI 턴이 등장하면 음성으로 읽어준다 (audio_url 있으면 그것을, 없으면 브라우저 TTS).
  useEffect(() => {
    const lastAi = [...turns].reverse().find((t) => t.speaker === 'ai')
    if (!lastAi || lastAi.turn_id === lastSpokenTurnRef.current) return
    lastSpokenTurnRef.current = lastAi.turn_id

    const onEnd = () => {
      notifySpeakingDone()
      readyAtRef.current = Date.now() // 아동 응답 시간 측정 시작점
    }

    if (lastAi.audio_url) {
      const audio = new Audio(lastAi.audio_url)
      audio.onended = onEnd
      audio.onerror = onEnd
      void audio.play().catch(onEnd)
    } else {
      speak(lastAi.text, { onEnd })
    }
  }, [turns, speak, notifySpeakingDone])

  // 새 메시지로 스크롤
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns, showHistory])

  const handleResult = useCallback(
    (text: string) => {
      const ms = Date.now() - readyAtRef.current
      submitChildUtterance(text, ms)
    },
    [submitChildUtterance],
  )

  const handleEnd = useCallback(async () => {
    cancel()
    setShowEndModal(false)
    await endSession('completed')
    navigate('report')
  }, [cancel, endSession, navigate])

  if (!scenario) return null

  const micDisabled = phase !== 'idle'

  return (
    <div className="flex min-h-full flex-col">
      {/* 상단 바 */}
      <header className="flex items-center justify-between px-4 py-3 sm:px-8">
        <Button
          variant="ghost"
          size="md"
          icon="✕"
          onClick={() => setShowEndModal(true)}
        >
          그만하기
        </Button>
        <div className="text-center">
          <p className="text-xs text-brand-400">{scenario.location}</p>
          <h1 className="text-lg font-bold text-brand-700">
            {scenario.emoji} {scenario.title}
          </h1>
        </div>
        <Button
          variant="ghost"
          size="md"
          icon="💬"
          onClick={() => setShowHistory((v) => !v)}
          aria-pressed={showHistory}
        >
          대화
        </Button>
      </header>

      {/* 본문: 아바타 또는 대화 기록 */}
      <div className="relative flex flex-1 flex-col items-center justify-center px-4">
        {showHistory ? (
          <div
            ref={scrollRef}
            className="flex w-full max-w-2xl flex-1 flex-col gap-3 overflow-y-auto py-4"
          >
            {turns.map((turn) => (
              <ChatBubble key={`${turn.speaker}-${turn.turn_id}`} turn={turn} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-6 py-4">
            <Avatar state={avatarState} name="미래" size={260} />

            {/* 가장 최근 AI 말풍선 미리보기 */}
            <LatestAiLine />
          </div>
        )}

        {error && (
          <div className="absolute bottom-2 rounded-2xl bg-emotion-frustrated/15 px-4 py-2 text-base text-brand-700">
            {error} 다시 한 번 말해줄래?
          </div>
        )}
      </div>

      {/* 하단: 마이크 입력 영역 */}
      <footer className="sticky bottom-0 flex flex-col items-center gap-3 px-4 pb-6 pt-3">
        {suggestEnd && phase === 'idle' && (
          <button
            onClick={() => setShowEndModal(true)}
            className="animate-pop-in rounded-full bg-emotion-happy/40 px-5 py-2 text-base font-semibold text-brand-700"
          >
            🌟 오늘 연습을 마치고 결과를 볼까요?
          </button>
        )}
        <MicButton
          disabled={micDisabled}
          onResult={handleResult}
          onListeningChange={setListening}
        />
      </footer>

      <Modal
        open={showEndModal}
        title="연습을 마칠까요?"
        confirmLabel="결과 보기"
        cancelLabel="더 할래요"
        onConfirm={handleEnd}
        onCancel={() => setShowEndModal(false)}
      >
        지금까지 한 대화로 학습 결과를 만들어 드려요.
      </Modal>
    </div>
  )
}

/** 아바타 화면일 때 가장 최근 AI 발화를 텍스트로도 보여준다 (FR-007 보조). */
function LatestAiLine() {
  const lastAiText = useSessionStore((s) => {
    const ai = [...s.turns].reverse().find((t) => t.speaker === 'ai')
    return ai?.text ?? ''
  })
  if (!lastAiText) return null
  return (
    <div className="max-w-xl animate-pop-in rounded-3xl bg-white/90 px-6 py-4 text-center text-xl leading-relaxed text-brand-800 shadow-card">
      {lastAiText}
    </div>
  )
}
