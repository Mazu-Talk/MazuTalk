"""Phase 3: DPO preference 데이터 생성.

각 프롬프트에 대해 chosen(SoT 준수) / rejected(규칙 위반) 쌍을 만든다.

- chosen: teacher 가 생성하고 출력 스키마/enum/한국어/금지표현 검증을 통과한 응답.
          (안전 케이스는 신뢰성을 위해 안전 템플릿으로 직접 구성)
- rejected: hard negative. 다음 중 하나를 회전 적용.
    1) base 모델 raw 출력(enum 위반·외국어 혼입이 잦아 자연스러운 negative)
    2) 너무 긴 응답  3) 평가/비난 표현  4) 안전 flag 누락  5) 깨진 JSON

출력: {"system","prompt","chosen","rejected","metadata"} (train_dpo.py 가 소비)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

import common as C
import build_eval_set as bev
from build_sft_data import validate_assistant, SAFETY_TRAIN


OUTPUT_VALIDATOR = Draft202012Validator(C.build_output_schema())
DIFFICULTIES = ["low", "medium", "high"]


# ----------------------------- rejected 생성기 -----------------------------

def rej_too_long(chosen: dict[str, Any]) -> str:
    bad = json.loads(json.dumps(chosen))
    msg = bad.get("child_message", "응.")
    bad["child_message"] = (msg + " ") * 5 + "그리고 더 길게 설명할게. 왜냐하면 여러 가지 이유가 있는데 먼저 첫째로 둘째로 셋째로 자세히 말해줄게."
    return json.dumps(bad, ensure_ascii=False)


def rej_evaluative(chosen: dict[str, Any]) -> str:
    bad = json.loads(json.dumps(chosen))
    bad["child_message"] = "그렇게 말하면 안 돼. 틀렸어. 다시 제대로 말해."
    return json.dumps(bad, ensure_ascii=False)


def rej_drop_safety(chosen: dict[str, Any]) -> str:
    bad = json.loads(json.dumps(chosen))
    bad["safety"] = {"risk_flag": "none", "requires_adult_attention": False}
    return json.dumps(bad, ensure_ascii=False)


def rej_broken_json(chosen: dict[str, Any]) -> str:
    s = json.dumps(chosen, ensure_ascii=False)
    return s[:-1]  # 닫는 중괄호 제거 -> 파싱 실패


def rej_foreign(chosen: dict[str, Any]) -> str:
    bad = json.loads(json.dumps(chosen))
    bad["child_message"] = "你好! 我们一起玩吧。 같이 놀자."
    return json.dumps(bad, ensure_ascii=False)


REJ_STRATEGIES = [rej_too_long, rej_evaluative, rej_broken_json, rej_foreign]


# ----------------------------- 안전 chosen 템플릿 -----------------------------

def safety_chosen(risk: str, needs_adult: bool) -> dict[str, Any]:
    return {
        "child_message": "지금은 가까운 어른에게 바로 말하자. 선생님이나 보호자에게 같이 가자.",
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


# ----------------------------- 메인 생성 -----------------------------

def generate(teacher_backend: str, teacher: str, base: str, max_pairs: int, per_scenario: int) -> list[dict[str, Any]]:
    scenarios = C.iter_scenarios()
    system_prompt = C.load_system_prompt(runtime=True)
    rows: list[dict[str, Any]] = []
    rej_i = 0

    # 1) 역할극 pair
    for idx, scenario in enumerate(scenarios):
        flow = scenario.get("dialogueFlow") or []
        if not flow:
            continue
        step = flow[0]
        target_skill = (scenario.get("targetSkills") or ["unknown"])[0]
        scen_id = scenario.get("scenarioId")
        made = 0
        for j in range(len(bev.ROLEPLAY_CASES)):
            if made >= per_scenario or len(rows) >= max_pairs:
                break
            emotion, utt_type, feats, strat = bev.ROLEPLAY_CASES[j]
            difficulty = DIFFICULTIES[(idx + j) % len(DIFFICULTIES)]
            runtime = C.scenario_to_runtime(
                scenario, target_skill=target_skill, difficulty=difficulty,
                emotion_state=emotion, child_input=bev._child_input(step, strat),
                observed_features=feats,
            )
            user_content = json.dumps(runtime, ensure_ascii=False)
            try:
                raw = C.teacher_generate(
                    teacher_backend, teacher,
                    [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_content}],
                    temperature=0.7, max_new=1024,
                    seed=C.DEFAULT_SEED + len(rows),
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  teacher error: {exc}")
                continue
            chosen = C.extract_json(raw)
            if not chosen or not validate_assistant(chosen):
                continue

            # rejected: base raw 가 invalid 면 그대로, 아니면 corruption 회전
            rejected_str: str | None = None
            if base:
                try:
                    base_raw = C.ollama_chat(
                        base,
                        [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": user_content}],
                        temperature=0.9, num_predict=1024, think=False,
                        seed=C.DEFAULT_SEED + 7 + len(rows),
                    )
                    base_parsed = C.extract_json(base_raw)
                    if base_parsed is None or not validate_assistant(base_parsed):
                        rejected_str = base_raw.strip() or None
                except Exception:  # noqa: BLE001
                    rejected_str = None
            if rejected_str is None:
                rejected_str = REJ_STRATEGIES[rej_i % len(REJ_STRATEGIES)](chosen)
                rej_i += 1

            rows.append({
                "system": system_prompt,
                "prompt": user_content,
                "chosen": json.dumps(chosen, ensure_ascii=False),
                "rejected": rejected_str,
                "metadata": {
                    "kind": "roleplay", "scenario_id": scen_id,
                    "target_skill": target_skill, "emotion": emotion,
                    "preference_reason": "chosen은 SoT 준수(짧고 한국어, 비난 없음, 유효 스키마); rejected는 규칙 위반",
                },
            })
            made += 1
            print(f"[{len(rows)}] pair {scen_id} {emotion}/{utt_type}")

    # 2) 안전 pair (chosen=안전 템플릿, rejected=flag 누락)
    #    입력은 SAFETY_TRAIN(=eval 안전셋과 분리된 표현)을 사용 → eval 누수 방지
    base_scn = scenarios[0] if scenarios else {"context": {}, "targetSkills": ["unknown"]}
    for k, (risk, needs_adult, text) in enumerate(SAFETY_TRAIN):
        if len(rows) >= max_pairs:
            break
        runtime = C.scenario_to_runtime(
            base_scn, target_skill="unknown", difficulty="low",
            emotion_state="anxious", child_input=text,
        )
        chosen = safety_chosen(risk, needs_adult)
        rows.append({
            "system": system_prompt,
            "prompt": json.dumps(runtime, ensure_ascii=False),
            "chosen": json.dumps(chosen, ensure_ascii=False),
            "rejected": rej_drop_safety(chosen),
            "metadata": {
                "kind": "safety", "risk_flag": risk,
                "preference_reason": "chosen은 위험을 flag 하고 어른 연결; rejected는 안전 flag 누락",
            },
        })
        print(f"[{len(rows)}] safety pair risk={risk}")

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="MazuTalk DPO preference 데이터 생성")
    parser.add_argument("--teacher-backend", choices=["ollama", "openai"], default="ollama",
                        help="chosen 생성 teacher 백엔드. openai 는 OPENAI_API_KEY 필요.")
    parser.add_argument("--teacher", default=None,
                        help="chosen teacher 모델. 미지정 시 backend 기본값.")
    parser.add_argument("--base", default="qwen3.5:4b",
                        help="rejected 후보를 뽑을 base 모델(Ollama, 빈 문자열이면 corruption만 사용)")
    parser.add_argument("--per-scenario", type=int, default=3)
    parser.add_argument("--max", type=int, default=600)
    parser.add_argument("--out", type=Path, default=C.PROCESSED_DIR / "dpo_train.jsonl")
    args = parser.parse_args()

    teacher = args.teacher or C.DEFAULT_TEACHER[args.teacher_backend]
    print(f"chosen teacher backend={args.teacher_backend} model={teacher}; rejected base={args.base}")
    rows = generate(args.teacher_backend, teacher, args.base, args.max, args.per_scenario)
    n = C.write_jsonl(args.out, rows)
    n_safety = sum(1 for r in rows if r["metadata"].get("kind") == "safety")
    print(f"OK: {n} DPO pairs -> {args.out} (safety {n_safety})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
