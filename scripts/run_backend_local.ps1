$ErrorActionPreference = "Continue"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location (Join-Path $root "backend")

$env:OLLAMA_URL = "http://localhost:11434"
$env:LLM_MODEL = "mazutalk"
$env:AI_SERVICE_TIMEOUT = "60"
$env:RP_PROMPT_PATH = (Resolve-Path (Join-Path $root "ai\prompts\RP_system_prompt_runtime.md")).Path

$env:STT_MODEL = (Resolve-Path (Join-Path $root "ai\stt\models\faster-whisper-medium-child-lora-int8")).Path
$env:STT_FALLBACK_MODEL = "medium"
$env:STT_DEVICE = "cpu"
$env:STT_COMPUTE_TYPE = "int8"
$env:STT_BEAM_SIZE = "3"

$env:TTS_DEVICE = "cpu"
$env:TTS_OUTPUT_DIR = Join-Path $root "output_audio"
$env:SESSION_DB_PATH = ":memory:"
$env:CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
