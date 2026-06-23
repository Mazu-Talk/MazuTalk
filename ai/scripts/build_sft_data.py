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
    args = parser.parse_args()

    teacher = args.teacher or C.DEFAULT_TEACHER[args.backend]
    ages = [int(a) for a in args.ages.split(",") if a.strip()]
    print(f"teacher backend={args.backend} model={teacher} ages={ages}")
    rows = generate(args.backend, teacher, args.max, args.eval, args.per_scenario, ages)
    n = C.write_jsonl(args.out, rows)
    print(f"OK: {n} SFT turns -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
