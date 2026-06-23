# LLM Post-Training

마주톡(MazuTalk) 롤플레잉 챗봇용 LLM을 ASD 아동 대화 목적에 맞게 개선하기 위한
post-training(QLoRA SFT + 소규모 DPO) 모듈입니다. 전체 계획은
`docs/LLM_POST_TRAINING_PLAN.md`를 따릅니다.

기준 모델은 로컬 Ollama의 `qwen3.5:4b`(추론용)이며, 실제 학습은 대응하는 Hugging Face
instruct 체크포인트에 LoRA를 적용한 뒤 GGUF로 변환해 Ollama로 되돌립니다.

## Directory Layout

```
ai/
├── prompts/
│   ├── RP_system_prompt.md            # SoT: 행동 원칙·출력 스키마·안전 규칙 전문
│   └── RP_system_prompt_runtime.md    # SoT 파생 축약본 (학습·서빙·평가 공통 system prompt)
├── schemas/
│   ├── scenario_schema.json           # 시나리오 데이터 스키마
│   └── examples/
├── data/
│   ├── scenarios/                     # seed 시나리오 (4 카테고리 × 5 = 20개)
│   └── processed/                     # 평가셋·생성 데이터·추론/평가 산출물
├── configs/
│   ├── model.yaml                     # 기준 모델 + 4bit 양자화 설정
│   ├── sft.yaml                       # QLoRA SFT 하이퍼파라미터
│   └── dpo.yaml                       # DPO 하이퍼파라미터
├── scripts/                           # 전처리·생성·학습·평가·변환 스크립트
├── notebooks/
│   └── mazutalk_post_training.ipynb   # Colab GPU 오케스트레이션
├── models/                            # 학습 산출물(LoRA 어댑터·병합·GGUF)
├── requirements.txt                   # 로컬(데이터 생성·평가) 의존성
└── requirements-train.txt             # GPU 학습 의존성 (Colab)
```

## Data Policy

학습 산출물과 대용량/재생성 가능한 실행 결과는 용량·라이선스 이슈를 피하기 위해 기본적으로
Git에 커밋하지 않습니다.

- **커밋하지 않음**: `models/`(어댑터·GGUF), `data/processed/baseline_outputs.jsonl`,
  `*_outputs.jsonl`, `*_eval.csv`, `_smoke.*` 등 추론/평가 산출물
- **커밋함**: `data/processed/eval_set.jsonl`(frozen held-out 평가셋 — 비교 재현용),
  최종 학습 데이터(`sft_train.jsonl`, `dpo_train.jsonl`)는 소형이라 선택적으로 커밋
- 시나리오 seed(`data/scenarios/`)와 프롬프트·스키마·설정은 항상 커밋

## 환경 / 역할 분담

로컬 GPU(4GB) + Python 3.14 환경으로는 4B QLoRA 학습이 불가능해, 단계를 나눠 실행합니다.

| 단계 | 실행 위치 | 비고 |
|---|---|---|
| 데이터 생성 · baseline 추론 · 자동 평가 | **로컬 (Ollama / OpenAI)** | `requirements.txt`만 설치 |
| QLoRA SFT · DPO · HF 추론 · 병합 | **Colab/클라우드 GPU** | `requirements-train.txt` |

teacher(데이터 합성)는 백엔드를 선택합니다: `--backend openai`(권장, `gpt-4o-mini`,
`OPENAI_API_KEY` 필요) 또는 `--backend ollama`(로컬, 무료).

## Post-Training Pipeline

`docs/LLM_POST_TRAINING_PLAN.md`의 Phase 0~5를 구현한 스크립트입니다. 모든 코드는
`ai/scripts/`에, 탐색/오케스트레이션 노트북은 `ai/notebooks/`에 둡니다.

**common.py**

SoT(`RP_system_prompt.md`, `scenario_schema.json`)에서 파생한 enum/contract, 시나리오
→런타임 입력 변환, Ollama·OpenAI teacher 클라이언트, 출력 JSON 스키마, 금지 표현,
코칭 전략 기대맵을 한곳에 모은 공용 모듈입니다.

**build_eval_set.py**

seed 시나리오 × (감정 상태 × 발화 유형) 조합 + 안전 케이스를 결정적으로 생성해 frozen
held-out 평가셋(`eval_set.jsonl`)을 만듭니다. 한 번 만든 뒤에는 baseline/SFT/DPO 비교를
위해 변경하지 않습니다.

**run_baseline.py**

평가셋을 기준으로 모델(기본 `qwen3.5:4b`)을 로컬 Ollama로 추론해 원시 출력을 저장합니다.
thinking 비활성화·고정 seed로 재현성을 확보합니다.

**evaluate.py**

추론 출력(jsonl)에서 정량 지표를 계산합니다: JSON 스키마 준수율, 응답 길이/단일 질문
준수율, 사회성 기술 적합도, 코칭 전략 적합도, 안전 recall·오탐율, 금지 표현 위반율,
응답 지연(p50/p90).

**build_sft_data.py**

teacher로 SoT 준수 응답을 합성해 SFT 데이터를 만듭니다. 출력 스키마/enum/한국어/금지표현
검증을 통과한 것만 채택하고, 평가셋에 쓰인 조합은 제외(누수 방지)합니다. `--ages`로
나이(5~8) 변주를 주어 볼륨을 확장합니다.

**build_dpo_data.py**

`chosen`(teacher의 SoT 준수 응답) / `rejected`(약한 base 모델의 실제 출력 또는 규칙 위반
변형) preference 쌍을 만듭니다. 안전 케이스는 위험 flag 누락을 rejected로 둡니다.

**train_sft.py** / **train_dpo.py** *(GPU)*

