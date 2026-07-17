#!/usr/bin/env bash
set -Eeuo pipefail
MODELO="${AGENTE_MODELO_OLLAMA:-qwen2.5:3b-instruct-q4_K_M}"
command -v ollama >/dev/null || { echo "Ollama no está instalado."; exit 1; }
ollama list | awk 'NR>1 {print $1}' | grep -Fxq "${MODELO}" || ollama pull "${MODELO}"

