// E2E(프론트) 테스트용 결정론적 fixture.
import type { ConversationTurn, GazeSample, Scenario, Session } from '@/types/domain'
import { SCENARIOS } from '@/data/scenarios'

export const SCENARIO_GREETING: Scenario = SCENARIOS.find((s) => s.scenario_id === 'playground_greeting')!
export const SCENARIO_NEXT: Scenario = SCENARIOS.find((s) => s.scenario_id === 'classroom_emotion')!

export const SAMPLE_SESSION: Session = {
  session_id: 'session_test01',
  child_id: 'child-001',
  scenario_id: 'playground_greeting',
  started_at: '2026-01-01T00:00:00.000Z',
  status: 'completed',
}

function child(turn_id: number, text: string, emotion: ConversationTurn['emotion'], rt = 1000): ConversationTurn {
  return {
    turn_id,
    session_id: SAMPLE_SESSION.session_id,
    speaker: 'child',
    text,
    emotion,
    response_time_ms: rt,
    created_at: '2026-01-01T00:00:01.000Z',
  }
}
function ai(turn_id: number, text: string): ConversationTurn {
  return {
    turn_id,
    session_id: SAMPLE_SESSION.session_id,
    speaker: 'ai',
    text,
    emotion: 'happy',
    response_time_ms: 0,
    created_at: '2026-01-01T00:00:02.000Z',
  }
}

// AI 오프닝 + (아동/AI) 3턴. 아동 감정: happy, happy, confused → dominant=happy
export const SAMPLE_TURNS: ConversationTurn[] = [
  ai(1, '안녕! 나는 미래야. 너도 같이 놀래?'),
  child(2, '좋아 같이 놀자', 'happy'),
  ai(3, '반가워! 우리 같이 미끄럼틀 탈래?'),
  child(4, '응 좋아', 'happy'),
  ai(5, '좋아! 너랑 노니까 정말 즐거워.'),
  child(6, '이거 어떻게 하는지 몰라', 'confused', 3000),
]

// 시선 샘플 6개: center 4 / left 1 / right 1 → center 67%
export const SAMPLE_GAZE: GazeSample[] = [
  { direction: 'center', irisPos: 0.5, timestamp: 1 },
  { direction: 'center', irisPos: 0.51, timestamp: 2 },
  { direction: 'center', irisPos: 0.49, timestamp: 3 },
  { direction: 'center', irisPos: 0.5, timestamp: 4 },
  { direction: 'left', irisPos: 0.7, timestamp: 5 },
  { direction: 'right', irisPos: 0.3, timestamp: 6 },
]
