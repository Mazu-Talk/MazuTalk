"""Compare base Whisper Medium and trained LoRA adapters on held-out speech."""

from __future__ import annotations

import argparse
import gc
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import jiwer
import librosa
import numpy as np
import pandas as pd
import soundfile as sf
import torch
import yaml
from tqdm import tqdm

if TYPE_CHECKING:
    from peft import PeftModel
    from transformers import WhisperForConditionalGeneration, WhisperProcessor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="ai/stt/configs/whisper_medium_lora.yaml")
    parser.add_argument("--data-root")
    parser.add_argument("--child-metadata")
    parser.add_argument("--asd-metadata")
    parser.add_argument("--output-dir")
    parser.add_argument("--checkpoint-root")
    parser.add_argument("--child-limit", type=int)
    parser.add_argument("--device", choices=("auto", "cuda", "mps", "cpu"), default="auto")
    parser.add_argument("--dtype", choices=("auto", "float16", "float32"), default="auto")
    parser.add_argument("--skip-asd", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def select_device(requested: str) -> torch.device:
    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. Use --device mps or --device cpu.")
    if requested == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is not available in this Python environment. Use --device cpu.")
    return torch.device(requested)


def select_dtype(requested: str, device: torch.device) -> torch.dtype:
    if requested == "float16":
        return torch.float16
    if requested == "float32":
        return torch.float32
    return torch.float16 if device.type in {"cuda", "mps"} else torch.float32


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def normalize_characters(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text)).lower()
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def normalize_words(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = re.sub(r"[^0-9a-z가-힣\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_audio_path(data_root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else data_root / path


def resolve_metadata_path(override: str | None, data_root: Path, configured: str) -> Path:
    if override:
        path = Path(override)
        return path if path.is_absolute() else Path.cwd() / path
    return data_root / configured


def prepare_frame(frame: pd.DataFrame, data_root: Path, max_audio_seconds: float) -> pd.DataFrame:
    result = frame.copy()
    result["text"] = result["text"].fillna("").astype(str).str.strip()
    result["speaker_id"] = result["speaker_id"].fillna("unknown").astype(str)
    result["duration_sec"] = pd.to_numeric(result["duration_sec"], errors="coerce")
    result["resolved_audio_path"] = result["audio_path"].map(
        lambda value: resolve_audio_path(data_root, value)
    )
    result = result[result["text"].ne("")]
    result = result[result["duration_sec"].le(max_audio_seconds)]
    result = result[result["resolved_audio_path"].map(Path.exists)]
    return result.reset_index(drop=True)


def build_child_test(child: pd.DataFrame, config: dict[str, Any], limit: int) -> pd.DataFrame:
    seed = int(config["split"]["seed"])
    speakers = child["speaker_id"].drop_duplicates().to_numpy()
    rng = np.random.default_rng(seed)
    rng.shuffle(speakers)
    n_val = max(1, int(len(speakers) * float(config["split"]["validation_ratio"])))
    n_test = max(1, int(len(speakers) * float(config["split"]["test_ratio"])))
    test_speakers = set(speakers[n_val : n_val + n_test])
    test = child[child["speaker_id"].isin(test_speakers)]
    return test.sample(min(limit, len(test)), random_state=seed).reset_index(drop=True)


def build_asd_test(asd: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    test_files = set(config["asd_adaptation"]["test_files"])
    names = asd["resolved_audio_path"].map(lambda path: Path(path).name)
    return asd[names.isin(test_files)].reset_index(drop=True)


def load_audio(path: Path, sample_rate: int) -> np.ndarray:
    audio, current_rate = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if current_rate != sample_rate:
        audio = librosa.resample(audio, orig_sr=current_rate, target_sr=sample_rate)
    return audio


def load_model(
    model_id: str,
    device: torch.device,
    dtype: torch.dtype,
    language: str,
    task: str,
    adapter_path: Path | None = None,
) -> WhisperForConditionalGeneration | PeftModel:
    from peft import PeftModel
    from transformers import WhisperForConditionalGeneration

    model = WhisperForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )
    if adapter_path is not None:
        model = PeftModel.from_pretrained(model, str(adapter_path), is_trainable=False)
    model.generation_config.language = language
    model.generation_config.task = task
    model.generation_config.forced_decoder_ids = None
    model.config.use_cache = True
    model.to(device)
    model.eval()
    return model


@torch.inference_mode()
def evaluate_frame(
    model: WhisperForConditionalGeneration | PeftModel,
    processor: WhisperProcessor,
    frame: pd.DataFrame,
    model_name: str,
    domain: str,
    config: dict[str, Any],
    device: torch.device,
    dtype: torch.dtype,
    prompt: str | None = None,
) -> pd.DataFrame:
    sample_rate = int(config["data"]["sample_rate"])
    rows: list[dict[str, Any]] = []
    prompt_ids = None
    if prompt:
        prompt_ids = processor.get_prompt_ids(prompt, return_tensors="pt").to(device)

    for index, row in tqdm(frame.iterrows(), total=len(frame), desc=f"{domain}:{model_name}"):
        audio = load_audio(Path(row["resolved_audio_path"]), sample_rate)
        input_features = processor.feature_extractor(
            audio,
            sampling_rate=sample_rate,
            return_tensors="pt",
        ).input_features.to(device=device, dtype=dtype)
        generate_args: dict[str, Any] = {
            "language": config["model"]["language"],
            "task": config["model"]["task"],
            "num_beams": int(config["prompt"]["num_beams"]),
            "max_new_tokens": int(config["model"]["max_label_length"]),
        }
        if prompt_ids is not None:
            generate_args["prompt_ids"] = prompt_ids

        started_at = time.perf_counter()
        generated = model.generate(input_features=input_features, **generate_args)
        latency_sec = time.perf_counter() - started_at
        prediction = processor.tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()
        reference = str(row["text"])
        normalized_reference = normalize_characters(reference)
        normalized_prediction = normalize_characters(prediction)
        word_reference = normalize_words(reference)
        word_prediction = normalize_words(prediction)
        rows.append(
            {
                "domain": domain,
                "model": model_name,
                "sample_id": Path(row["resolved_audio_path"]).stem,
                "audio_path": str(row["audio_path"]),
                "speaker_id": str(row["speaker_id"]),
                "duration_sec": float(row["duration_sec"]),
                "reference": reference,
                "prediction": prediction,
                "normalized_reference": normalized_reference,
                "normalized_prediction": normalized_prediction,
                "sample_cer": jiwer.cer(normalized_reference, normalized_prediction),
                "sample_wer": jiwer.wer(word_reference, word_prediction),
                "exact_match": normalized_reference == normalized_prediction,
                "latency_sec": latency_sec,
                "prompt_applied": prompt is not None,
            }
        )
    return pd.DataFrame(rows)


def summarize(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model_name, frame in predictions.groupby("model", sort=False):
        references = frame["normalized_reference"].tolist()
        hypotheses = frame["normalized_prediction"].tolist()
        word_references = frame["reference"].map(normalize_words).tolist()
        word_hypotheses = frame["prediction"].map(normalize_words).tolist()
        rows.append(
            {
                "model": model_name,
                "sample_count": len(frame),
                "cer": jiwer.cer(references, hypotheses),
                "wer": jiwer.wer(word_references, word_hypotheses),
                "exact_match_accuracy": float(frame["exact_match"].mean()),
                "mean_latency_sec": float(frame["latency_sec"].mean()),
            }
        )
    summary = pd.DataFrame(rows)
    base_rows = summary[summary["model"] == "base_medium"]
    if not base_rows.empty:
        base_cer = float(base_rows.iloc[0]["cer"])
        summary["cer_reduction_absolute"] = base_cer - summary["cer"]
        summary["cer_reduction_percent"] = np.where(
            base_cer > 0,
            (base_cer - summary["cer"]) / base_cer * 100,
            np.nan,
        )
    return summary


def build_wide_comparison(predictions: pd.DataFrame) -> pd.DataFrame:
    metadata_columns = [
        "sample_id",
        "audio_path",
        "speaker_id",
        "duration_sec",
        "reference",
    ]
    metadata = predictions[metadata_columns].drop_duplicates("sample_id")
    values = predictions.pivot(
        index="sample_id",
        columns="model",
        values=["prediction", "sample_cer", "exact_match", "latency_sec"],
    )
    values.columns = [f"{model}_{metric}" for metric, model in values.columns]
    return metadata.merge(values.reset_index(), on="sample_id", how="left")


def save_domain_results(predictions: pd.DataFrame, output_dir: Path, domain: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    long_path = output_dir / f"{domain}_stt_predictions_long.csv"
    comparison_path = output_dir / f"{domain}_stt_comparison.csv"
    summary_path = output_dir / f"{domain}_stt_metrics_summary.csv"
    predictions.to_csv(long_path, index=False, encoding="utf-8-sig")
    build_wide_comparison(predictions).to_csv(comparison_path, index=False, encoding="utf-8-sig")
    summary = summarize(predictions)
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"\n[{domain}] saved: {output_dir}")
    print(summary.to_string(index=False))


def main() -> None:
    args = parse_args()

    import peft
    import transformers
    from transformers import WhisperProcessor

    config = load_config(args.config)
    data_root = Path(args.data_root or config["data"]["runtime_root"])
    output_dir = Path(args.output_dir or config["evaluation"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    child_limit = int(args.child_limit or config["evaluation"]["child_test_limit"])
    device = select_device(args.device)
    dtype = select_dtype(args.dtype, device)

    child_metadata_path = resolve_metadata_path(
        args.child_metadata,
        data_root,
        config["data"]["child_metadata"],
    )
    asd_metadata_path = resolve_metadata_path(
        args.asd_metadata,
        data_root,
        config["data"]["asd_metadata"],
    )
    checkpoint_root = Path(args.checkpoint_root or config["training"]["output_dir"])
    print(
        {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "peft": peft.__version__,
            "device": str(device),
            "child_metadata": str(child_metadata_path),
            "child_metadata_exists": child_metadata_path.exists(),
            "asd_metadata": str(asd_metadata_path),
            "asd_metadata_exists": asd_metadata_path.exists(),
            "checkpoint_root": str(checkpoint_root),
            "checkpoint_root_exists": checkpoint_root.exists(),
        }
    )
    if not child_metadata_path.exists() or not asd_metadata_path.exists():
        raise FileNotFoundError("Dataset archive is not extracted. Run the evaluation notebook setup cells first.")

    child = prepare_frame(
        pd.read_csv(child_metadata_path),
        data_root,
        float(config["data"]["max_audio_seconds"]),
    )
    asd = prepare_frame(
        pd.read_csv(asd_metadata_path),
        data_root,
        float(config["data"]["max_audio_seconds"]),
    )
    child_test = build_child_test(child, config, child_limit)
    asd_test = build_asd_test(asd, config)
    child_test.to_csv(output_dir / "child_test_manifest.csv", index=False, encoding="utf-8-sig")
    partial_path = output_dir / "child_stt_predictions_partial.csv"
    existing_predictions = pd.DataFrame()
    if args.resume and partial_path.exists():
        existing_predictions = pd.read_csv(partial_path)
        print(
            "Resume data:",
            existing_predictions.groupby("model").size().to_dict(),
        )

    model_id = config["model"]["id"]
    specs: list[tuple[str, Path | None]] = [("base_medium", None)]
    child_adapter = checkpoint_root / "adapter-child"
    asd_adapter = checkpoint_root / "adapter-child-asd"
    if child_adapter.exists():
        specs.append(("child_lora", child_adapter))
    if asd_adapter.exists():
        specs.append(("child_asd_lora", asd_adapter))
    if len(specs) == 1:
        available = sorted(str(path.relative_to(checkpoint_root)) for path in checkpoint_root.rglob("*") if path.is_file())
        raise FileNotFoundError(
            f"No LoRA adapter found under {checkpoint_root}. Expected adapter-child or adapter-child-asd. "
            f"Available files: {available[:30]}"
        )

    processor = WhisperProcessor.from_pretrained(
        model_id,
        language=config["model"]["language"],
        task=config["model"]["task"],
    )
    child_predictions: list[pd.DataFrame] = []
    asd_predictions: list[pd.DataFrame] = []

    for model_name, adapter_path in specs:
        print(f"\nLoading {model_name}: {adapter_path or model_id}")
        model = load_model(
            model_id,
            device,
            dtype,
            config["model"]["language"],
            config["model"]["task"],
            adapter_path,
        )
        expected_sample_ids = set(
            child_test["resolved_audio_path"].map(lambda path: Path(path).stem)
        )
        completed = existing_predictions[existing_predictions.get("model", pd.Series(dtype=str)) == model_name]
        completed = completed[completed.get("sample_id", pd.Series(dtype=str)).isin(expected_sample_ids)]
        completed = completed.drop_duplicates("sample_id", keep="last")
        if len(completed) == len(expected_sample_ids) and set(completed["sample_id"]) == expected_sample_ids:
            print(f"Skipping completed child evaluation: {model_name} ({len(completed)} samples)")
            child_predictions.append(completed.reset_index(drop=True))
        else:
            child_predictions.append(
                evaluate_frame(model, processor, child_test, model_name, "child", config, device, dtype)
            )
        pd.concat(child_predictions, ignore_index=True).to_csv(
            partial_path,
            index=False,
            encoding="utf-8-sig",
        )
        if not args.skip_asd:
            asd_predictions.append(
                evaluate_frame(model, processor, asd_test, model_name, "asd", config, device, dtype)
            )
            if model_name == specs[-1][0]:
                asd_predictions.append(
                    evaluate_frame(
                        model,
                        processor,
                        asd_test,
                        f"{model_name}_prompt",
                        "asd",
                        config,
                        device,
                        dtype,
                        prompt=config["prompt"]["text"],
                    )
                )
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if device.type == "mps":
            torch.mps.empty_cache()

    save_domain_results(pd.concat(child_predictions, ignore_index=True), output_dir, "child")
    if asd_predictions:
        save_domain_results(pd.concat(asd_predictions, ignore_index=True), output_dir, "asd")


if __name__ == "__main__":
    main()
