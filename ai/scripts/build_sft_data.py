"""Phase 1: SFT 데이터 생성.

seed 시나리오(ai/data/scenarios) × (감정 × 발화유형 × 난이도) 조합으로 런타임
입력을 만들고, teacher 모델(로컬 Ollama 또는 더 강한 모델)로 SoT 준수 assistant
응답을 생성한다. 출력 스키마/enum 검증을 통과한 것만 SFT 데이터로 채택한다.

출력 형식(계획서 §Phase 1): {"messages":[system,user,assistant], "metadata":{...}}

- system  = 런타임 축약 프롬프트(RP_system_prompt_runtime.md) → 서빙과 동일 (skew 방지)
- 평가셋(eval_set.jsonl)에 쓰인 (scenario, emotion, utterance) 조합은 제외(누수 방지)
- teacher 가 invalid JSON/enum 위반/외국어 혼입을 내면 해당 turn 은 버린다.

실제 대량 생성은 Colab에서 강한 teacher로 돌리는 것을 권장한다. 로컬에서는
파이프라인 검증과 소량 생성을 위해 사용한다.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

import common as C
import build_eval_set as bev


OUTPUT_VALIDATOR = Draft202012Validator(C.build_output_schema())
_HANGUL_OR_ASCII = re.compile(r"[가-힣A-Za-z0-9\s\.\,\!\?\'\"~…·\-\(\)]+")
# 한글/영숫자/기호 외 문자(중국어·일본어·키릴 등)가 섞였는지 검사
_FOREIGN = re.compile(r"[぀-ヿ一-鿿Ѐ-ӿ]")

DIFFICULTIES = ["low", "medium", "high"]

# 학습용 안전 케이스. eval_set 의 SAFETY_CASES 와 표현이 겹치지 않게 구성(누수 방지).
# 표현을 풍부하게 다양화해 모델이 "특정 문장 암기"가 아니라 "위험 개념"을 일반화하도록 한다.
# (eval 은 self_harm/abuse/aggression/medical/distress 5종만 채점하므로 거기에 집중)
SAFETY_TRAIN = [
    # self_harm
    ("self_harm", True, "나 없어졌으면 좋겠어"),
    ("self_harm", True, "사는 게 너무 싫어, 다 그만하고 싶어"),
    ("self_harm", True, "나 같은 건 그냥 사라져도 돼"),
    ("self_harm", True, "자꾸 나쁜 생각이 들어"),
    ("self_harm", True, "세상에서 없어지고 싶어"),
    ("self_harm", True, "아무도 날 안 좋아해서 사라지고 싶어"),
    ("self_harm", True, "나 죽으면 다 편해질까"),
    ("self_harm", True, "다 끝내버리고 싶어"),
    # abuse
    ("abuse", True, "엄마가 화나면 나를 자꾸 때려요"),
    ("abuse", True, "삼촌이 자꾸 이상한 데를 만져"),
    ("abuse", True, "어른이 아무한테도 말하지 말랬어"),
    ("abuse", True, "형이 매일 나를 꼬집고 때려"),
    ("abuse", True, "누가 옷을 벗으라고 했어"),
    ("abuse", True, "아빠가 밥을 안 주고 방에 가둬"),
    ("abuse", True, "이웃 아저씨가 자꾸 만지려고 해"),
    ("abuse", True, "엄마가 다치게 하고 비밀로 하래"),
    # aggression
    ("aggression", True, "쟤 가위로 찌를 거야"),
    ("aggression", True, "친구 물건 다 부숴버릴래"),
    ("aggression", True, "발로 차서 울려버릴 거야"),
    ("aggression", True, "돌로 머리를 때릴 거야"),
    ("aggression", True, "쟤를 계단에서 밀어버릴래"),
    ("aggression", True, "친구를 세게 깨물어 줄 거야"),
    ("aggression", True, "의자를 던질 거야"),
    ("aggression", True, "쟤 머리카락 다 잘라버릴래"),
    # medical
    ("medical", True, "넘어져서 팔에서 피가 많이 나"),
    ("medical", True, "갑자기 가슴이 아프고 숨쉬기 힘들어"),
    ("medical", True, "머리를 부딪혀서 너무 어지러워"),
    ("medical", True, "배가 너무 아파서 토할 것 같아"),
    ("medical", True, "손가락이 문에 끼어서 피가 나"),
    ("medical", True, "갑자기 눈이 잘 안 보여"),
    ("medical", True, "뜨거운 물에 데서 너무 따가워"),
    ("medical", True, "자꾸 어지럽고 쓰러질 것 같아"),
    # distress
    ("distress", True, "너무 무서워서 자꾸 떨려요"),
    ("distress", True, "여기 나 혼자 있는데 무서워"),
    ("distress", True, "엄마가 안 와서 너무 무서워"),
    ("distress", True, "숨고 싶을 만큼 무서워"),
    ("distress", True, "자꾸 나쁜 꿈이 생각나서 떨려"),
    ("distress", True, "무서워서 아무 말도 못 하겠어"),
    ("distress", True, "심장이 쿵쿵 뛰고 너무 불안해"),
    ("distress", True, "자꾸 눈물이 나고 마음이 아파"),
]

# 안전 응답 child_message 변형(모두 SoT §14 준수: 차분·어른 연결·비난 없음).
# 한 문장만 암기하지 않도록 회전 사용.
SAFE_MESSAGES = [
    "지금은 가까운 어른에게 바로 말하자. 선생님이나 보호자에게 같이 가자.",
    "이건 어른이 꼭 알아야 해. 옆에 있는 선생님이나 부모님에게 같이 말하러 가자.",
    "많이 힘들었겠다. 지금 바로 믿을 수 있는 어른에게 이야기하자.",
    "그건 위험할 수 있어. 가까운 어른을 찾아서 같이 말하자.",
    "놀이는 잠깐 멈추자. 지금은 어른에게 도움을 받는 게 가장 중요해.",
    "괜찮아, 네 잘못이 아니야. 어른에게 바로 알리자.",
]


def _safety_response(risk: str, needs_adult: bool, message: str) -> dict[str, Any]:
    """안전 신호 감지 시 SoT(§14) 기준의 모범 응답."""
    return {
        "child_message": message,
        "avatar_expression": "concerned",
        "tts_style": {"speed": "slow", "tone": "calm", "pause_after_ms": 400},
        "detected": {
            "emotion": "anxious", "social_skill": "unknown",
            "utterance_type": "appropriate_response", "engagement": "low",
        },
        "coaching": {
            "strategy": "close_session", "next_goal": "안전 확보 후 어른과 함께 있기",
            "difficulty_next": "low", "reason": "위험 신호가 있어 역할극을 멈추고 어른에게 연결",
        },
        "report_event": {
            "turn_success": False, "child_attempt_observed": True,
            "response_length": "sentence", "conversation_continued": False,
            "notes_for_guardian": "아동 발화에서 위험 신호가 감지되어 안전 안내로 전환함. 보호자 확인 필요.",
        },
        "safety": {"risk_flag": risk, "requires_adult_attention": needs_adult},
    }


def generate_safety(ages: list[int]) -> list[dict[str, Any]]:
    """안전 케이스 SFT turn 생성(템플릿 응답 회전, teacher 불필요)."""
    import json
    scenarios = C.iter_scenarios()
    base_scn = scenarios[0] if scenarios else {"context": {}, "targetSkills": ["unknown"]}
    system_prompt = C.load_system_prompt(runtime=True)
    rows: list[dict[str, Any]] = []
    for i, (risk, needs_adult, text) in enumerate(SAFETY_TRAIN):
        for j, age in enumerate(ages):
            message = SAFE_MESSAGES[(i + j) % len(SAFE_MESSAGES)]
            runtime = C.scenario_to_runtime(
                base_scn, target_skill="unknown", difficulty="low",
                emotion_state="anxious", child_input=text, child_age=age,
            )
            assistant = _safety_response(risk, needs_adult, message)
            rows.append({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(runtime, ensure_ascii=False)},
                    {"role": "assistant", "content": json.dumps(assistant, ensure_ascii=False)},
                ],
                "metadata": {
                    "kind": "safety", "risk_flag": risk, "child_age": age,
                },
            })
    return rows


def _is_korean_clean(text: str) -> bool:
    return not _FOREIGN.search(text)


def _eval_combo_keys(eval_path: Path) -> set[tuple]:
    keys: set[tuple] = set()
    if not eval_path.exists():
        return keys
    for r in C.read_jsonl(eval_path):
        exp = r.get("expected", {})
        keys.add((r.get("scenario_id"), exp.get("emotion_state"), exp.get("utterance_type")))
    return keys


def validate_assistant(parsed: dict[str, Any]) -> bool:
    if not OUTPUT_VALIDATOR.is_valid(parsed):
        return False
    msg = str(parsed.get("child_message", ""))
    if not msg or not _is_korean_clean(msg):
        return False
    if C.find_forbidden(msg):
        return False
    return True


def generate(backend: str, teacher: str, max_turns: int, eval_path: Path,
             per_scenario: int, ages: list[int]) -> list[dict[str, Any]]:
    scenarios = C.iter_scenarios()
    exclude = _eval_combo_keys(eval_path)
    system_prompt = C.load_system_prompt(runtime=True)

    rows: list[dict[str, Any]] = []
    attempted = kept = 0

    for idx, scenario in enumerate(scenarios):
        flow = scenario.get("dialogueFlow") or []
        if not flow:
            continue
        step = flow[0]
        target_skill = (scenario.get("targetSkills") or ["unknown"])[0]
        scen_id = scenario.get("scenarioId")

        combos = 0
        for j in range(len(bev.ROLEPLAY_CASES)):
            if combos >= per_scenario or len(rows) >= max_turns:
                break
            emotion, utt_type, feats, strat = bev.ROLEPLAY_CASES[j]
            if (scen_id, emotion, utt_type) in exclude:
                continue  # 누수 방지
            combos += 1
            # 나이별 변주: 나이에 따라 난이도도 회전시켜 타깃 다양화
            for ai, age in enumerate(ages):
                if len(rows) >= max_turns:
                    break
                difficulty = DIFFICULTIES[(idx + j + ai) % len(DIFFICULTIES)]
                runtime = C.scenario_to_runtime(
                    scenario, target_skill=target_skill, difficulty=difficulty,
                    emotion_state=emotion, child_input=bev._child_input(step, strat),
                    observed_features=feats, child_age=age,
                )
                user_content = json.dumps(runtime, ensure_ascii=False)
                attempted += 1
                try:
                    raw = C.teacher_generate(
                        backend, teacher,
                        [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": user_content}],
                        temperature=0.7, max_new=1024,
                        seed=C.DEFAULT_SEED + attempted,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"  teacher error {scen_id}/{emotion}/{utt_type}/age{age}: {exc}")
                    continue
                parsed = C.extract_json(raw)
                if not parsed or not validate_assistant(parsed):
                    continue
                rows.append({
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)},
                    ],
                    "metadata": {
                        "scenario_id": scen_id,
                        "target_skill": target_skill,
                        "difficulty": difficulty,
                        "emotion": emotion,
                        "utterance_type": utt_type,
                        "child_age": age,
                        "strategy": parsed.get("coaching", {}).get("strategy"),
                        "teacher": teacher,
                        "teacher_backend": backend,
                    },
                })
                kept += 1
                print(f"[{kept}] kept {scen_id} {emotion}/{utt_type}/{difficulty}/age{age}")

    print(f"\n생성 시도 {attempted}, 채택 {kept} (탈락률 {100*(attempted-kept)/max(attempted,1):.0f}%)")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="MazuTalk SFT 데이터 생성")
    parser.add_argument("--backend", choices=["ollama", "openai"], default="ollama",
                        help="teacher 백엔드. openai 는 OPENAI_API_KEY 필요.")
    parser.add_argument("--teacher", default=None,
                        help="teacher 모델. 미지정 시 backend 기본값(ollama=qwen3.5:4b, openai=gpt-4o-mini)")
    parser.add_argument("--per-scenario", type=int, default=9)
    parser.add_argument("--ages", default="6,7,8",
                        help="child_age 변주(쉼표구분). 조합당 나이별로 샘플 생성해 볼륨 확장.")
    parser.add_argument("--max", type=int, default=2000)
    parser.add_argument("--eval", type=Path, default=C.PROCESSED_DIR / "eval_set.jsonl")
    parser.add_argument("--out", type=Path, default=C.PROCESSED_DIR / "sft_train.jsonl")
    parser.add_argument("--no-safety", action="store_true",
                        help="안전 케이스 SFT turn 생성을 건너뜀")
    parser.add_argument("--safety-only", action="store_true",
                        help="안전 케이스만 생성(teacher 미사용). 기존 데이터에 보강할 때 사용")
    args = parser.parse_args()

    ages = [int(a) for a in args.ages.split(",") if a.strip()]

    if args.safety_only:
        rows = generate_safety(ages)
        n = C.write_jsonl(args.out, rows)
        print(f"OK: {n} safety SFT turns -> {args.out}")
        return 0

    teacher = args.teacher or C.DEFAULT_TEACHER[args.backend]
    print(f"teacher backend={args.backend} model={teacher} ages={ages}")
    rows = generate(args.backend, teacher, args.max, args.eval, args.per_scenario, ages)
    if not args.no_safety:
        safety_rows = generate_safety(ages)
        rows += safety_rows
        print(f"안전 케이스 {len(safety_rows)} turn 추가")
    n = C.write_jsonl(args.out, rows)
    n_safety = sum(1 for r in rows if r["metadata"].get("kind") == "safety")
    print(f"OK: {n} SFT turns -> {args.out} (안전 {n_safety})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
