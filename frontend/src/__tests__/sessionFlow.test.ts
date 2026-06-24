// E2E — 클라이언트 오케스트레이션 (USE_MOCK=true, MockConnection).
// 세션 시작 → 시나리오 → 발화 입력 → (mock STT/LLM) 응답 이벤트 → 턴 갱신
// → 비전(시선/표정) 수집 → 세션 종료 → 리포트 생성 → 다음 시나리오.
//
// MOCK 처리: STT/LLM/TTS 는 api/mockEngine + api/websocket 의 MockConnection 으로 대체.
//            (백엔드 연결 시 USE_MOCK=false 로 동일 인터페이스 사용)
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useSessionStore } from '@/stores/sessionStore'
import { SCENARIO_GREETING, SCENARIO_NEXT } from './fixtures'

beforeEach(() => {
  useSessionStore.getState().reset()
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
})

describe('세션 오케스트레이션 E2E (mock)', () => {
  it('세션 시작 → 발화 → 응답 → 비전수집 → 리포트 → 다음 시나리오', async () => {
    const store = useSessionStore

    // 1) 세션 시작 + 시나리오 로드 → 오프닝 AI 턴
    await store.getState().startSession(SCENARIO_GREETING)
    let s = store.getState()
    expect(s.session).not.toBeNull()
    expect(s.scenario?.scenario_id).toBe('playground_greeting')
    expect(s.turns).toHaveLength(1)
    expect(s.turns[0].speaker).toBe('ai')
    expect(s.phase).toBe('speaking')

    // AI 오프닝 음성 재생 종료 처리
    store.getState().notifySpeakingDone()

    // 2) 비전 모듈 산출물 수집 (표정/시선)
    store.getState().setFacialEmotion('happy')
    store.getState().addEmotionSample({ label: 'happy', confidence: 0.9, timestamp: 1 })
    for (const dir of ['center', 'center', 'center', 'center', 'left', 'right'] as const) {
      store.getState().addGazeSample({ direction: dir, irisPos: 0.5, timestamp: 1 })
    }

    // 3) 아동 발화 입력 → 즉시 child 턴 추가 + thinking
    store.getState().submitChildUtterance({ text: '좋아 같이 놀자' }, 1000)
    s = store.getState()
    const childTurn = s.turns.find((t) => t.speaker === 'child')
    expect(childTurn).toBeDefined()
    expect(s.phase).toBe('thinking')

    // 4) mock STT/LLM 이벤트 처리 (setTimeout 기반) → AI 응답 턴 등장
    await vi.advanceTimersByTimeAsync(2000)
    s = store.getState()
    const aiTurns = s.turns.filter((t) => t.speaker === 'ai')
    expect(aiTurns.length).toBeGreaterThanOrEqual(2) // 오프닝 + 응답
    const lastAi = aiTurns[aiTurns.length - 1]
    expect(lastAi.text.length).toBeGreaterThan(0) // 응답 텍스트 생성
    expect(s.currentEmotion).toBe('happy') // 감정 융합 결과 반영
    // 아동 턴 감정이 감지값으로 갱신됨
    expect(s.turns.find((t) => t.speaker === 'child')!.emotion).toBe('happy')
    expect(s.phase).toBe('speaking')

    store.getState().notifySpeakingDone()
    expect(store.getState().phase).toBe('idle')

    // 5) 세션 종료 → 리포트 생성 (상호작용 로그 + 시선/감정 분석)
    await store.getState().endSession('completed')
    s = store.getState()
    expect(s.phase).toBe('ended')
    expect(s.report).not.toBeNull()
    const report = s.report!
    expect(report.total_turns).toBe(s.turns.length)
    expect(report.emotion_timeline.length).toBeGreaterThanOrEqual(1)
    expect(report.gaze_summary).toBeDefined()
    expect(report.gaze_summary!.center).toBe(67) // 4/6 정면
    expect(report.completion_status).toBe('completed')

    // 6) 다음 시나리오 진행 → 상태 초기화 후 새 세션
    store.getState().reset()
    await store.getState().startSession(SCENARIO_NEXT)
    s = store.getState()
    expect(s.scenario?.scenario_id).toBe('classroom_emotion')
    expect(s.report).toBeNull()
    expect(s.gazeLog).toHaveLength(0) // 비전 로그 초기화
    expect(s.turns).toHaveLength(1) // 새 오프닝만
  })

  it('빈 발화 입력은 에러 이벤트로 처리되고 AI 응답이 생성되지 않는다 (엣지)', async () => {
    const store = useSessionStore
    await store.getState().startSession(SCENARIO_GREETING)
    // 빈 텍스트(인식 실패/무발화) → 백엔드·mock 모두 error 이벤트로 처리되는 계약
    store.getState().submitChildUtterance({ text: '' }, 500)
    await vi.advanceTimersByTimeAsync(2000)
    const s = store.getState()
    expect(s.error).toBeTruthy()
    expect(s.phase).toBe('idle')
    // 오프닝 AI 턴만, AI 응답 턴은 추가되지 않음
    expect(s.turns.filter((t) => t.speaker === 'ai')).toHaveLength(1)
  })
})
