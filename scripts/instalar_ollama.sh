#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="0.32.0"
SHA_INSTALADOR="25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f"
MODELO="qwen2.5:3b-instruct-q4_K_M"

temporal="$(mktemp -d)"
trap 'rm -rf "${temporal}"' EXIT
curl -fL --retry 3 -o "${temporal}/instalar.sh" \
  "https://github.com/ollama/ollama/releases/download/v${VERSION}/install.sh"
echo "${SHA_INSTALADOR}  ${temporal}/instalar.sh" | sha256sum -c -
sudo env OLLAMA_VERSION="${VERSION}" sh "${temporal}/instalar.sh"
sudo install -d -m 0755 /etc/systemd/system/ollama.service.d
printf '%s\n' '[Service]' 'Environment="OLLAMA_HOST=127.0.0.1:11434"' | \
  sudo tee /etc/systemd/system/ollama.service.d/seguridad.conf >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
for _ in $(seq 1 30); do
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null && break
  sleep 1
done
ollama pull "${MODELO}"
ollama list
