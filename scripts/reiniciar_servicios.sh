#!/usr/bin/env bash
set -Eeuo pipefail
sudo systemctl restart agente-telefonico.service
sudo systemctl is-active agente-telefonico.service

