# Whisper vs Faster-Whisper Experiment

## 1. Prepare Test Data

`ai/stt/data/processed/metadata.csv`는 같은 음성 파일과 같은 정답 문장을 두 모델에 모두 사용합니다.

```csv
audio_path,text,speaker_id,duration_sec,split
ai/stt/data/processed/wav/sample.wav,정답 문장,speaker_001,3.2,test
```

비교용 wav는 가능하면 다음 기준으로 통일합니다.

- mono
- 16 kHz
- wav
- 너무 짧거나 무음이 많은 파일 제외
- 같은 `test` split만 평가에 사용

## 2. Run Both Models Under Same Conditions

정확도 비교는 같은 모델 크기부터 시작합니다.

- Whisper: `small`, `medium` 등
- Faster-Whisper: 같은 크기의 `small`, `medium` 등
- language: `ko`
- beam size: 같은 값으로 시작, 예: `5`
- 첫 실행의 모델 다운로드 시간은 처리 시간에서 제외

속도 비교는 실제 사용할 설정도 별도로 기록합니다.

- Whisper CPU 기준
- Faster-Whisper CPU `compute_type=int8` 기준

## 3. Save Prediction Results

각 모델 결과는 파일 단위로 저장합니다.

```csv
audio_path,reference,prediction,duration_sec,elapsed_sec,rtf
```

`rtf`는 `elapsed_sec / duration_sec`입니다. 1보다 작으면 실제 재생시간보다 빠르게 처리한 것입니다.

## 4. Evaluate

CER은 최소 두 가지를 같이 봅니다.

- `cer_raw`: 원문 그대로 비교
- `cer_normalized`: 공백, 일부 문장부호, 반복 공백 등을 정규화한 뒤 비교

최종 비교 표에는 다음 값을 둡니다.

```csv
engine,model_size,cer_raw,cer_normalized,total_audio_sec,total_elapsed_sec,avg_rtf
```

## 5. Recommended Order

1. 작은 샘플 10개로 파이프라인이 도는지 확인
2. `small` 모델로 Whisper와 Faster-Whisper 결과 비교
3. 문제 없으면 100개 이상으로 확장
4. `medium` 이상 모델에서 정확도 개선 대비 처리 시간 증가 확인
5. CER이 높은 케이스를 따로 모아 라벨 오류, 잡음, 발화 길이, 화자 특성을 확인

## 6. Commands

프로젝트 루트에서 가상환경을 활성화합니다.

```bash
source .venv/bin/activate
```

AI Hub 원본 파일을 아래 위치에 둡니다.

```text
ai/stt/data/raw/wav/
ai/stt/data/raw/labels/
```

wav 파일명과 json 파일명은 확장자를 제외한 stem이 같아야 자동 매칭됩니다.

```text
ai/stt/data/raw/wav/0001.wav
ai/stt/data/raw/labels/0001.json
```

metadata를 생성합니다.

```bash
python ai/stt/scripts/build_metadata.py \
  --wav-dir ai/stt/data/raw/wav \
  --label-dir ai/stt/data/raw/labels \
  --output ai/stt/data/processed/metadata.csv \
  --split test
```

JSON 라벨 텍스트 위치가 자동으로 잡히지 않으면 dotted path로 직접 지정합니다.

```bash
python ai/stt/scripts/build_metadata.py \
  --text-key data.0.transcript \
  --speaker-key speaker.id
```

wav를 16kHz mono로 전처리합니다.

```bash
python ai/stt/scripts/preprocess_audio.py \
  --input-metadata ai/stt/data/processed/metadata.csv \
  --output-metadata ai/stt/data/processed/metadata_preprocessed.csv \
  --force
```

Whisper를 실행합니다.

```bash
python ai/stt/scripts/run_whisper.py \
  --metadata ai/stt/data/processed/metadata_preprocessed.csv \
  --model small \
  --language ko \
  --device cpu \
  --beam-size 5
```

Faster-Whisper를 실행합니다.

```bash
python ai/stt/scripts/run_faster_whisper.py \
  --metadata ai/stt/data/processed/metadata_preprocessed.csv \
  --model small \
  --language ko \
  --device cpu \
  --compute-type int8 \
  --beam-size 5
```

CER과 처리 시간을 비교합니다.

```bash
python ai/stt/scripts/evaluate.py
```
