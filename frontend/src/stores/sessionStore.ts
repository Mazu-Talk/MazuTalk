import { create } from 'zustand'
import type {
  AvatarState,
  ConversationTurn,
  Difficulty,
  Emotion,
  EmotionSample,
  GazeSample,
  Report,
  Scenario,
  Session,
  VisionEmotion,
} from '@/types/domain'
import type { ServerEvent } from '@/types/ws'
import { createSession, endSession as endSessionApi } from '@/api/client'
import { connectRolePlay, type RolePlayConnection, type UtteranceContent } from '@/api/websocket'
import { buildReport } from '@/lib/report'

/** 대화 세션의 진행 단계 (아바타/마이크 UI가 이 값을 따른다) */
export type SessionPhase =
  | 'idle' // 아동 차례 (마이크 입력 대기)
  | 'listening' // 아동 음성 청취 중
  | 'thinking' // AI 응답 생성 중
  | 'speaking' // AI 음성 재생 중
  | 'ended' // 세션 종료

interface SessionState {
  session: Session | null
  scenario: Scenario | null
  turns: ConversationTurn[]
  phase: SessionPhase
  avatarState: AvatarState
  currentEmotion: Emotion
  difficulty: Difficulty
  /** 충분히 대화하여 마무리를 권하는 신호 (RP 프롬프트 §16) */
  suggestEnd: boolean
  report: Report | null
  error: string | null

  // ── 비전(멀티모달) 상태 ─────────────────────────────
  /** YOLOv8 표정 분류의 현재 우세 감정 (EmotionDetector가 갱신) */
  facialEmotion: VisionEmotion
  /** 표정 감정 로그 (1초 간격 누적) — 리포트/융합에 사용 */
  emotionLog: EmotionSample[]
  /** 시선 로그 (1초 간격 누적) — 리포트 gaze_summary 계산에 사용 */
  gazeLog: GazeSample[]
  /** TTS 재생 볼륨 (0~) — VRM 아바타 립싱크용 */
  lipSyncVolume: number

  // 액션
  startSession: (scenario: Scenario) => Promise<void>
  setListening: (listening: boolean) => void
  submitChildUtterance: (content: UtteranceContent, responseTimeMs: number) => void
  notifySpeakingDone: () => void
  endSession: (status?: 'completed' | 'interrupted') => Promise<void>
  reset: () => void

  // 비전 액션
  setFacialEmotion: (emotion: VisionEmotion) => void
  addEmotionSample: (sample: EmotionSample) => void
  addGazeSample: (sample: GazeSample) => void
  setLipSyncVolume: (volume: number) => void
  resetVision: () => void
}

/** WS/연결 객체는 렌더와 무관하므로 store 바깥(모듈 스코프)에 보관 */
let connection: RolePlayConnection | null = null
let turnCounter = 0

const initial = {
  session: null,
  scenario: null,
  turns: [] as ConversationTurn[],
  phase: 'idle' as SessionPhase,
  avatarState: 'idle' as AvatarState,
  currentEmotion: 'neutral' as Emotion,
  difficulty: 'easy' as Difficulty,
  suggestEnd: false,
  report: null,
  error: null,
  facialEmotion: 'neutral' as VisionEmotion,
  emotionLog: [] as EmotionSample[],
  gazeLog: [] as GazeSample[],
  lipSyncVolume: 0,
}

