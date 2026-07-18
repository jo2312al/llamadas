#!/usr/bin/env bash
set -Eeuo pipefail

RUTA_PROYECTO="${EC2_RUTA_PROYECTO:-/opt/agente-telefonico-hotel}"
DESTINO="/etc/asterisk"
MARCA="$(date -u +%Y%m%dT%H%M%SZ)"

for variable in SIP_PROVEEDOR_HOST SIP_USUARIO SIP_PASSWORD SIP_DID \
  SIP_PROVEEDOR_CIDR SIP_IP_PUBLICA; do
  [[ -n "${!variable:-}" ]] || { echo "Falta ${variable}."; exit 2; }
done
SIP_RED_LOCAL="${SIP_RED_LOCAL:-172.31.0.0/16}"

[[ "${SIP_PROVEEDOR_HOST}" =~ ^[A-Za-z0-9.-]+(:[0-9]{1,5})?$ ]] || {
  echo "SIP_PROVEEDOR_HOST no es válido."; exit 3;
}
[[ "${SIP_USUARIO}" =~ ^[A-Za-z0-9_.+@-]{1,128}$ ]] || {
  echo "SIP_USUARIO no es válido."; exit 3;
}
[[ "${SIP_PASSWORD}" =~ ^[A-Za-z0-9_.+@:-]{8,128}$ ]] || {
  echo "SIP_PASSWORD debe tener 8-128 caracteres seguros."; exit 3;
}
[[ "${SIP_DID}" =~ ^[0-9]{7,15}$ ]] || { echo "SIP_DID debe contener 7-15 dígitos."; exit 3; }
[[ "${SIP_PROVEEDOR_CIDR}" =~ ^[0-9A-Fa-f:.]+/[0-9]{1,3}$ ]] || {
  echo "SIP_PROVEEDOR_CIDR debe ser una red CIDR."; exit 3;
}
[[ "${SIP_IP_PUBLICA}" =~ ^[0-9.]+$ ]] || { echo "SIP_IP_PUBLICA debe ser IPv4."; exit 3; }
[[ "${SIP_RED_LOCAL}" =~ ^[0-9.]+/[0-9]{1,2}$ ]] || {
  echo "SIP_RED_LOCAL debe ser una red IPv4 CIDR."; exit 3;
}

temporal="$(mktemp -d)"
trap 'rm -rf "${temporal}"' EXIT

renderizar() {
  local origen="$1" destino="$2" contenido
  contenido="$(<"${origen}")"
  contenido="${contenido//__SIP_HOST__/${SIP_PROVEEDOR_HOST}}"
  contenido="${contenido//__SIP_USUARIO__/${SIP_USUARIO}}"
  contenido="${contenido//__SIP_PASSWORD__/${SIP_PASSWORD}}"
  contenido="${contenido//__SIP_DID__/${SIP_DID}}"
  contenido="${contenido//__SIP_CIDR__/${SIP_PROVEEDOR_CIDR}}"
  contenido="${contenido//__SIP_IP_PUBLICA__/${SIP_IP_PUBLICA}}"
  contenido="${contenido//__SIP_RED_LOCAL__/${SIP_RED_LOCAL}}"
  printf '%s\n' "${contenido}" >"${destino}"
}

renderizar "${RUTA_PROYECTO}/asterisk/pjsip_troncal.conf.plantilla" \
  "${temporal}/pjsip_troncal.conf"
renderizar "${RUTA_PROYECTO}/asterisk/extensions_entrante.conf.plantilla" \
  "${temporal}/extensions_entrante.conf"

for archivo in pjsip.conf extensions.conf pjsip_troncal.conf extensions_entrante.conf; do
  sudo test ! -f "${DESTINO}/${archivo}" || \
    sudo cp -a "${DESTINO}/${archivo}" "${DESTINO}/${archivo}.respaldo.${MARCA}"
done
sudo grep -Fqx '#include pjsip_troncal.conf' "${DESTINO}/pjsip.conf" || \
  printf '\n#include pjsip_troncal.conf\n' | sudo tee -a "${DESTINO}/pjsip.conf" >/dev/null
sudo grep -Fqx '#include extensions_entrante.conf' "${DESTINO}/extensions.conf" || \
  printf '\n#include extensions_entrante.conf\n' | sudo tee -a "${DESTINO}/extensions.conf" >/dev/null
sudo install -m 0640 -o asterisk -g asterisk \
  "${temporal}/pjsip_troncal.conf" "${DESTINO}/pjsip_troncal.conf"
sudo install -m 0640 -o asterisk -g asterisk \
  "${temporal}/extensions_entrante.conf" "${DESTINO}/extensions_entrante.conf"

sudo /usr/sbin/asterisk -rx 'core reload'
sleep 2
sudo /usr/sbin/asterisk -rx 'pjsip show endpoint proveedor-hotel' | grep -Fq 'Endpoint:'
echo "Troncal SIP instalada. Falta autorizar SIP/RTP solo desde las redes del proveedor."
