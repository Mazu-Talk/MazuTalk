/**
 * 마주톡 도메인 타입
 * 출처: ARCHITECTURE.md §7 데이터 모델, FunctionalDescription.md, ai/prompts/RP_system_prompt.md
 */

/** 감정 라벨 — ARCHITECTURE §5.4 + RP 프롬프트의 emotion_state */
export type Emotion =
  | 'happy' // 기쁨
  | 'neutral' // 중립
  | 'anxious' // 긴장
  | 'confused' // 혼란
  | 'passive' // 소극적
  | 'shy' // 부끄러움
  | 'frustrated' // 속상함

/** 아바타 상태 — ARCHITECTURE §5.8 + FD-06 */
export type AvatarState =
  | 'idle' // 대기
  | 'listening' // 사용자 음성 청취
  | 'thinking' // AI 응답 생성 중
  | 'speaking' // TTS 재생 중
  | 'happy' // 긍정 감정
  | 'confused' // 혼란
  | 'encouraging' // 격려
  | 'sad' // 슬픔

/** 난이도 — scenario.schema (easy/medium/hard) */
export type Difficulty = 'easy' | 'medium' | 'hard'

/** 사회성 기술 — RP 프롬프트 §3 */
export type SocialSkill =
  | 'greeting'
  | 'self_introduction'
  | 'emotion_expression'
  | 'requesting_help'
  | 'joining_play'
  | 'turn_taking'
  | 'conflict_resolution'
  | 'goodbye'

export type Speaker = 'child' | 'ai'

export type SessionStatus = 'active' | 'completed' | 'interrupted'

/** 시나리오 — ARCHITECTURE §7.3 Scenario (+ UI 표현용 필드) */
export interface Scenario {
  scenario_id: string
  title: string
  location: string
  target_skill: SocialSkill
  difficulty: Difficulty
  ai_role: 'peer_friend' | 'teacher'
  opening_message: string
  success_criteria: string[]
  /** UI 표현용 */
  emoji: string
  description: string
  accent: string // tailwind 색상 클래스 접두용 hex
}

/** 대화 턴 — ARCHITECTURE §7.2 ConversationTurn */
export interface ConversationTurn {
  turn_id: number
  session_id: string
  speaker: Speaker
  text: string
  emotion: Emotion
  response_time_ms: number
  created_at: string
  /** AI 턴이 음성으로 재생될 오디오 (mock 모드에서는 브라우저 TTS 사용) */
  audio_url?: string
}

/** 세션 — ARCHITECTURE §7.1 Session */
export interface Session {
  session_id: string
  child_id: string
  scenario_id: string
  started_at: string
  ended_at?: string
  status: SessionStatus
}

/** 감정 타임라인 한 점 — ARCHITECTURE §7.4 */
export interface EmotionPoint {
  turn_id: number
  emotion: Emotion
}

/** 시선 요약 — MediaPipe 시선 추적 결과 */
export interface GazeSummary {
  center: number  // 정면 비율 (%)
  left: number    // 왼쪽 비율 (%)
  right: number   // 오른쪽 비율 (%)
}

/** 학습 리포트 — ARCHITECTURE §7.4 Report + FD-07 */
export interface Report {
  report_id: string
  session_id: string
  scenario_id: string
  total_turns: number
  avg_response_time_ms: number
  avg_utterance_length: number
  emotion_timeline: EmotionPoint[]
  dominant_emotion: Emotion
  participation_score: number
  completion_status: 'completed' | 'interrupted'
  created_at: string
  gaze_summary?: GazeSummary  // 시선 집중도 (선택적, MediaPipe 시선 추적 결과)
}