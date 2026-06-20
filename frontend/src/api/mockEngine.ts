/**
 * Mock Role-play 엔진.
 *
 * 백엔드(STT → 감정분석 → LLM → Safety → TTS)가 아직 없으므로,
 * RP_system_prompt.md 의 원칙(짧고 따뜻한 또래 말투, 시도 강화, 긍정 코칭)을
 * 규칙 기반으로 흉내 내어 UI 흐름 전체를 단독으로 시연할 수 있게 한다.
 *
 * 백엔드가 준비되면 websocket.ts 의 USE_MOCK 플래그만 끄면 된다.
 */
import type { AvatarState, Emotion, Scenario } from '@/types/domain'
import type { ConversationTurn } from '@/types/domain'

export interface MockTurnInput {
  scenario: Scenario
  childText: string
  responseTimeMs: number
  history: ConversationTurn[]
}

export interface MockTurnOutput {
  text: string
  emotion: Emotion
  avatarState: AvatarState
  /** 이 턴 이후 세션을 부드럽게 마무리하면 좋다는 신호 (RP 프롬프트 §16) */
  shouldClose: boolean
}

/** STT 결과/응답 지연을 바탕으로 아동 감정을 추정 (FD-03, ARCHITECTURE §5.4) */
export function detectEmotion(text: string, responseTimeMs: number): Emotion {
  const t = text.trim()
  if (t.length === 0) return 'passive'

  const lower = t.toLowerCase()
  const has = (...words: string[]) => words.some((w) => lower.includes(w))

  if (has('몰라', '모르겠', '뭐', '어떻게')) return 'confused'
  if (has('싫어', '안해', '안 해', '하지마', '저리', '비켜')) return 'frustrated'
  if (has('무서', '떨려', '못하겠', '불안')) return 'anxious'
  if (has('좋아', '응', '네', '그래', '하자', '재밌', '신나', '놀자')) return 'happy'

  // 발화가 매우 짧거나 응답이 오래 걸리면 소극/긴장 신호
  if (t.length <= 2) return responseTimeMs > 4000 ? 'anxious' : 'shy'
  if (responseTimeMs > 6000) return 'anxious'

  return 'neutral'
}

/** 감정 → 아바타 표정 매핑 */
function emotionToAvatar(emotion: Emotion): AvatarState {
  switch (emotion) {
    case 'happy':
      return 'happy'
    case 'confused':
      return 'confused'
    case 'anxious':
    case 'frustrated':
      return 'encouraging'
    case 'shy':
    case 'passive':
      return 'encouraging'
    default:
      return 'speaking'
  }
}

/** 시나리오별 단계 응답 뱅크 — 턴이 진행될수록 다음 단계로 확장 */
const SKILL_FLOW: Record<string, string[]> = {
  greeting: [
    '안녕! 먼저 인사해줘서 고마워. 너 이름은 뭐야?',
    '반가워! 우리 같이 미끄럼틀 탈래?',
    '좋아! 너랑 노니까 정말 즐거워.',
  ],
  emotion_expression: [
    '그렇구나, 말해줘서 고마워. 왜 그런 기분이 들었어?',
    '아하, 그래서 그랬구나. 나도 네 마음 알 것 같아.',
    '네 기분을 말해줘서 정말 멋져!',
  ],
  requesting_help: [
    '어려울 땐 "도와줄래?" 라고 말해도 괜찮아. 한번 말해볼까?',
    '좋아! 내가 같이 도와줄게. 이렇게 끼우면 돼.',
    '우와, 우리 같이 하니까 금방 했다! 잘했어.',
  ],
  conflict_resolution: [
    '같이 쓰고 싶구나. 이렇게 말해볼까? "끝나면 나도 써도 돼?"',
    '그렇게 말해줘서 고마워. 그럼 조금만 기다려줄래?',
    '순서를 잘 지켰어! 이제 네 차례야. 자, 여기 있어.',
  ],
  joining_play: [
    '같이 놀고 싶구나! "나도 같이 놀아도 돼?" 라고 말해볼까?',
    '당연하지! 같이 술래잡기 하자. 네가 먼저 도망가도 돼.',
    '너랑 같이 노니까 더 재밌다!',
  ],
  goodbye: [
    '오늘 즐거웠어! 헤어질 땐 "잘 가" 라고 말해볼까?',
    '응, 잘 가! 다음에 또 만나자.',
    '또 놀자고 말해줘서 고마워. 안녕!',
  ],
}

const FALLBACK_FLOW = [
  '천천히 말해도 괜찮아. 한 번 더 같이 해볼까?',
  '좋아, 잘하고 있어. 조금만 더 이야기해보자.',
  '오늘 정말 잘했어. 같이 말해줘서 고마워.',
]

/** 감정 상태에 맞춘 도입 위로 문장 (RP 프롬프트 §9) */
function emotionPrefix(emotion: Emotion): string {
  switch (emotion) {
    case 'anxious':
      return '괜찮아. 천천히 해도 돼. '
    case 'frustrated':
      return '속상했구나. 잠깐 쉬어도 괜찮아. '
    case 'confused':
      return '어렵지? 쉽게 다시 해보자. '
    case 'shy':
      return '작게 말해도 괜찮아. '
    case 'passive':
      return '괜찮아, 고개를 끄덕여도 돼. '
    default:
      return ''
  }
}

/** 아동 입력에 대한 AI 응답을 생성한다. */
export function generateMockTurn(input: MockTurnInput): MockTurnOutput {
  const { scenario, childText, responseTimeMs, history } = input
  const emotion = detectEmotion(childText, responseTimeMs)

  // 지금까지 등장한 AI 턴 수로 진행 단계를 가늠
  const aiTurns = history.filter((t) => t.speaker === 'ai').length
  const flow = SKILL_FLOW[scenario.target_skill] ?? FALLBACK_FLOW
  const stage = Math.min(aiTurns, flow.length - 1)

  const prefix = emotionPrefix(emotion)
  const body = flow[stage]
  const text = (prefix + body).trim()

  // 흐름의 마지막 단계에 도달했거나 충분히 대화했으면 마무리 제안
  const childTurns = history.filter((t) => t.speaker === 'child').length + 1
  const shouldClose = stage >= flow.length - 1 || childTurns >= 6

  return {
    text,
    emotion,
    avatarState: emotionToAvatar(emotion),
    shouldClose,
  }
}
