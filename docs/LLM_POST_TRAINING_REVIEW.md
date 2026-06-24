# LLM Post-Training 검토 결과

검토 일자: 2026-06-24  
검토 범위: `docs/LLM_POST_TRAINING_PLAN.md`, `ai/scripts/`, `ai/configs/`, `ai/notebooks/mazutalk_post_training.ipynb`, `ai/data/processed/*.jsonl`

## 요약

post-training 파이프라인은 SFT/DPO 학습, HF 추론, 평가, GGUF 변환까지 기본 흐름이 갖춰져 있다. 스크립트 문법 검증과 노트북 JSON 검증은 통과했고, 현재 SFT/DPO 데이터의 chosen/assistant JSON schema도 통과한다.

다만 재학습/재평가 전에 반드시 정리해야 할 문제가 있다.

1. DPO 안전 응답 다양화가 코드와 데이터에 실질 반영되지 않았다.
2. DPO roleplay prompt 일부가 eval prompt와 정확히 겹친다.
3. safety recall 평가가 위험 유형 정확도를 보지 않아 점수를 과대평가할 수 있다.

## High Priority

### 1. DPO 안전 chosen 메시지가 단일 문장으로 고정됨

관련 파일:

- `ai/scripts/build_dpo_data.py`
  - `SAFE_MESSAGES` import: line 25
  - `safety_chosen()`: line 69
  - 안전 pair 생성: line 171, line 178

현재 `build_dpo_data.py`는 `SAFE_MESSAGES`를 import하지만 실제로 사용하지 않는다. `safety_chosen()`의 `child_message`는 아래 한 문장으로 고정되어 있다.

```text
지금은 가까운 어른에게 바로 말하자. 선생님이나 보호자에게 같이 가자.
```

실제 데이터 확인 결과:

- `ai/data/processed/dpo_train.jsonl`
- safety pair: 24개
- safety chosen unique message: 1개

영향:

- SFT에서는 안전 응답을 6개 메시지로 회전시키지만, DPO에서 다시 단일 안전 문장을 선호하도록 학습시킬 수 있다.
- PR #45의 “DPO 안전 응답도 다양화” 피드백이 실질적으로 해결되지 않는다.

권장 조치:

- `safety_chosen()`이 `message`를 인자로 받도록 바꾸고, safety pair 생성 시 `SAFE_MESSAGES[k % len(SAFE_MESSAGES)]` 또는 age/index 기반 회전을 적용한다.
- 가능하면 `build_sft_data.py`의 `_safety_response()`를 공개 함수로 바꾸어 SFT/DPO가 같은 응답 구조를 재사용하게 한다.
- 변경 후 `dpo_train.jsonl`을 재생성한다.

### 2. DPO 데이터에 eval prompt 누수가 있음

관련 파일:

- `ai/scripts/build_sft_data.py`
  - eval 조합 제외: line 180, line 199
- `ai/scripts/build_dpo_data.py`
  - DPO roleplay 생성: line 93, line 108

SFT 생성기는 eval 조합을 제외하지만, DPO 생성기는 eval 제외 로직 없이 `ROLEPLAY_CASES`를 그대로 사용한다.

실제 데이터 확인 결과:

- SFT와 eval exact prompt overlap: 0건
- DPO와 eval exact prompt overlap: 7건
- 겹친 eval case id:
  - `rp_0004`
  - `rp_0026`
  - `rp_0027`
  - `rp_0031`
  - `rp_0053`
  - `rp_0054`
  - `rp_0058`

영향:

- DPO 후 평가 점수가 held-out 성능을 과대평가할 수 있다.
- 계획서의 frozen held-out / 누수 금지 원칙과 맞지 않는다.

권장 조치:

- `build_dpo_data.py`도 `--eval` 인자를 받고, SFT와 같은 방식으로 `(scenario_id, emotion_state, utterance_type)` 조합을 제외한다.
- 더 안전하게는 canonical JSON prompt 기준 exact overlap 검사를 데이터 생성 후 검증 단계에 추가한다.

### 3. safety recall이 risk type 정확도를 평가하지 않음

관련 파일:

- `ai/scripts/evaluate.py`
  - safety flag count: line 121, line 128
  - adult recall: line 132
  - summary: line 154

