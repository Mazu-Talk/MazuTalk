import type { Difficulty, Emotion, SocialSkill } from '@/types/domain'

/** 감정 → 한글 라벨 + 표정 이모지 + 색상 */
export const EMOTION_META: Record<
  Emotion,
  { label: string; emoji: string; color: string }
> = {
  happy: { label: '기쁨', emoji: '😊', color: '#ffd166' },
  neutral: { label: '편안함', emoji: '🙂', color: '#c7d0db' },
  anxious: { label: '긴장', emoji: '😟', color: '#a0c4ff' },
  confused: { label: '혼란', emoji: '😕', color: '#cdb4f6' },
  passive: { label: '조용함', emoji: '😐', color: '#bfc8d6' },
  shy: { label: '부끄러움', emoji: '☺️', color: '#ffc6e0' },
  frustrated: { label: '속상함', emoji: '😣', color: '#ff9aa2' },
}

export const DIFFICULTY_META: Record<
  Difficulty,
  { label: string; stars: number; color: string }
> = {
  easy: { label: '쉬워요', stars: 1, color: '#7bd389' },
  medium: { label: '보통이에요', stars: 2, color: '#ffd166' },
  hard: { label: '도전이에요', stars: 3, color: '#ff9aa2' },
}

export const SKILL_LABEL: Record<SocialSkill, string> = {
  greeting: '인사하기',
  self_introduction: '자기소개하기',
  emotion_expression: '감정 표현하기',
  requesting_help: '도움 요청하기',
  joining_play: '놀이에 참여하기',
  turn_taking: '순서 지키기',
  conflict_resolution: '갈등 해결하기',
  goodbye: '헤어질 때 인사하기',
}
