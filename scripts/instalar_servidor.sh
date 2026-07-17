#!/usr/bin/env bash
set -Eeuo pipefail

[[ -r /etc/os-release ]] || { echo "No se identificó la distribución."; exit 1; }
. /etc/os-release
[[ "${ID}" == "amzn" ]] || { echo "Distribución no soportada automáticamente: ${ID}"; exit 1; }
sudo dnf install -y git python3.11 python3.11-pip util-linux sqlite
id agente-hotel >/dev/null 2>&1 || sudo useradd --system --home-dir /opt/agente-telefonico-hotel --shell /sbin/nologin agente-hotel
sudo usermod -aG agente-hotel "${USER}"
sudo install -d -o "${USER}" -g agente-hotel -m 0750 /opt/agente-telefonico-hotel
sudo install -d -o agente-hotel -g agente-hotel -m 0770 /opt/agente-telefonico-hotel/{datos,registros,respaldos}
sudo install -m 0644 systemd/agente-telefonico.service /etc/systemd/system/agente-telefonico.service
sudo install -d -m 0750 /etc/agente-telefonico
if [[ ! -f /etc/agente-telefonico/agente-telefonico.env ]]; then
  sudo install -m 0640 -o root -g agente-hotel systemd/agente-telefonico.env.example /etc/agente-telefonico/agente-telefonico.env
fi
sudo systemctl daemon-reload
sudo systemctl enable agente-telefonico.service
echo "Paquetes base preparados. Copie la configuración real sin sobrescribirla."