현재 safety recall은 아래 조건만 본다.

```python
saf.get("risk_flag", "none") != "none"
```

따라서 `self_harm` 케이스를 `distress`로 잘못 분류해도 safety recall에는 성공으로 포함된다.

영향:

- 위험 유형별 대응 성능을 과대평가할 수 있다.
- 계획서의 “`risk_flag`와 `requires_adult_attention`을 올바르게 설정” 목표와 다르다.

권장 조치:

- `risk_flag == expected["risk_flag"]` 기준의 `safety_risk_type_accuracy` 또는 엄격한 `safety_recall`을 추가한다.
- 기존 “non-none 감지율”은 별도 지표인 `safety_detection_rate`로 분리한다.
- adult flag도 expected 값과 정확히 일치하는지 별도 계산한다.

## Medium Priority

### 4. privacy 안전 케이스가 학습/평가에서 빠져 있음

관련 파일:

- `ai/scripts/common.py`
  - `RISK_FLAGS`: line 73
- `ai/scripts/build_eval_set.py`
  - `SAFETY_CASES`: line 33
- `ai/scripts/build_sft_data.py`
  - `SAFETY_TRAIN`: line 41

`privacy`는 enum과 계획서에는 포함되어 있지만, 현재 eval 안전셋과 SFT 안전셋에는 없다.

영향:

- 아동 개인정보 노출 상황을 학습/검증하지 못한다.
- 서비스 안전 요구사항 중 개인정보 보호 대응이 비어 있다.

권장 조치:

- eval에는 held-out privacy 케이스를 추가한다.
- SFT/DPO에는 eval 표현과 겹치지 않는 privacy 학습 케이스를 추가한다.
- 예: 주소, 전화번호, 학교/반, 이름, 비밀번호 공유 요청/발화.

주의:

- 이미 baseline/SFT/DPO 비교에 사용한 frozen eval을 바꾸면 기존 결과와 직접 비교가 어려워진다.
- 변경 시 eval version을 명시하거나 새 evaluation set으로 재측정한다.

### 5. DPO 안전 pair가 `--max`에 의해 쉽게 잘림

관련 파일:

- `ai/scripts/build_dpo_data.py`
  - safety pair loop: line 171
  - `max_pairs` 중단: line 172

현재 DPO는 roleplay pair를 먼저 만들고, 이후 safety pair를 추가한다. 전체 row 수가 `max_pairs`에 도달하면 safety pair가 잘린다.

실제 데이터 확인 결과:

- `dpo_train.jsonl`: 총 84 rows
- roleplay: 60
- safety: 24
- `SAFETY_TRAIN`: 40 cases

영향:

- 안전 recall 회복 목적과 달리 DPO 안전 pair가 충분히 들어가지 않을 수 있다.

권장 조치:

- `--max-roleplay`, `--max-safety`를 분리한다.
- 또는 safety pair를 먼저 생성하고 남은 budget을 roleplay에 배정한다.

### 6. HF 평가 추론이 재현 가능하지 않음

관련 파일:

- `ai/scripts/infer_hf.py`
  - `model.generate(...)`: line 103
  - `do_sample=True`: line 105

HF 평가 추론은 sampling을 사용하지만 `torch.manual_seed`, `transformers.set_seed`, `generator`를 설정하지 않는다.

영향:

- 같은 checkpoint라도 평가 실행마다 점수가 흔들릴 수 있다.
- 계획서의 “고정 seed + 동일 샘플링” 전제와 맞지 않는다.

권장 조치:

- `--seed` 인자를 추가하고 `transformers.set_seed(args.seed)` 또는 `torch.Generator(device=model.device).manual_seed(args.seed)`를 사용한다.
- case별 seed를 `DEFAULT_SEED + index`처럼 고정하면 재현성과 케이스 다양성을 동시에 확보할 수 있다.

### 7. social skill 커버리지가 16개 중 6개에 집중됨

현재 SFT 데이터의 `target_skill` 분포:

| skill | count |
|---|---:|
| conflict_resolution | 120 |
| emotion_expression | 119 |
| greeting | 96 |
| requesting_help | 72 |
| refusal | 47 |
| goodbye | 24 |

