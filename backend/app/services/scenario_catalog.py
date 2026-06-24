"""시나리오 컨텍스트 카탈로그 (LLM 프롬프트 grounding 용).

프런트 `data/scenarios.ts`의 핵심 필드를 백엔드에서도 참조할 수 있게 미러링한다.
RP 시스템 프롬프트가 기대하는 difficulty(low|medium|high)/target_skill/goal 을 제공해
또래 친구 응답의 길이·전략이 시나리오에 맞게 조정되도록 한다.
"""

SCENARIOS: dict[str, dict[str, str]] = {
    "playground_greeting": {
        "location": "놀이터",
        "situation": "놀이터에서 처음 만난 친구에게 먼저 인사하기",
        "target_skill": "greeting",
        "goal": "인사하고 대화를 3턴 이상 이어가기",
        "difficulty": "low",
    },
    "classroom_emotion": {
        "location": "교실",
        "situation": "교실에서 친구와 오늘 기분을 이야기하기",
        "target_skill": "emotion_expression",
        "goal": "자기 기분을 한 단어로 말하고 이유를 덧붙이기",
        "difficulty": "medium",
    },
    "blocks_help": {
        "location": "교실 놀이 시간",
        "situation": "블록이 잘 안 끼워질 때 친구에게 도움 요청하기",
        "target_skill": "requesting_help",
        "goal": "\"도와줄래?\"라고 요청하고 고맙다고 말하기",
        "difficulty": "low",
    },
    "sandbox_conflict": {
        "location": "모래놀이터",
        "situation": "같은 삽을 쓰고 싶을 때 밀지 않고 말로 부탁하기",
        "target_skill": "conflict_resolution",
        "goal": "순서를 기다리며 \"끝나면 빌려줄래?\"라고 부탁하기",
        "difficulty": "high",
    },
    "park_joining_play": {
        "location": "공원",
        "situation": "친구들의 술래잡기 놀이에 끼고 싶을 때 말하기",
        "target_skill": "joining_play",
        "goal": "\"나도 같이 놀아도 돼?\"라고 묻고 대답에 반응하기",
        "difficulty": "medium",
    },
    "goodbye_friend": {
        "location": "유치원 앞",
        "situation": "놀이를 마치고 친구와 헤어질 때 인사하기",
        "target_skill": "goodbye",
        "goal": "헤어지는 인사를 하고 다음에 또 만나자고 말하기",
        "difficulty": "low",
    },
}


def get_scenario_context(scenario_id: str) -> dict[str, str]:
    return SCENARIOS.get(scenario_id, {})
