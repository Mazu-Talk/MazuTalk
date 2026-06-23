import type { Scenario } from '@/types/domain'

/**
 * MVP 시나리오 데이터셋.
 * FR-001(시나리오 선택) 우선 제공 4종 + 확장 2종.
 * 백엔드 GET /api/scenarios 가 준비되면 client.ts 가 이 데이터를 대체한다.
 */
export const SCENARIOS: Scenario[] = [
  {
    scenario_id: 'playground_greeting',
    title: '친구에게 인사하기',
    location: '놀이터',
    target_skill: 'greeting',
    difficulty: 'easy',
    ai_role: 'peer_friend',
    opening_message: '안녕! 나는 미래야. 너도 같이 놀래?',
    success_criteria: [
      '인사 표현을 말한다',
      '상대방의 질문에 응답한다',
      '대화를 3턴 이상 유지한다',
    ],
    emoji: '👋',
    description: '놀이터에서 처음 만난 친구에게 먼저 인사해 봐요.',
    accent: '#ffd166',
  },
  {
    scenario_id: 'classroom_emotion',
    title: '감정 표현하기',
    location: '교실',
    target_skill: 'emotion_expression',
    difficulty: 'medium',
    ai_role: 'peer_friend',
    opening_message: '오늘 기분이 어때? 나는 좀 신나!',
    success_criteria: [
      '자신의 기분을 한 단어로 말한다',
      '왜 그런 기분인지 짧게 말한다',
      '친구의 기분을 물어본다',
    ],
    emoji: '💛',
    description: '지금 내 마음이 어떤지 친구에게 말해 봐요.',
    accent: '#cdb4f6',
  },
  {
    scenario_id: 'blocks_help',
    title: '도움 요청하기',
    location: '교실 놀이 시간',
    target_skill: 'requesting_help',
    difficulty: 'easy',
    ai_role: 'peer_friend',
    opening_message: '블록이 잘 안 끼워지네. 우리 같이 만들어 볼까?',
    success_criteria: [
      '어려운 상황을 말한다',
      '"도와줄래?" 라고 요청한다',
      '도움을 받고 고맙다고 말한다',
    ],
    emoji: '🧩',
    description: '어려울 때 "도와줘"라고 말하는 연습이에요.',
    accent: '#a0c4ff',
  },
  {
    scenario_id: 'sandbox_conflict',
    title: '갈등 해결하기',
    location: '모래놀이터',
    target_skill: 'conflict_resolution',
    difficulty: 'hard',
    ai_role: 'peer_friend',
    opening_message: '내가 지금 삽을 쓰고 있어. 너도 쓰고 싶어?',
    success_criteria: [
      '밀거나 빼앗지 않고 말로 표현한다',
      '"끝나면 빌려줄래?" 라고 부탁한다',
      '순서를 기다린다',
    ],
    emoji: '🤝',
    description: '장난감을 같이 쓰고 싶을 때 말로 부탁해 봐요.',
    accent: '#ff9aa2',
  },
  {
    scenario_id: 'park_joining_play',
    title: '놀이에 참여하기',
    location: '공원',
    target_skill: 'joining_play',
    difficulty: 'medium',
    ai_role: 'peer_friend',
    opening_message: '우리 지금 술래잡기 하고 있어!',
    success_criteria: [
      '같이 놀고 싶다고 말한다',
      '"나도 같이 놀아도 돼?" 라고 묻는다',
      '대답을 듣고 반응한다',
    ],
    emoji: '🏃',
    description: '친구들 놀이에 끼고 싶을 때 말해 봐요.',
    accent: '#7bd389',
  },
  {
    scenario_id: 'goodbye_friend',
    title: '헤어질 때 인사하기',
    location: '유치원 앞',
    target_skill: 'goodbye',
    difficulty: 'easy',
    ai_role: 'peer_friend',
    opening_message: '오늘 너랑 놀아서 정말 즐거웠어!',
    success_criteria: [
      '헤어지는 인사를 한다',
      '고맙다고 말한다',
      '다음에 또 만나자고 말한다',
    ],
    emoji: '👋',
    description: '오늘 놀이를 마치고 친구와 인사해요.',
    accent: '#8ec6ff',
  },
]

export function getScenario(id: string): Scenario | undefined {
  return SCENARIOS.find((s) => s.scenario_id === id)
}
