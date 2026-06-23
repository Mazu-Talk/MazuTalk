/**
 * 실시간 대화 연결 — ARCHITECTURE.md §8.2 WebSocket API.
 *
 * mock 모드: 백엔드 없이 STT결과 → 아바타 thinking → AI응답 파이프라인을 타이머로 시뮬레이션한다.
 * real 모드: /ws/sessions/{session_id} 에 연결하여 동일한 ServerEvent 스트림을 수신한다.
 *
 * 어느 모드든 소비자(sessionStore)는 onEvent(ServerEvent) 한 가지 인터페이스만 사용한다.
 */
import type { ConversationTurn, Scenario } from '@/types/domain'
import type { ServerEvent } from '@/types/ws'
import { USE_MOCK, WS_BASE } from './config'
import { generateMockTurn } from './mockEngine'

export interface SendUtteranceArgs {
  turnId: number
  text: string
  responseTimeMs: number
  /** mock 엔진에 필요한 컨텍스트 (real 모드에서는 서버가 보유하므로 무시됨) */
  scenario: Scenario
  history: ConversationTurn[]
}

type EventHandler = (event: ServerEvent) => void

export interface RolePlayConnection {
  onEvent(handler: EventHandler): void
  sendUtterance(args: SendUtteranceArgs): void
  close(): void
}

/** 연결 생성 팩토리 */
export function connectRolePlay(sessionId: string): RolePlayConnection {
  return USE_MOCK
    ? new MockConnection()
    : new RealConnection(sessionId)
}

// ---------------------------------------------------------------------------
// Mock 구현
// ---------------------------------------------------------------------------
class MockConnection implements RolePlayConnection {
  private handler: EventHandler | null = null
  private timers: ReturnType<typeof setTimeout>[] = []

  onEvent(handler: EventHandler) {
    this.handler = handler
  }

  sendUtterance({ turnId, text, responseTimeMs, scenario, history }: SendUtteranceArgs) {
    // 1) STT 결과 (사용자가 말한 내용 확정) — 거의 즉시
    this.schedule(150, {
      type: 'stt_result',
      payload: { text, turn_id: turnId },
    })

    // 2) 아바타: 생각 중
    this.schedule(300, {
      type: 'avatar_state',
      payload: { avatar_state: 'thinking' },
    })

    // 3) AI 응답 (LLM + 감정 + 아바타 상태). 데모용으로 0.8~1.3초 지연.
    const think = 800 + Math.min(text.length * 20, 500)
    const out = generateMockTurn({ scenario, childText: text, responseTimeMs, history })
    this.schedule(300 + think, {
      type: 'ai_response',
      payload: {
        text: out.text,
        emotion: out.emotion,
        audio_url: null, // mock: 브라우저 SpeechSynthesis 로 재생
        avatar_state: out.avatarState,
        turn_id: turnId + 1,
      },
    })
  }

  private schedule(ms: number, event: ServerEvent) {
    const t = setTimeout(() => this.handler?.(event), ms)
    this.timers.push(t)
  }

  close() {
    this.timers.forEach(clearTimeout)
    this.timers = []
    this.handler = null
  }
}

// ---------------------------------------------------------------------------
// Real 구현 (백엔드 준비 시 사용)
// ---------------------------------------------------------------------------
class RealConnection implements RolePlayConnection {
  private ws: WebSocket
  private handler: EventHandler | null = null
  private queue: string[] = []
  private ready = false

  constructor(sessionId: string) {
    this.ws = new WebSocket(`${WS_BASE}/sessions/${sessionId}`)
    this.ws.onopen = () => {
      this.ready = true
      this.queue.forEach((m) => this.ws.send(m))
      this.queue = []
    }
    this.ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as ServerEvent
        this.handler?.(event)
      } catch {
        this.handler?.({
          type: 'error',
          payload: { message: '응답을 읽지 못했어요.', recoverable: true },
        })
      }
    }
    this.ws.onerror = () => {
      this.handler?.({
        type: 'error',
        payload: { message: '연결에 문제가 생겼어요.', recoverable: true },
      })
    }
  }

  onEvent(handler: EventHandler) {
    this.handler = handler
  }

  sendUtterance({ turnId, text }: SendUtteranceArgs) {
    // 브라우저 STT로 이미 텍스트를 얻었으므로 end_utterance 에 text 를 실어 보낸다.
    this.send(
      JSON.stringify({
        type: 'end_utterance',
        session_id: '',
        turn_id: turnId,
        payload: { text },
      }),
    )
  }

  private send(message: string) {
    if (this.ready) this.ws.send(message)
    else this.queue.push(message)
  }

  close() {
    this.handler = null
    this.ws.close()
  }
}