`sft_train.jsonl`로 base instruct 모델에 4-bit QLoRA SFT를 수행하고, DPO는 SFT 어댑터를
시작점(policy)으로, 어댑터를 끈 base를 reference로 선호 정렬합니다.

**infer_hf.py** *(GPU)*

학습한 모델(어댑터/병합)로 평가셋을 추론해 `evaluate.py`가 소비할 출력을 만듭니다.
Colab에서 Ollama 없이 SFT/DPO 모델을 평가할 수 있게 합니다.

**export_gguf.py** *(GPU)*

LoRA를 병합하고 GGUF로 변환·양자화(Q4_K_M)한 뒤 Ollama Modelfile을 생성합니다.

## 실행

### 로컬 — Phase 0 (baseline) · Phase 1·3 (데이터)

```bash
pip install -r ai/requirements.txt

# Phase 0: 평가셋 동결 → baseline 추론 → 자동 평가
python ai/scripts/build_eval_set.py --per-scenario 3
python ai/scripts/run_baseline.py   --out ai/data/processed/baseline_outputs.jsonl
python ai/scripts/evaluate.py       --in ai/data/processed/baseline_outputs.jsonl \
                                    --csv ai/data/processed/baseline_eval.csv

# Phase 1: SFT 데이터 (OpenAI teacher, 나이 변주)
export OPENAI_API_KEY=sk-...
python ai/scripts/build_sft_data.py --backend openai --per-scenario 9 --ages 5,6,7,8 \
                                    --out ai/data/processed/sft_train.jsonl

# Phase 3: DPO 데이터 (chosen=OpenAI, rejected=약한 qwen)
python ai/scripts/build_dpo_data.py --teacher-backend openai --base qwen3.5:4b \
                                    --out ai/data/processed/dpo_train.jsonl
```

### Colab GPU — Phase 2·4·5 (학습·평가·변환)

`ai/notebooks/mazutalk_post_training.ipynb` 참고. 요약:

```bash
pip install -r ai/requirements-train.txt

# Phase 2: QLoRA SFT → 평가
python ai/scripts/train_sft.py --data ai/data/processed/sft_train.jsonl --out ai/models/sft
python ai/scripts/infer_hf.py  --adapter ai/models/sft --out ai/data/processed/sft_outputs.jsonl
python ai/scripts/evaluate.py  --in ai/data/processed/sft_outputs.jsonl --csv ai/data/processed/sft_eval.csv

# Phase 4: DPO → 평가
python ai/scripts/train_dpo.py --data ai/data/processed/dpo_train.jsonl --sft-adapter ai/models/sft --out ai/models/dpo
python ai/scripts/infer_hf.py  --adapter ai/models/dpo --out ai/data/processed/dpo_outputs.jsonl
python ai/scripts/evaluate.py  --in ai/data/processed/dpo_outputs.jsonl --csv ai/data/processed/dpo_eval.csv

# Phase 5: 병합 → GGUF → Modelfile → Ollama 등록
python ai/scripts/export_gguf.py --adapter ai/models/dpo --llama-cpp llama.cpp --quant Q4_K_M
```

## Baseline 결과

`qwen3.5:4b`(축약 런타임 프롬프트, frozen 평가셋 70 케이스 = 역할극 60 + 안전 10) 기준
자동 평가 결과입니다. post-training의 개선 대상을 정량화한 출발점입니다.

| 지표 | baseline | 목표 | 평가 |
|---|---:|---:|---|
| JSON 파싱 성공률 | 97.1% | — | 양호 |
| **JSON 스키마 준수율** | **68.6%** | 98% | enum 임의생성으로 큰 격차 |
| 응답 길이 준수율 | 93.1% | 90% | 이미 충족 |
| 단일 질문 준수율 | 91.2% | 90% | 이미 충족 |
| **사회성 기술 적합도** | **41.4%** | 85% | 최대 개선 대상 |
| 코칭 전략 적합도 | 65.5% | 80% | 개선 필요 |
| **안전 recall** | **80.0%** | 95% | 위험 누락 존재 |
| 성인 개입 recall | 66.7% | — | 개선 필요 |
| 안전 오탐율 | 3.4% | 낮을수록 | 양호 |
| 금지 표현 위반율 | 0.0% | ≤1% | 충족 |
| 응답 지연 p50 / p90 | 53s / 63s | 3s / 5s | 로컬 4GB·CPU 한계(배포 HW와 별개) |

**해석**: 길이·단일질문·금지표현은 이미 목표를 만족하지만, **스키마 준수(enum)·사회성 기술
적합도·안전 recall**이 크게 부족합니다. SFT/DPO의 핵심 목표는 이 세 지표를 끌어올리는 것입니다.

## 평가 무결성 · 알려진 이슈

- `eval_set.jsonl`은 한 번 동결하면 변경하지 않고, baseline/SFT/DPO를 같은 셋으로 평가합니다.
  학습 데이터 생성에서 평가 조합을 제외해 누수를 막습니다.
- 추론은 전 구간 `enable_thinking=false` + 고정 seed로 재현성을 확보합니다.
- `qwen3.5:4b`는 전체 `RP_system_prompt.md`(700줄)에서 출력이 degenerate(`{`만 출력)하여,
  SoT 파생 축약본 `RP_system_prompt_runtime.md`를 학습·서빙·평가 공통 프롬프트로 사용합니다.
- Qwen3 계열은 greedy(temperature 0)에서 반복 degenerate → `temperature 0.7 + seed`를 사용합니다.
- seed 시나리오가 4개 카테고리 20개에 한정되어 16개 사회성 기술 전체 커버리지는 부족합니다
  (합성으로 보완, 시나리오 확장이 후속 과제).
