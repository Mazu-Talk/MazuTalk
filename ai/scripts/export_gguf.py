"""Phase 5: LoRA 병합 -> HF 저장 -> GGUF 변환 -> Ollama Modelfile.

1) base + (SFT|DPO) LoRA 어댑터 병합 후 HF 형식으로 저장
2) llama.cpp 의 convert_hf_to_gguf.py 로 GGUF 변환 (llama.cpp 경로 필요)
3) Q4_K_M/Q5_K_M 양자화
4) Ollama Modelfile 작성 -> `ollama create mazutalk-qwen-roleplay -f Modelfile`

GPU 환경에서 병합까지 수행. GGUF 변환은 llama.cpp 가 있으면 자동, 없으면
명령만 출력한다.

사용:
  python ai/scripts/export_gguf.py --adapter ai/models/dpo --llama-cpp /path/to/llama.cpp
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import yaml

import common as C


os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")


MODELFILE_TEMPLATE = '''FROM ./{gguf_name}

# 서빙 기본값 — 학습/평가와 동일 조건 (Qwen3 비-thinking 권장 샘플링)
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER num_predict 1024

# thinking 비활성화 (JSON-only 안정화)
PARAMETER think false

SYSTEM """{system}"""
'''


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> int:
    parser = argparse.ArgumentParser(description="LoRA 병합 + GGUF + Modelfile")
    parser.add_argument("--model-config", type=Path, default=C.CONFIG_DIR / "model.yaml")
    parser.add_argument("--adapter", type=Path, default=Path("ai/models/dpo"))
    parser.add_argument("--merged-out", type=Path, default=Path("ai/models/merged"))
    parser.add_argument("--gguf-out", type=Path, default=Path("ai/models/gguf"))
    parser.add_argument("--llama-cpp", type=Path, default=None, help="llama.cpp 저장소 경로")
    parser.add_argument("--quant", default="Q4_K_M")
    parser.add_argument("--model-name", default="mazutalk-qwen-roleplay")
    parser.add_argument("--skip-merge", action="store_true",
                        help="이미 생성된 merged-out 을 사용하고 LoRA 병합을 건너뜀")
    args = parser.parse_args()

    mcfg = load_yaml(args.model_config)

    # 1) 병합
    if args.skip_merge:
        if not args.merged_out.exists():
            raise FileNotFoundError(f"--skip-merge 사용 시 merged-out 이 필요합니다: {args.merged_out}")
        print(f"[1/4] base + adapter 병합 건너뜀 -> {args.merged_out}")
    else:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print("[1/4] base + adapter 병합 ...")
        tokenizer = AutoTokenizer.from_pretrained(
            mcfg["base_model"], revision=mcfg.get("revision"),
            trust_remote_code=mcfg.get("trust_remote_code", True),
        )
        base = AutoModelForCausalLM.from_pretrained(
            mcfg["base_model"], revision=mcfg.get("revision"),
            dtype=torch.float16, device_map="cpu",
            trust_remote_code=mcfg.get("trust_remote_code", True),
        )
        merged = PeftModel.from_pretrained(base, str(args.adapter)).merge_and_unload()
        args.merged_out.mkdir(parents=True, exist_ok=True)
        merged.save_pretrained(str(args.merged_out))
        tokenizer.save_pretrained(str(args.merged_out))
        print(f"   병합 모델 저장 -> {args.merged_out}")

    # 2) GGUF 변환
    args.gguf_out.mkdir(parents=True, exist_ok=True)
    f16_path = args.gguf_out / "model-f16.gguf"
    quant_name = f"model-{args.quant}.gguf"
    quant_path = args.gguf_out / quant_name

    if args.llama_cpp and args.llama_cpp.exists():
        print("[2/4] GGUF(f16) 변환 ...")
        subprocess.run([
            "python", str(args.llama_cpp / "convert_hf_to_gguf.py"),
            str(args.merged_out), "--outfile", str(f16_path), "--outtype", "f16",
        ], check=True)
        print(f"[3/4] {args.quant} 양자화 ...")
        quantize_bin = args.llama_cpp / "llama-quantize"
        subprocess.run([str(quantize_bin), str(f16_path), str(quant_path), args.quant], check=True)
    else:
        print("[2-3/4] llama.cpp 경로 미지정 — 아래 명령을 GPU 환경에서 수동 실행:")
        print(f"  python <llama.cpp>/convert_hf_to_gguf.py {args.merged_out} "
              f"--outfile {f16_path} --outtype f16")
        print(f"  <llama.cpp>/llama-quantize {f16_path} {quant_path} {args.quant}")

    # 4) Modelfile
    print("[4/4] Ollama Modelfile 작성 ...")
    system_prompt = C.load_system_prompt(runtime=True).replace('"""', "'''")
    modelfile = MODELFILE_TEMPLATE.format(gguf_name=quant_name, system=system_prompt)
    mf_path = args.gguf_out / "Modelfile"
    mf_path.write_text(modelfile, encoding="utf-8")
    print(f"   Modelfile -> {mf_path}")
    print(f"\n다음 명령으로 Ollama 등록:")
    print(f"  cd {args.gguf_out} && ollama create {args.model_name} -f Modelfile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
