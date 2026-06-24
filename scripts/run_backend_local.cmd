@echo off
set ROOT=%~dp0..
cd /d "%ROOT%\backend"

set OLLAMA_URL=http://localhost:11434
set LLM_MODEL=mazutalk
set AI_SERVICE_TIMEOUT=60
set RP_PROMPT_PATH=%ROOT%\ai\prompts\RP_system_prompt_runtime.md

set STT_MODEL=%ROOT%\ai\stt\models\faster-whisper-medium-child-lora-int8
set STT_FALLBACK_MODEL=medium
set STT_DEVICE=cpu
set STT_COMPUTE_TYPE=int8
set STT_BEAM_SIZE=3

set TTS_DEVICE=cpu
set TTS_OUTPUT_DIR=%ROOT%\output_audio
set SESSION_DB_PATH=:memory:
set CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "%ROOT%\backend.local.log" 2>&1
