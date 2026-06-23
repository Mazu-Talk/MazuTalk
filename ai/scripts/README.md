# Post-Training 스크립트

계획서 `docs/LLM_POST_TRAINING_PLAN.md` 의 파이프라인 구현. 모든 post-training
코드는 이 디렉터리에 있고, 탐색/오케스트레이션 노트북은 `ai/notebooks/` 에 있다.

## 역할 분담

| 단계 | 실행 위치 | 이유 |
|---|---|---|
| 데이터 생성, baseline 추론, 자동 평가 | **로컬 (Ollama)** | `qwen3.5:4b` 가 로컬 Ollama 에 있음 |
| QLoRA SFT, DPO, HF 추론, 병합 | **Colab/클라우드 GPU** | 로컬 GPU(4GB)·Python 3.14 로는 학습 불가 |

## 파일

| 파일 | Phase | 설명 |
|---|---|---|
| `common.py` | 공통 | SoT enum/contract, 프롬프트 로드, 시나리오→런타임 변환, Ollama 클라이언트, 출력 스키마, 금지표현, 전략 기대맵 |
| `build_eval_set.py` | 0 | frozen held-out 평가셋 생성 (`eval_set.jsonl`) |
| `run_baseline.py` | 0 | Ollama 로 baseline/모델 추론 → outputs jsonl |
| `evaluate.py` | 0·2·4 | 자동 지표 계산 (JSON·길이·단일질문·기술·전략·안전·금지표현·지연) |
| `build_sft_data.py` | 1 | teacher 로 SFT 데이터 합성 + 스키마/enum/한국어 검증 (eval 누수 제외) |
| `build_dpo_data.py` | 3 | chosen/rejected preference pair 생성 |
| `train_sft.py` | 2 | QLoRA SFT (GPU) |
| `train_dpo.py` | 4 | DPO (GPU, SFT 어댑터에서 출발) |
| `infer_hf.py` | 2·4 | transformers 추론 → 평가용 outputs (Colab 평가 루프) |
| `export_gguf.py` | 5 | LoRA 병합 → GGUF → Ollama Modelfile |
| `validate_scenario_schema.py` | 공통 | 시나리오 JSON 스키마 검증 (기존) |

## 실행 순서

### 로컬 (Python 3.14, `pip install jsonschema`)

```bash
# Phase 0
python ai/scripts/build_eval_set.py --per-scenario 3
python ai/scripts/run_baseline.py   --out ai/data/processed/baseline_outputs.jsonl
python ai/scripts/evaluate.py       --in  ai/data/processed/baseline_outputs.jsonl --csv ai/data/processed/baseline_eval.csv

# Phase 1·3 데이터 생성 (teacher 는 강할수록 좋음)
python ai/scripts/build_sft_data.py --teacher qwen3.5:4b --out ai/data/processed/sft_train.jsonl
python ai/scripts/build_dpo_data.py --teacher qwen3.5:4b --base qwen3.5:4b --out ai/data/processed/dpo_train.jsonl
```

### Colab GPU (`ai/notebooks/mazutalk_post_training.ipynb`)

1. `ai/configs/model.yaml` 의 `base_model` 을 실제 HF 체크포인트로 확정
2. `pip install -r ai/requirements-train.txt`
3. `train_sft.py` → `infer_hf.py` → `evaluate.py` (SFT 평가)
4. `train_dpo.py` → `infer_hf.py` → `evaluate.py` (DPO 평가)
5. `export_gguf.py` → Modelfile → `ollama create`

## 무결성 규칙 (계획서 §5)

- `eval_set.jsonl` 은 한 번 만들면 변경하지 않는다. baseline/SFT/DPO 모두 동일 셋으로 평가.
- 학습 데이터는 eval 조합을 제외해 누수를 막는다(`build_sft_data.py` 가 자동 처리).
- 추론은 `enable_thinking=false` + 고정 seed + 동일 샘플링으로 재현성 확보.
- system prompt 는 학습·서빙·평가 모두 `RP_system_prompt_runtime.md` 로 통일.

## 알려진 환경 이슈

- `qwen3.5:4b` 는 전체 `RP_system_prompt.md`(700줄) 에서 출력이 degenerate(`{` 만 출력)
  하므로, SoT 에서 파생한 축약본 `RP_system_prompt_runtime.md` 를 런타임 프롬프트로 사용한다.
- Qwen3 계열은 greedy(temperature 0) 에서 반복 degenerate → `temperature 0.7 + seed` 사용.
- 이 빌드의 `qwen3.5:4b` 는 한국어가 약하고 enum 을 임의 생성하는 경향 → post-training 의 핵심 개선 대상.
