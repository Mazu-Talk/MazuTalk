# STT Experiments

Whisper와 Faster-Whisper 기반 STT 실험을 위한 독립 모듈입니다.

## Directory Layout

```text
ai/stt/
├── configs/                 # STT 실험 설정 파일
├── data/
│   ├── raw/
│   │   ├── wav/             # AI Hub 원본 wav
│   │   └── labels/          # AI Hub 원본 json 라벨
│   └── processed/
│       ├── wav/             # 전처리된 STT 실험용 wav
│       └── metadata.csv     # STT 실험용 메타데이터
├── results/
│   ├── whisper/             # Whisper 실행 결과
│   ├── faster-whisper/      # Faster-Whisper 실행 결과
│   └── metrics/             # CER, 처리 시간 비교 결과
└── scripts/                 # 전처리, 추론, 평가 스크립트
```

## Data Policy

원천 wav, json 라벨, 전처리된 wav, metadata.csv, 모델 실행 결과는 용량과 라이선스 이슈를 피하기 위해 기본적으로 Git에 커밋하지 않습니다.

필요한 경우 `data/processed/metadata.csv`는 다음 형태를 기준으로 생성합니다.

```csv
audio_path,text,speaker_id,duration_sec,split
```

## STT Experiment Pipeline

이 파이프라인은 AI Hub 아동 음성 데이터의 라벨 JSON을 기반으로 Whisper / Faster-Whisper 비교 실험을 수행하기 위한 전처리 및 평가 코드입니다.

1. `build_dataset.py`
   - AI Hub 라벨 JSON에서 wav 파일명, 정답 문장, 화자 정보, 음성 길이, 발화 시작/종료 시점 등을 추출해 `metadata.csv`를 생성합니다.

2. `run_whisper.py`
   - `metadata.csv`의 `audio_path`를 기준으로 OpenAI Whisper 모델을 실행하고 전사 결과를 저장합니다.

3. `run_faster_whisper.py`
   - 동일한 음성 파일에 대해 Faster-Whisper 모델을 실행하고 전사 결과를 저장합니다.

4. `compare_stt.py`
   - 두 모델의 결과를 정답 문장과 비교하여 CER과 처리 시간을 기준으로 성능을 비교합니다.

초기 실험은 `small` 모델과 샘플 50개 기준으로 진행하고, 이후 데이터와 실행 환경이 준비되면 더 큰 모델과 더 많은 샘플로 확장합니다.

```bash
python ai/stt/scripts/build_dataset.py \
  --label-dir ai/data/raw/kor_free/labels \
  --audio-root ai/data/raw/kor_free/audio \
  --output ai/data/processed/stt/metadata.csv \
  --limit 50

python ai/stt/scripts/run_whisper.py \
  --metadata ai/data/processed/stt/metadata.csv \
  --output ai/stt/results/whisper_result.csv \
  --model small \
  --limit 50

python ai/stt/scripts/run_faster_whisper.py \
  --metadata ai/data/processed/stt/metadata.csv \
  --output ai/stt/results/faster_whisper_result.csv \
  --model small \
  --device cpu \
  --compute-type int8 \
  --limit 50

python ai/stt/scripts/compare_stt.py \
  --whisper ai/stt/results/whisper_result.csv \
  --faster-whisper ai/stt/results/faster_whisper_result.csv \
  --output ai/stt/results/stt_compare_result.csv
```
