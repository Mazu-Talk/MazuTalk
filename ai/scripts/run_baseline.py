"""Phase 0: baseline 추론.

frozen 평가셋(eval_set.jsonl)을 대상으로 지정 모델(기본 qwen3.5:4b)을
로컬 Ollama로 추론해 원시 출력을 저장한다.

- system = RP_system_prompt.md 전문
- user   = 런타임 입력 JSON (계획서 §6 contract)
- thinking 비활성화(think=false), temperature 0, 고정 num_predict (평가 무결성)

SFT/DPO 모델 평가에도 동일 스크립트를 재사용한다(--model, --out 만 변경).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import common as C


def run(model: str, eval_path: Path, out_path: Path, limit: int, num_predict: int) -> int:
    cases = C.read_jsonl(eval_path)
    if limit > 0:
        cases = cases[:limit]

    system_prompt = C.load_system_prompt()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            user_content = json.dumps(case["input"], ensure_ascii=False)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            t0 = time.perf_counter()
            try:
                raw = C.ollama_chat(
                    model, messages,
                    temperature=0.7, num_predict=num_predict, think=False,
                    seed=C.DEFAULT_SEED,
                )
                error = None
            except Exception as exc:  # noqa: BLE001 - 케이스별 실패를 기록하고 계속
                raw, error = "", str(exc)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            row = {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "expected": case["expected"],
                "raw_output": raw,
                "error": error,
                "elapsed_ms": round(elapsed_ms, 1),
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            status = "ERR" if error else "ok "
            print(f"[{n}/{len(cases)}] {status} {case['case_id']} {elapsed_ms:7.0f}ms")

    print(f"OK: {n} outputs written to {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MazuTalk baseline/모델 추론")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--eval", type=Path, default=C.PROCESSED_DIR / "eval_set.jsonl")
    parser.add_argument("--out", type=Path, default=C.PROCESSED_DIR / "baseline_outputs.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="앞에서부터 N개만 (0=전체)")
    parser.add_argument("--num-predict", type=int, default=512)
    args = parser.parse_args()

    return run(args.model, args.eval, args.out, args.limit, args.num_predict)


if __name__ == "__main__":
    raise SystemExit(main())
