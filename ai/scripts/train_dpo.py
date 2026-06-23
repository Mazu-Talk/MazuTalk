"""Phase 4: 소규모 DPO (GPU 필요 — Colab/클라우드에서 실행).

SFT 어댑터를 시작점으로 chosen/rejected 선호 정렬을 수행한다.
reference 모델 = 학습 전 SFT 가중치(DPOTrainer 기본 동작).

ai/data/processed/dpo_train.jsonl (system/prompt/chosen/rejected) 을 사용.

사용:
  python ai/scripts/train_dpo.py \
      --model-config ai/configs/model.yaml \
      --train-config ai/configs/dpo.yaml \
      --data ai/data/processed/dpo_train.jsonl \
      --sft-adapter ai/models/sft
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

import common as C


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> int:
    parser = argparse.ArgumentParser(description="DPO")
    parser.add_argument("--model-config", type=Path, default=C.CONFIG_DIR / "model.yaml")
    parser.add_argument("--train-config", type=Path, default=C.CONFIG_DIR / "dpo.yaml")
    parser.add_argument("--data", type=Path, default=C.PROCESSED_DIR / "dpo_train.jsonl")
    parser.add_argument("--sft-adapter", type=Path, default=Path("ai/models/sft"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    import torch
    from datasets import load_dataset
    from peft import PeftModel, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import DPOConfig, DPOTrainer

    mcfg = load_yaml(args.model_config)
    tcfg = load_yaml(args.train_config)
    out_dir = str(args.out or tcfg["output_dir"])

    # 학습 precision(fp16/bf16)과 4bit 연산 dtype를 일치시킨다 (T4는 fp16)
    compute_dtype = torch.bfloat16 if tcfg.get("bf16") else torch.float16
    bnb = BitsAndBytesConfig(
        load_in_4bit=mcfg.get("load_in_4bit", True),
        bnb_4bit_quant_type=mcfg.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=mcfg.get("bnb_4bit_use_double_quant", True),
    )

    tokenizer = AutoTokenizer.from_pretrained(
        mcfg["base_model"], revision=mcfg.get("revision"),
        trust_remote_code=mcfg.get("trust_remote_code", True),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base = AutoModelForCausalLM.from_pretrained(
        mcfg["base_model"], revision=mcfg.get("revision"),
        quantization_config=bnb, device_map="auto",
        torch_dtype=compute_dtype,
        trust_remote_code=mcfg.get("trust_remote_code", True),
    )
    base.config.use_cache = False
    base = prepare_model_for_kbit_training(base)
    # SFT 어댑터를 정책 시작점으로 로드 (학습 가능). 새 peft_config 를 추가하지 않는다.
    model = PeftModel.from_pretrained(base, str(args.sft_adapter), is_trainable=True)
    # 학습 가능한 LoRA 파라미터를 fp32 로 강제 → fp16 GradScaler 호환
    for p in model.parameters():
        if p.requires_grad:
            p.data = p.data.float()

    # system+prompt -> 템플릿 적용한 prompt 문자열로 변환
    def to_dpo(example):
        messages = [
            {"role": "system", "content": example["system"]},
            {"role": "user", "content": example["prompt"]},
        ]
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
        return {
            "prompt": prompt_text,
            "chosen": example["chosen"],
            "rejected": example["rejected"],
        }

    dataset = load_dataset("json", data_files=str(args.data), split="train")
    dataset = dataset.map(to_dpo, remove_columns=dataset.column_names)

    dpo_args = DPOConfig(
        output_dir=out_dir,
        seed=tcfg.get("seed", 42),
        beta=tcfg["beta"],
        learning_rate=float(tcfg["learning_rate"]),
        num_train_epochs=tcfg["num_train_epochs"],
        per_device_train_batch_size=tcfg["per_device_train_batch_size"],
        gradient_accumulation_steps=tcfg["gradient_accumulation_steps"],
        max_prompt_length=tcfg["max_prompt_length"],
        max_length=tcfg["max_length"],
        warmup_ratio=tcfg["warmup_ratio"],
        lr_scheduler_type=tcfg["lr_scheduler_type"],
        optim=tcfg["optim"],
        logging_steps=tcfg["logging_steps"],
        save_strategy=tcfg["save_strategy"],
        bf16=tcfg.get("bf16", False),
        fp16=tcfg.get("fp16", False),
        report_to="none",
    )

    # reference = 정책의 학습 전 복사본(어댑터 비활성). LoRA DPO 에서는 ref_model=None
    # 으로 두면 DPOTrainer 가 어댑터를 끈 base 를 reference 로 사용한다.
    trainer = DPOTrainer(
        model=model,                 # SFT 어댑터가 적용된 학습 가능 모델
        ref_model=None,              # 어댑터를 끈 base 가 reference 로 사용됨
        args=dpo_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"OK: DPO LoRA 어댑터 저장 -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
