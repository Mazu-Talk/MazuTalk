import type {
  ConversationTurn,
  Emotion,
  EmotionPoint,
  GazeSample,
  GazeSummary,
  Report,
  Session,
} from '@/types/domain'
import { uid } from '@/api/config'

/**
 * 세션 대화 로그로부터 학습 리포트를 계산한다.
 * 산식 출처: FD-07 / ARCHITECTURE §5.9, §7.4
 */
export function buildReport(
  session: Session,
  turns: ConversationTurn[],
  nowIso: string,
  gazeLog: GazeSample[] = [],
): Report {
  const childTurns = turns.filter((t) => t.speaker === 'child')

  const total_turns = turns.length

  const avg_response_time_ms =
    childTurns.length > 0
      ? Math.round(
          childTurns.reduce((sum, t) => sum + t.response_time_ms, 0) /
            childTurns.length,
        )
      : 0

  const avg_utterance_length =
    childTurns.length > 0
      ? Math.round(
          (childTurns.reduce((sum, t) => sum + t.text.trim().length, 0) /
            childTurns.length) *
            10,
        ) / 10
      : 0

  const emotion_timeline: EmotionPoint[] = childTurns.map((t) => ({
    turn_id: t.turn_id,
    emotion: t.emotion,
  }))

  const dominant_emotion = mostFrequentEmotion(childTurns.map((t) => t.emotion))

  return {
    report_id: uid('report'),
    session_id: session.session_id,
    scenario_id: session.scenario_id,
    total_turns,
    avg_response_time_ms,
    avg_utterance_length,
    emotion_timeline,
    dominant_emotion,
    participation_score: computeParticipationScore(childTurns),
    completion_status: session.status === 'completed' ? 'completed' : 'interrupted',
    created_at: nowIso,
    gaze_summary: computeGazeSummary(gazeLog),
  }
}

/** 시선 로그 → 정면/좌/우 비율(%) 요약. 데이터가 없으면 undefined. */
function computeGazeSummary(gazeLog: GazeSample[]): GazeSummary | undefined {
  const total = gazeLog.length
  if (total === 0) return undefined
  const ratio = (dir: GazeSample['direction']) =>
    Math.round((gazeLog.filter((g) => g.direction === dir).length / total) * 100)
  return { center: ratio('center'), left: ratio('left'), right: ratio('right') }
}

function mostFrequentEmotion(emotions: Emotion[]): Emotion {
  if (emotions.length === 0) return 'neutral'
  const counts = new Map<Emotion, number>()
  for (const e of emotions) counts.set(e, (counts.get(e) ?? 0) + 1)
  let best: Emotion = emotions[0]
  let bestN = 0
  for (const [e, n] of counts) {
    if (n > bestN) {
      best = e
      bestN = n
    }
  }
  return best
}

/**
 * 참여도 점수 (0~100).
 * - 대화 횟수(많을수록 +)
 * - 평균 발화 길이(길수록 +)
 * - 긍정/중립 감정 비율(높을수록 +)
 * - 무응답(빈 발화) 비율(높을수록 -)
 */
function computeParticipationScore(childTurns: ConversationTurn[]): number {
  if (childTurns.length === 0) return 0

  const turnScore = Math.min(childTurns.length / 8, 1) * 40 // 최대 40

  const avgLen =
    childTurns.reduce((s, t) => s + t.text.trim().length, 0) / childTurns.length
  const lengthScore = Math.min(avgLen / 12, 1) * 25 // 최대 25

  const positive = childTurns.filter((t) =>
    ['happy', 'neutral'].includes(t.emotion),
  ).length
  const emotionScore = (positive / childTurns.length) * 25 // 최대 25

  const responded = childTurns.filter((t) => t.text.trim().length > 0).length
  const responseScore = (responded / childTurns.length) * 10 // 최대 10

  return Math.round(turnScore + lengthScore + emotionScore + responseScore)
}
