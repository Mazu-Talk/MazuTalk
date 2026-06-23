import type { ConversationTurn } from '@/types/domain'
import { EMOTION_META } from '@/constants/labels'
import { cn } from '@/lib/cn'

interface ChatBubbleProps {
  turn: ConversationTurn
  aiName?: string
}

/** 대화 말풍선 — 아동(오른쪽) / AI(왼쪽) */
export function ChatBubble({ turn, aiName = '미래' }: ChatBubbleProps) {
  const isChild = turn.speaker === 'child'
  const emotion = EMOTION_META[turn.emotion]

  return (
    <div className={cn('flex w-full animate-pop-in', isChild ? 'justify-end' : 'justify-start')}>
      <div className={cn('flex max-w-[80%] items-end gap-2', isChild && 'flex-row-reverse')}>
        {!isChild && (
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-200 text-lg">
            🙂
          </div>
        )}
        <div>
          <div
            className={cn(
              'rounded-3xl px-5 py-3 text-lg leading-relaxed shadow-card',
              isChild
                ? 'rounded-br-md bg-brand-500 text-white'
                : 'rounded-bl-md bg-white text-brand-800',
            )}
          >
            {turn.text || <span className="opacity-60">…</span>}
          </div>
          <div
            className={cn(
              'mt-1 flex items-center gap-1 px-1 text-xs text-brand-500',
              isChild ? 'justify-end' : 'justify-start',
            )}
          >
            <span>{isChild ? '나' : aiName}</span>
            {isChild && turn.text && (
              <span title={`감지된 감정: ${emotion.label}`}>
                · {emotion.emoji} {emotion.label}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
