import type { ConversationTurn, Scenario } from '@/types/domain'
import type { ServerEvent, SttPipelineResponse } from '@/types/ws'
import { REST_BASE, USE_MOCK, WS_BASE } from './config'
import { generateMockTurn } from './mockEngine'

export type UtteranceContent =
  | { text: string; audio?: never; durationSeconds?: number }
  | { audio: Blob; text?: never; durationSeconds: number }

export interface SendUtteranceArgs {
  turnId: number
  responseTimeMs: number
  scenario: Scenario
  history: ConversationTurn[]
  content: UtteranceContent
  /** 발화 시점의 표정 스냅샷 (YOLOv8) — 비전 융합용 */
  facialEmotion?: string
}

type EventHandler = (event: ServerEvent) => void

export interface RolePlayConnection {
  onEvent(handler: EventHandler): void
  sendUtterance(args: SendUtteranceArgs): void
  close(): void
}

export function connectRolePlay(sessionId: string): RolePlayConnection {
  return USE_MOCK ? new MockConnection() : new RealConnection(sessionId)
}

class MockConnection implements RolePlayConnection {
  private handler: EventHandler | null = null
  private timers: ReturnType<typeof setTimeout>[] = []

  onEvent(handler: EventHandler) {
    this.handler = handler
  }

  sendUtterance({ turnId, responseTimeMs, scenario, history, content }: SendUtteranceArgs) {
    if (!content.text) {
      this.schedule(0, {
        type: 'error',
        payload: { message: 'Mock 모드에서는 브라우저 음성 인식을 사용해 주세요.', recoverable: true },
      })
      return
    }
    const text = content.text
    this.schedule(150, { type: 'stt_result', payload: { text, turn_id: turnId } })
    this.schedule(300, { type: 'avatar_state', payload: { avatar_state: 'thinking' } })
    const out = generateMockTurn({ scenario, childText: text, responseTimeMs, history })
    this.schedule(1100 + Math.min(text.length * 20, 500), {
      type: 'ai_response',
      payload: {
        text: out.text,
        emotion: out.emotion,
        audio_url: null,
        avatar_state: out.avatarState,
        turn_id: turnId,
      },
    })
  }

  private schedule(ms: number, event: ServerEvent) {
    const timer = setTimeout(() => this.handler?.(event), ms)
    this.timers.push(timer)
  }

  close() {
    this.timers.forEach(clearTimeout)
    this.timers = []
    this.handler = null
  }
}

class RealConnection implements RolePlayConnection {
  private ws: WebSocket
  private handler: EventHandler | null = null
  private queue: string[] = []
  private ready = false
  private closed = false

  constructor(private readonly sessionId: string) {
    this.ws = new WebSocket(`${WS_BASE}/sessions/${sessionId}/ws`)
    this.ws.onopen = () => {
      this.ready = true
      this.queue.forEach((message) => this.ws.send(message))
      this.queue = []
    }
    this.ws.onmessage = (message) => {
      try {
        this.handler?.(JSON.parse(message.data) as ServerEvent)
      } catch {
        this.emitError('응답을 읽지 못했어요.')
      }
    }
    this.ws.onerror = () => this.emitError('실시간 연결에 문제가 생겼어요.')
  }

  onEvent(handler: EventHandler) {
    this.handler = handler
  }

  sendUtterance(args: SendUtteranceArgs) {
    if (args.content.audio) {
      void this.sendAudio(args)
      return
    }
    this.send(JSON.stringify({
      type: 'end_utterance',
      session_id: this.sessionId,
      turn_id: args.turnId,
      payload: {
        text: args.content.text,
        duration_seconds: args.content.durationSeconds,
        response_time_ms: args.responseTimeMs,
        facial_emotion: args.facialEmotion,
      },
    }))
  }

  private async sendAudio(args: SendUtteranceArgs) {
    const audio = args.content.audio
    if (!audio) return
    this.handler?.({ type: 'avatar_state', payload: { avatar_state: 'thinking' } })
    const form = new FormData()
    const extension = audio.type.includes('ogg') ? 'ogg' : 'webm'
    form.append('audio', audio, `turn-${args.turnId}.${extension}`)
    form.append('session_id', this.sessionId)
    form.append('turn_id', String(args.turnId))
    form.append('duration_seconds', String(args.content.durationSeconds))
    if (args.facialEmotion) form.append('facial_emotion', args.facialEmotion)
    const responseStartedAt = Date.now() - args.content.durationSeconds * 1000
    form.append('response_requested_at', new Date(responseStartedAt - args.responseTimeMs).toISOString())
    form.append('response_started_at', new Date(responseStartedAt).toISOString())

    try {
      const response = await fetch(`${REST_BASE}/stt/pipeline`, { method: 'POST', body: form })
      if (!response.ok) throw new Error(`STT pipeline returned ${response.status}`)
      const result = (await response.json()) as SttPipelineResponse
      if (this.closed) return
      this.handler?.({
        type: 'stt_result',
        payload: { text: result.transcript, turn_id: args.turnId },
      })
      this.handler?.({
        type: 'ai_response',
        payload: {
          text: result.llm.therapist_reply,
          emotion: result.emotion,
          audio_url: result.audio_url,
          avatar_state: result.avatar_state,
          turn_id: args.turnId,
        },
      })
    } catch {
      if (!this.closed) this.emitError('음성을 처리하지 못했어요.')
    }
  }

  private send(message: string) {
    if (this.ready) this.ws.send(message)
    else this.queue.push(message)
  }

  private emitError(message: string) {
    this.handler?.({ type: 'error', payload: { message, recoverable: true } })
  }

  close() {
    this.closed = true
    this.handler = null
    this.ws.close()
  }
}
