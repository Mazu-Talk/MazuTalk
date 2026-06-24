// 모듈 4 — Learning Report 분석/생성 검증 (buildReport).
// 상호작용 로그(turns) + 시선 로그(gazeLog) → 참여도/감정추이/우세감정/정면집중도.
import { describe, it, expect } from 'vitest'
import { buildReport } from '@/lib/report'
import { SAMPLE_SESSION, SAMPLE_TURNS, SAMPLE_GAZE } from './fixtures'

describe('Learning Report 모듈 (buildReport)', () => {
  it('상호작용 데이터로 리포트 핵심 지표를 생성한다', () => {
    const report = buildReport(SAMPLE_SESSION, SAMPLE_TURNS, '2026-01-01T00:01:00.000Z', SAMPLE_GAZE)

    // 대화 지속성
    expect(report.total_turns).toBe(SAMPLE_TURNS.length)
    expect(report.session_id).toBe(SAMPLE_SESSION.session_id)
    expect(report.scenario_id).toBe(SAMPLE_SESSION.scenario_id)

    // 감정 변화: 아동 턴만, 순서대로
    expect(report.emotion_timeline.map((p) => p.emotion)).toEqual(['happy', 'happy', 'confused'])
    expect(report.dominant_emotion).toBe('happy')

    // 반응 속도 / 발화 길이
    expect(report.avg_response_time_ms).toBeGreaterThan(0)
    expect(report.avg_utterance_length).toBeGreaterThan(0)

    // 참여도 (0~100)
    expect(report.participation_score).toBeGreaterThanOrEqual(0)
    expect(report.participation_score).toBeLessThanOrEqual(100)

    // 시나리오 수행 결과
    expect(report.completion_status).toBe('completed')
  })

  it('시선/홍채 특징 → 정면 집중도(gaze_summary)를 계산한다', () => {
    const report = buildReport(SAMPLE_SESSION, SAMPLE_TURNS, '2026-01-01T00:01:00.000Z', SAMPLE_GAZE)
    expect(report.gaze_summary).toBeDefined()
    expect(report.gaze_summary!.center).toBe(67) // 4/6
    expect(report.gaze_summary!.left).toBe(17) // 1/6
    expect(report.gaze_summary!.right).toBe(17) // 1/6
  })

  it('시선 데이터가 없으면 gaze_summary 는 undefined', () => {
    const report = buildReport(SAMPLE_SESSION, SAMPLE_TURNS, '2026-01-01T00:01:00.000Z', [])
    expect(report.gaze_summary).toBeUndefined()
  })

  it('아동 발화가 없으면 참여도 0, 우세감정 neutral', () => {
    const aiOnly = SAMPLE_TURNS.filter((t) => t.speaker === 'ai')
    const report = buildReport(SAMPLE_SESSION, aiOnly, '2026-01-01T00:01:00.000Z', [])
    expect(report.participation_score).toBe(0)
    expect(report.dominant_emotion).toBe('neutral')
    expect(report.emotion_timeline).toEqual([])
  })

  it('중단된 세션은 completion_status=interrupted', () => {
    const report = buildReport(
      { ...SAMPLE_SESSION, status: 'interrupted' },
      SAMPLE_TURNS,
      '2026-01-01T00:01:00.000Z',
      SAMPLE_GAZE,
    )
    expect(report.completion_status).toBe('interrupted')
  })
})
