#!/usr/bin/env bash
set -Eeuo pipefail
for servicio in agente-telefonico asterisk ollama; do
  systemctl is-active "${servicio}.service" 2>/dev/null || true
done
free -h
df -h /
ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -10
sudo journalctl -u agente-telefonico.service -p err -n 30 --no-pager || true