영향:

- 계획서의 16개 social skill 목표 대비 미커버 skill은 학습 효과를 기대하기 어렵다.
- 평가가 현재 seed scenario 범위에만 머물면 전체 제품 목표 달성을 과대평가할 수 있다.

권장 조치:

- 부족 skill에 대한 synthetic scenario seed를 추가한다.
- skill별 최소 turn 수를 데이터 생성 후 검증하는 스크립트를 추가한다.

## Security / Supply Chain

### 8. HF 모델 revision이 고정되지 않았고 remote code를 신뢰함

관련 파일:

- `ai/configs/model.yaml`
  - `base_model`: line 10
  - `revision: null`: line 11
  - `trust_remote_code: true`: line 12

영향:

- 같은 학습 명령이 나중에 다른 모델 코드/가중치를 사용할 수 있다.
- `trust_remote_code: true`는 원격 저장소 코드를 실행하므로 revision pin 없이 쓰면 공급망 리스크가 커진다.

권장 조치:

- HF model revision을 commit hash로 고정한다.
- 해당 모델에 remote code가 꼭 필요한지 확인하고, 가능하면 `trust_remote_code: false`로 낮춘다.

### 9. 학습 의존성이 range spec으로만 고정됨

관련 파일:

- `ai/requirements-train.txt`
  - `transformers>=4.44`
  - `peft>=0.12`
  - `trl>=0.10`

영향:

- Colab 실행 시점에 따라 TRL/Transformers API가 달라질 수 있다.
- 이미 `DPOConfig` 호환성 방어 코드가 필요한 상태라, 결과 재현성이 낮다.

권장 조치:

- 검증된 Colab 조합을 exact pin 또는 upper bound 포함으로 고정한다.
- 예: `transformers==...`, `trl==...`, `peft==...`, `bitsandbytes==...`.

### 10. llama.cpp clone이 commit pin 없이 main을 사용함

관련 파일:

- `ai/notebooks/mazutalk_post_training.ipynb`
  - `git clone https://github.com/ggerganov/llama.cpp`

영향:

- GGUF 변환 결과와 CLI 동작이 시점에 따라 바뀔 수 있다.

권장 조치:

- 검증된 llama.cpp commit으로 checkout한다.
- notebook에 commit hash를 명시한다.

## 검증 결과

명령:

```bash
python -m py_compile ai/scripts/common.py ai/scripts/build_eval_set.py ai/scripts/build_sft_data.py ai/scripts/build_dpo_data.py ai/scripts/run_baseline.py ai/scripts/infer_hf.py ai/scripts/evaluate.py ai/scripts/train_sft.py ai/scripts/train_dpo.py ai/scripts/export_gguf.py
python -c "import json; json.load(open('ai/notebooks/mazutalk_post_training.ipynb', encoding='utf-8')); print('notebook json ok')"
```

결과:

- post-training scripts compile: pass
- notebook JSON parse: pass

데이터 검증:

| file | rows | result |
|---|---:|---|
| `ai/data/processed/eval_set.jsonl` | 70 | roleplay 60, safety 10 |
| `ai/data/processed/sft_train.jsonl` | 558 | roleplay 478, safety 80, assistant schema bad 0 |
| `ai/data/processed/dpo_train.jsonl` | 84 | roleplay 60, safety 24, chosen schema bad 0 |

추가 확인:

- SFT safety unique message: 6
- DPO safety chosen unique message: 1
- SFT/eval exact prompt overlap: 0
- DPO/eval exact prompt overlap: 7
- DPO rejected unparseable JSON: 15

## 권장 수정 순서

1. DPO safety chosen에서 `SAFE_MESSAGES` 회전 적용.
2. DPO 생성기에 eval 제외 로직 추가.
3. `evaluate.py`의 safety 지표를 detection/type/adult로 분리.
4. privacy 안전 케이스를 eval/train에 추가하고 eval version을 명시.
5. DPO roleplay/safety budget 분리.
6. HF inference seed 고정.
7. HF model revision, Python dependency, llama.cpp commit pinning.
8. skill coverage 검증 및 부족 skill 데이터 보강.

