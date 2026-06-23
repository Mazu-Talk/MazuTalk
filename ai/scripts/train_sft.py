"""Phase 2: QLoRA SFT (GPU 필요 — Colab/클라우드에서 실행).

ai/data/processed/sft_train.jsonl (messages 형식) 으로 base instruct 모델에
4-bit QLoRA SFT 를 수행하고 LoRA 어댑터를 저장한다.

로컬(4GB VRAM, Python 3.14)에서는 실행 불가. requirements-train.txt 설치된
GPU 환경에서 실행할 것.

사용:
  python ai/scripts/train_sft.py \
      --model-config ai/configs/model.yaml \
      --train-config ai/configs/sft.yaml \
      --data ai/data/processed/sft_train.jsonl
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
    parser = argparse.ArgumentParser(description="QLoRA SFT")
    parser.add_argument("--model-config", type=Path, default=C.CONFIG_DIR / "model.yaml")
    parser.add_argument("--train-config", type=Path, default=C.CONFIG_DIR / "sft.yaml")
    parser.add_argument("--data", type=Path, default=C.PROCESSED_DIR / "sft_train.jsonl")
    parser.add_argument("--out", type=Path, default=None, help="어댑터 출력 디렉터리(미지정 시 config)")
    args = parser.parse_args()

    # 무거운 의존성은 GPU 환경에서만 import
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
    )
    from trl import SFTConfig, SFTTrainer

    mcfg = load_yaml(args.model_config)
    tcfg = load_yaml(args.train_config)
    out_dir = str(args.out or tcfg["output_dir"])

    # 학습 precision(fp16/bf16)과 4bit 연산 dtype를 일치시킨다.
    # (불일치 시 fp16 GradScaler가 bf16 그래디언트를 못 다뤄 학습이 깨짐 — T4는 fp16)
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

    model = AutoModelForCausalLM.from_pretrained(
        mcfg["base_model"], revision=mcfg.get("revision"),
        quantization_config=bnb, device_map={"": 0},
        dtype=compute_dtype,         # base·LoRA 를 의도한 dtype 로 로드 (torch_dtype 은 deprecated)
        trust_remote_code=mcfg.get("trust_remote_code", True),
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=tcfg["lora_rank"], lora_alpha=tcfg["lora_alpha"],
        lora_dropout=tcfg["lora_dropout"], bias="none", task_type="CAUSAL_LM",
        target_modules=tcfg["lora_target_modules"],
    )
    model = get_peft_model(model, peft_config)
    # 학습 가능한 LoRA 파라미터를 fp32 로 강제 → fp16 GradScaler 호환.
    # (base 가 bf16 로 저장돼 있어도 grad 가 fp32 가 되어 unscale 오류가 사라짐)
    for p in model.parameters():
        if p.requires_grad:
            p.data = p.data.float()

    # messages 형식 -> SFTTrainer 가 chat template 로 자동 포맷
    dataset = load_dataset("json", data_files=str(args.data), split="train")

    sft_kwargs = dict(
        output_dir=out_dir,
        seed=tcfg.get("seed", 42),
        learning_rate=float(tcfg["learning_rate"]),
        num_train_epochs=tcfg["num_train_epochs"],
        per_device_train_batch_size=tcfg["per_device_train_batch_size"],
        gradient_accumulation_steps=tcfg["gradient_accumulation_steps"],
        warmup_ratio=tcfg["warmup_ratio"],
        weight_decay=tcfg.get("weight_decay", 0.0),
        lr_scheduler_type=tcfg["lr_scheduler_type"],
        optim=tcfg["optim"],
        logging_steps=tcfg["logging_steps"],
        save_strategy=tcfg["save_strategy"],
        bf16=tcfg.get("bf16", False),
        fp16=tcfg.get("fp16", False),
        report_to="none",
    )
    # TRL 버전별 시퀀스 길이 파라미터명 호환 (구: max_seq_length / 신: max_length)
    _sft_fields = getattr(SFTConfig, "__dataclass_fields__", {})
    if "max_seq_length" in _sft_fields:
        sft_kwargs["max_seq_length"] = tcfg["max_seq_length"]
    elif "max_length" in _sft_fields:
        sft_kwargs["max_length"] = tcfg["max_seq_length"]
    sft_args = SFTConfig(**sft_kwargs)

    trainer = SFTTrainer(
        model=model,                 # 이미 peft 적용된 모델 (peft_config 중복 전달 금지)
        args=sft_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"OK: SFT LoRA 어댑터 저장 -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