export const useSessionStore = create<SessionState>((set, get) => {
  /** 서버(또는 mock) 이벤트 처리 — ARCHITECTURE §8.2 */
  const handleServerEvent = (event: ServerEvent) => {
    switch (event.type) {
      case 'stt_result': {
        // 백엔드 STT 경로에서 인식 텍스트를 확정. 브라우저 STT 경로에서는 이미 채워져 있다.
        set((state) => {
          const turns = [...state.turns]
          let childIndex = -1
          for (let index = turns.length - 1; index >= 0; index--) {
            if (turns[index].speaker === 'child') { childIndex = index; break }
          }
          if (childIndex >= 0 && !turns[childIndex].text) {
            turns[childIndex] = { ...turns[childIndex], text: event.payload.text }
          }
          return { turns }
        })
        break
      }
      case 'avatar_state': {
        set({ avatarState: event.payload.avatar_state })
        break
      }
      case 'ai_response': {
        const { text, emotion, avatar_state, audio_url, turn_id } = event.payload
        set((state) => {
          const turns = [...state.turns]
          // 감지된 감정을 직전 아동 턴에 반영
          for (let i = turns.length - 1; i >= 0; i--) {
            if (turns[i].speaker === 'child') {
              turns[i] = { ...turns[i], emotion }
              break
            }
          }
          const aiTurn: ConversationTurn = {
            turn_id,
            session_id: state.session?.session_id ?? '',
            speaker: 'ai',
            text,
            emotion,
            response_time_ms: 0,
            created_at: new Date().toISOString(),
            audio_url: audio_url ?? undefined,
          }
          const childTurnCount = turns.filter((t) => t.speaker === 'child').length
          return {
            turns: [...turns, aiTurn],
            currentEmotion: emotion,
            avatarState: avatar_state,
            phase: 'speaking',
            suggestEnd: childTurnCount >= 6,
          }
        })
        break
      }
      case 'error': {
        set({
          error: event.payload.message,
          phase: 'idle',
          avatarState: 'encouraging',
        })
        break
      }
    }
  }

  return {
    ...initial,

    async startSession(scenario) {
      turnCounter = 0
      const session = await createSession(scenario.scenario_id)
      connection?.close()
      connection = connectRolePlay(session.session_id)
      connection.onEvent(handleServerEvent)

      // 시나리오 오프닝을 첫 AI 턴으로 등록 → 페이지가 TTS로 읽어준다.
      const opening: ConversationTurn = {
        turn_id: ++turnCounter,
        session_id: session.session_id,
        speaker: 'ai',
        text: scenario.opening_message,
        emotion: 'happy',
        response_time_ms: 0,
        created_at: new Date().toISOString(),
      }

      set({
        ...initial,
        session,
        scenario,
        difficulty: scenario.difficulty,
        turns: [opening],
        phase: 'speaking',
        avatarState: 'speaking',
        currentEmotion: 'happy',
      })
    },

    setListening(listening) {
      const { phase } = get()
      if (listening) {
        set({ phase: 'listening', avatarState: 'listening' })
      } else if (phase === 'listening') {
        set({ phase: 'idle', avatarState: 'idle' })
      }
    },

    submitChildUtterance(content, responseTimeMs) {
      const { session, scenario, turns, facialEmotion } = get()
      if (!session || !scenario) return
      const text = content.text?.trim() ?? ''

      const childTurn: ConversationTurn = {
        turn_id: ++turnCounter,
        session_id: session.session_id,
        speaker: 'child',
        text,
        emotion: 'neutral', // ai_response 수신 시 감지값으로 갱신
        response_time_ms: responseTimeMs,
        created_at: new Date().toISOString(),
      }

      const nextTurns = [...turns, childTurn]
      set({ turns: nextTurns, phase: 'thinking', avatarState: 'thinking', error: null })

      connection?.sendUtterance({
        turnId: childTurn.turn_id,
        responseTimeMs,
        scenario,
        history: nextTurns,
        content,
        facialEmotion,
      })
    },

    notifySpeakingDone() {
      // AI 음성 재생이 끝나면 아동 차례로 전환
      if (get().phase === 'speaking') {
        set({ phase: 'idle', avatarState: 'idle' })
      }
    },

    async endSession(status = 'completed') {
      const { session, turns, gazeLog } = get()
      connection?.close()
      connection = null
      if (!session) {
        set({ phase: 'ended' })
        return
      }
      const endedSession: Session = {
        ...session,
        ended_at: new Date().toISOString(),
        status,
      }
      try {
        await endSessionApi(session.session_id, status)
      } catch {
        /* mock 모드 혹은 백엔드 미가동 시 무시 */
      }
      const report = buildReport(endedSession, turns, new Date().toISOString(), gazeLog)
      set({ session: endedSession, report, phase: 'ended', avatarState: 'idle' })
    },

    reset() {
      connection?.close()
      connection = null
      turnCounter = 0
      set({ ...initial })
    },

    // ── 비전 액션 ───────────────────────────────────────
    setFacialEmotion(emotion) {
      set({ facialEmotion: emotion })
    },

    addEmotionSample(sample) {
      set((state) => ({ emotionLog: [...state.emotionLog, sample] }))
    },

    addGazeSample(sample) {
      set((state) => ({ gazeLog: [...state.gazeLog, sample] }))
    },

    setLipSyncVolume(volume) {
      set({ lipSyncVolume: volume })
    },

    resetVision() {
      set({ facialEmotion: 'neutral', emotionLog: [], gazeLog: [], lipSyncVolume: 0 })
    },
  }
})

/** 셀렉터 헬퍼 */
export const selectLastAiTurn = (s: SessionState): ConversationTurn | undefined =>
  [...s.turns].reverse().find((t) => t.speaker === 'ai')
