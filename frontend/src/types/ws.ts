/**
 * WebSocket 이벤트 타입 — ARCHITECTURE.md §8.2 WebSocket API
 * 엔드포인트: /ws/sessions/{session_id}
 */
import type { AvatarState, Emotion } from './domain'

/** Client → Server */
export interface AudioChunkEvent {
  type: 'audio_chunk'
  session_id: string
  turn_id: number
  payload: { audio: ArrayBuffer | string }
}

export interface EndUtteranceEvent {
  type: 'end_utterance'
  session_id: string
  turn_id: number
  /** 브라우저 STT를 사용할 때는 인식된 텍스트를 직접 전달 (백엔드 STT 우회 경로) */
  payload: {
    text: string
    duration_seconds?: number
    response_time_ms?: number
    /** 발화 시점의 YOLOv8 표정 스냅샷 (비전 융합용) */
    facial_emotion?: string
  }
}

export type ClientEvent = AudioChunkEvent | EndUtteranceEvent

/** Server → Client */
export interface SttResultEvent {
  type: 'stt_result'
  payload: { text: string; turn_id: number }
}

export interface AvatarStateEvent {
  type: 'avatar_state'
  payload: { avatar_state: AvatarState }
}

export interface AiResponseEvent {
  type: 'ai_response'
  payload: {
    text: string
    emotion: Emotion
    audio_url: string | null
    avatar_state: AvatarState
    turn_id: number
  }
}

export interface ErrorEvent {
  type: 'error'
  payload: { message: string; recoverable: boolean }
}

export type ServerEvent =
  | SttResultEvent
  | AvatarStateEvent
  | AiResponseEvent
  | ErrorEvent

export type ServerEventType = ServerEvent['type']

export interface SttPipelineResponse {
  session_id: string
  turn_id: string
  transcript: string
  stt_model: string
  stt_time_seconds: number
  stt_fallback_used: boolean
  stt_fallback_reason: string | null
  llm: {
    therapist_reply: string
    next_prompt: string
    coaching_cues: string[]
    model_name: string
  }
  audio_url: string | null
  emotion: Emotion
  avatar_state: AvatarState
}
