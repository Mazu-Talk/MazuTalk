#!/bin/sh
# Ollama 서버 기동 + (GGUF 가 있으면) 'mazutalk' 모델 1회 등록.
# 모델 파일이 git 에 없으므로(대용량), 부재 시에도 서버는 계속 떠서
# 백엔드가 규칙기반 fallback 으로 동작하도록 한다. (set -e 사용 안 함)

ollama serve &
SERVE_PID=$!

echo "[entrypoint] waiting for ollama daemon..."
until ollama list >/dev/null 2>&1; do
  sleep 1
done

GGUF=/models/model-q4_k_m.gguf
if ollama list | grep -q '^mazutalk'; then
  echo "[entrypoint] model 'mazutalk' already present."
elif [ -f "$GGUF" ]; then
  echo "[entrypoint] registering 'mazutalk' from GGUF (one-time)..."
  if ollama create mazutalk -f /modelfile/Modelfile; then
    echo "[entrypoint] model registered."
  else
    echo "[entrypoint] WARNING: registration failed; backend uses rule-based fallback."
  fi
else
  echo "[entrypoint] GGUF not found at $GGUF — skipping registration."
  echo "[entrypoint] Put model-q4_k_m.gguf in ai/models/ to enable the LLM (else rule-based fallback)."
fi

wait "$SERVE_PID"
