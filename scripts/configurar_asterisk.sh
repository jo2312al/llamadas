#!/usr/bin/env bash
set -Eeuo pipefail

: "${ASTERISK_ARI_PASSWORD:?Defina ASTERISK_ARI_PASSWORD sin guardarla en Git}"
[[ "${ASTERISK_ARI_PASSWORD}" =~ ^[A-Za-z0-9_.-]{32,128}$ ]] || {
  echo "La contraseña ARI debe tener 32-128 caracteres seguros."; exit 3;
}
RUTA_PROYECTO="${EC2_RUTA_PROYECTO:-/opt/agente-telefonico-hotel}"
DESTINO="/etc/asterisk"
MARCA="$(date -u +%Y%m%dT%H%M%SZ)"

[[ -x /usr/sbin/asterisk ]] || { echo "Asterisk no está instalado."; exit 1; }
[[ "$(id -u)" -ne 0 ]] || { echo "Ejecute como usuario con sudo, no como root."; exit 2; }
for archivo in http.conf ari.conf extensions.conf pjsip.conf; do
  if [[ -f "${DESTINO}/${archivo}" ]]; then
    sudo cp -a "${DESTINO}/${archivo}" "${DESTINO}/${archivo}.respaldo.${MARCA}"
  fi
done
sudo install -m 0640 -o asterisk -g asterisk "${RUTA_PROYECTO}/asterisk/http.conf" "${DESTINO}/http.conf"
sudo install -m 0640 -o asterisk -g asterisk "${RUTA_PROYECTO}/asterisk/extensions.conf" "${DESTINO}/extensions.conf"
sudo install -m 0640 -o asterisk -g asterisk "${RUTA_PROYECTO}/asterisk/pjsip.conf" "${DESTINO}/pjsip.conf"
temporal="$(mktemp)"
trap 'rm -f "${temporal}"' EXIT
sed "s|__ARI_PASSWORD__|${ASTERISK_ARI_PASSWORD}|g" "${RUTA_PROYECTO}/asterisk/ari.conf.plantilla" >"${temporal}"
sudo install -m 0640 -o asterisk -g asterisk "${temporal}" "${DESTINO}/ari.conf"
sudo systemctl enable asterisk.service
sudo systemctl restart asterisk.service
sudo systemctl is-active --quiet asterisk.service
ari_disponible=false
for _intento in $(seq 1 15); do
  if curl --fail --silent --user "agente-hotel:${ASTERISK_ARI_PASSWORD}" \
    http://127.0.0.1:8088/ari/asterisk/info >/dev/null; then
    ari_disponible=true
    break
  fi
  sudo systemctl is-active --quiet asterisk.service || break
  sleep 1
done
[[ "${ari_disponible}" == true ]] || {
  echo "Asterisk inició, pero ARI no respondió con las credenciales configuradas."; exit 4;
}
echo "Asterisk y ARI configurados correctamente en localhost."
