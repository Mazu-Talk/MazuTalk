import type { AvatarState } from '@/types/domain'
import { cn } from '@/lib/cn'

interface AvatarProps {
  state: AvatarState
  /** 캐릭터 이름 (시나리오 ai_role 기반) */
  name?: string
  size?: number
}

const STATE_LABEL: Record<AvatarState, string> = {
  idle: '네 차례야',
  listening: '듣고 있어',
  thinking: '생각 중...',
  speaking: '말하는 중',
  happy: '기뻐요',
  confused: '음?',
  encouraging: '괜찮아!',
  sad: '속상해',
}

const FACE_BG: Record<AvatarState, string> = {
  idle: '#d9ecff',
  listening: '#bcdcff',
  thinking: '#cdb4f6',
  speaking: '#8ec6ff',
  happy: '#ffd166',
  confused: '#cdb4f6',
  encouraging: '#7bd389',
  sad: '#a0c4ff',
}

/**
 * 아동 친화형 표정 아바타.
 * MVP 단계에서는 3D/VRM 대신 SVG 표정 + 상태 전환을 우선 구현한다
 * (ARCHITECTURE §15: "MVP에서는 기본 표정/상태 전환 우선").
 */
export function Avatar({ state, name = '미래', size = 240 }: AvatarProps) {
  const bg = FACE_BG[state]
  const isListening = state === 'listening'
  const isThinking = state === 'thinking'
  const isSpeaking = state === 'speaking'

  return (
    <div className="flex flex-col items-center gap-4 select-none" aria-live="polite">
      <div
        className="relative grid place-items-center"
        style={{ width: size, height: size }}
        role="img"
        aria-label={`${name} 캐릭터, 상태: ${STATE_LABEL[state]}`}
      >
        {/* 듣는 중 펄스 링 */}
        {isListening && (
          <>
            <span className="absolute inset-0 rounded-full bg-brand-300/60 animate-pulse-ring" />
            <span
              className="absolute inset-0 rounded-full bg-brand-300/40 animate-pulse-ring"
              style={{ animationDelay: '0.5s' }}
            />
          </>
        )}

        <svg
          viewBox="0 0 200 200"
          width={size}
          height={size}
          className={cn(
            'relative drop-shadow-xl transition-transform',
            (state === 'idle' || state === 'happy') && 'animate-bounce-soft',
            state === 'encouraging' && 'animate-float',
          )}
        >
          {/* 얼굴 */}
          <circle cx="100" cy="100" r="84" fill={bg} />
          <circle cx="100" cy="100" r="84" fill="none" stroke="#ffffff" strokeWidth="6" opacity="0.5" />

          {/* 볼터치 (긍정 상태) */}
          {(state === 'happy' || state === 'speaking' || state === 'idle') && (
            <>
              <circle cx="58" cy="118" r="11" fill="#ff9aa2" opacity="0.5" />
              <circle cx="142" cy="118" r="11" fill="#ff9aa2" opacity="0.5" />
            </>
          )}

          <Eyes state={state} />
          <Mouth state={state} isSpeaking={isSpeaking} />
        </svg>

        {/* 생각 중 점 3개 */}
        {isThinking && (
          <div className="absolute -top-2 right-6 flex gap-1.5 rounded-full bg-white px-3 py-2 shadow-card">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-2.5 w-2.5 rounded-full bg-brand-400 animate-bounce-soft"
                style={{ animationDelay: `${i * 0.18}s` }}
              />
            ))}
          </div>
        )}
      </div>

      {/* 상태 라벨 + 말하는 중 사운드 웨이브 */}
      <div className="flex items-center gap-3 rounded-full bg-white/80 px-5 py-2 shadow-card">
        <span className="text-xl font-bold text-brand-700">{name}</span>
        <span className="text-brand-300">·</span>
        {isSpeaking ? (
          <SoundWave />
        ) : (
          <span className="text-lg text-brand-600">{STATE_LABEL[state]}</span>
        )}
      </div>
    </div>
  )
}

function Eyes({ state }: { state: AvatarState }) {
  // 기쁨/격려: 호선 눈(^ ^). 혼란: 한쪽만 작게. 슬픔: 처진 눈. 그 외: 동그란 눈.
  if (state === 'happy' || state === 'encouraging') {
    return (
      <g stroke="#1c3e72" strokeWidth="6" strokeLinecap="round" fill="none">
        <path d="M58 86 q12 -16 24 0" />
        <path d="M118 86 q12 -16 24 0" />
      </g>
    )
  }
  if (state === 'confused' || state === 'thinking') {
    return (
      <g fill="#1c3e72">
        <circle cx="70" cy="88" r="9" />
        <circle cx="130" cy="84" r="6" />
        <path d="M118 74 q12 -6 24 0" stroke="#1c3e72" strokeWidth="5" fill="none" strokeLinecap="round" />
      </g>
    )
  }
  if (state === 'sad') {
    return (
      <g fill="#1c3e72">
        <circle cx="70" cy="92" r="9" />
        <circle cx="130" cy="92" r="9" />
        <path d="M58 78 q12 6 24 2" stroke="#1c3e72" strokeWidth="5" fill="none" strokeLinecap="round" />
        <path d="M118 80 q12 -4 24 -2" stroke="#1c3e72" strokeWidth="5" fill="none" strokeLinecap="round" />
      </g>
    )
  }
  // idle / listening / speaking / neutral
  return (
    <g fill="#1c3e72">
      <circle cx="70" cy="88" r="10" />
      <circle cx="130" cy="88" r="10" />
      <circle cx="73" cy="84" r="3" fill="#fff" />
      <circle cx="133" cy="84" r="3" fill="#fff" />
    </g>
  )
}

function Mouth({ state, isSpeaking }: { state: AvatarState; isSpeaking: boolean }) {
  if (isSpeaking) {
    // 말하는 중: 열린 입 (위아래로 살짝 움직이는 애니메이션)
    return (
      <ellipse cx="100" cy="138" rx="20" ry="14" fill="#1c3e72" className="origin-center animate-wave">
        <animate attributeName="ry" values="14;7;14" dur="0.5s" repeatCount="indefinite" />
      </ellipse>
    )
  }
  switch (state) {
    case 'happy':
      return <path d="M72 132 q28 30 56 0" stroke="#1c3e72" strokeWidth="7" fill="none" strokeLinecap="round" />
    case 'encouraging':
      return <path d="M76 134 q24 22 48 0" stroke="#1c3e72" strokeWidth="7" fill="none" strokeLinecap="round" />
    case 'sad':
      return <path d="M76 144 q24 -20 48 0" stroke="#1c3e72" strokeWidth="7" fill="none" strokeLinecap="round" />
    case 'confused':
    case 'thinking':
      return <path d="M80 138 q20 6 40 -2" stroke="#1c3e72" strokeWidth="7" fill="none" strokeLinecap="round" />
    case 'listening':
      return <circle cx="100" cy="138" r="8" fill="#1c3e72" />
    default:
      return <path d="M80 136 q20 14 40 0" stroke="#1c3e72" strokeWidth="7" fill="none" strokeLinecap="round" />
  }
}

function SoundWave() {
  return (
    <span className="flex items-end gap-1 h-6" aria-hidden>
      {[0.1, 0.3, 0.0, 0.25, 0.15].map((delay, i) => (
        <span
          key={i}
          className="w-1.5 rounded-full bg-brand-500 animate-wave"
          style={{ height: '100%', animationDelay: `${delay}s` }}
        />
      ))}
    </span>
  )
}
