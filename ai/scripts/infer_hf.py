"""transformers 기반 추론 (GPU — Colab/클라우드).

학습한 모델(base + LoRA 어댑터, 또는 병합 모델)로 frozen 평가셋에 대해 응답을
생성하고 run_baseline.py 와 동일한 출력 형식(jsonl)으로 저장한다.
이렇게 하면 Colab에서 Ollama 없이도 evaluate.py 로 SFT/DPO 모델을 평가할 수 있다.

사용:
  python ai/scripts/infer_hf.py --adapter ai/models/sft --out ai/data/processed/sft_outputs.jsonl
  python ai/scripts/evaluate.py --in ai/data/processed/sft_outputs.jsonl --csv ai/data/processed/sft_eval.csv
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml

import common as C


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> int:
    parser = argparse.ArgumentParser(description="HF 추론 -> 평가용 출력")
    parser.add_argument("--model-config", type=Path, default=C.CONFIG_DIR / "model.yaml")
    parser.add_argument("--adapter", type=Path, default=None, help="LoRA 어댑터 경로(없으면 base)")
    parser.add_argument("--merged", type=Path, default=None, help="병합 모델 경로(있으면 우선)")
    parser.add_argument("--eval", type=Path, default=C.PROCESSED_DIR / "eval_set.jsonl")
    parser.add_argument("--out", type=Path, default=C.PROCESSED_DIR / "sft_outputs.jsonl")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--num-predict", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=C.DEFAULT_SEED,
                        help="샘플링 재현성을 위한 기본 seed. 케이스별로 seed+index 를 사용.")
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed

    set_seed(args.seed)

    mcfg = load_yaml(args.model_config)
    src = str(args.merged) if args.merged else mcfg["base_model"]

    tokenizer = AutoTokenizer.from_pretrained(
        src, revision=None if args.merged else mcfg.get("revision"),
        trust_remote_code=mcfg.get("trust_remote_code", True),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    load_kwargs = dict(device_map="auto", trust_remote_code=mcfg.get("trust_remote_code", True))
    if not args.merged and mcfg.get("load_in_4bit", True):
        # T4 안전: 추론도 float16 기본 (bf16은 T4에서 느리고 일부 op 미지원)
        compute_dtype = getattr(torch, mcfg.get("bnb_4bit_compute_dtype", "float16"))
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type=mcfg.get("bnb_4bit_quant_type", "nf4"),
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=mcfg.get("bnb_4bit_use_double_quant", True),
        )
    else:
        load_kwargs["dtype"] = torch.float16

    model = AutoModelForCausalLM.from_pretrained(
        src, revision=None if args.merged else mcfg.get("revision"), **load_kwargs,
    )
    if args.adapter and not args.merged:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(args.adapter))
    model.eval()

    system_prompt = C.load_system_prompt(runtime=True)
    cases = C.read_jsonl(args.eval)
    if args.limit > 0:
        cases = cases[: args.limit]

    # Qwen 계열 thinking 비활성화: apply_chat_template enable_thinking=False 지원 시 사용
    def build_inputs(user_content: str):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        return tokenizer(text, return_tensors="pt").to(model.device)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with args.out.open("w", encoding="utf-8") as fh:
        for case_idx, case in enumerate(cases):
            user_content = json.dumps(case["input"], ensure_ascii=False)
            set_seed(args.seed + case_idx)
            t0 = time.perf_counter()
            raw = ""
            error = None
            try:
                inputs = build_inputs(user_content)
                with torch.no_grad():
                    gen = model.generate(
                        **inputs, max_new_tokens=args.num_predict,
                        do_sample=True, temperature=0.7, top_p=0.8, top_k=20,
                        pad_token_id=tokenizer.pad_token_id,
                    )
                out_ids = gen[0][inputs["input_ids"].shape[1]:]
                raw = tokenizer.decode(out_ids, skip_special_tokens=True)
            except Exception as exc:  # noqa: BLE001 - 케이스별 실패를 기록하고 계속
                error = str(exc)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            fh.write(json.dumps({
                "case_id": case["case_id"], "kind": case["kind"],
                "expected": case["expected"], "raw_output": raw,
                "error": error, "elapsed_ms": round(elapsed_ms, 1),
            }, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            status = "ERR" if error else "ok "
            print(f"[{n}/{len(cases)}] {status} {case['case_id']} {elapsed_ms:.0f}ms")

    print(f"OK: {n} outputs -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
