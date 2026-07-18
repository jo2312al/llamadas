#!/usr/bin/env bash
set -Eeuo pipefail

fallos=0
comprobar() {
  local descripcion="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf '[correcto] %s\n' "${descripcion}"
  else
    printf '[pendiente] %s\n' "${descripcion}"
    fallos=$((fallos + 1))
  fi
}

comprobar_salida() {
  local descripcion="$1"
  local patron="$2"
  shift 2
  if salida=$("$@" 2>&1) && grep -Eq -- "${patron}" <<<"${salida}"; then
    printf '[correcto] %s\n' "${descripcion}"
  else
    printf '[pendiente] %s\n' "${descripcion}"
    fallos=$((fallos + 1))
  fi
}

comprobar "Asterisk activo" sudo systemctl is-active --quiet asterisk
comprobar "Agente activo" sudo systemctl is-active --quiet agente-telefonico
comprobar "ARI limitado a localhost" sudo ss -ltn 'sport = :8088'
comprobar_salida "Endpoint del proveedor cargado" \
  'Endpoint:[[:space:]]+proveedor-hotel/' \
  sudo /usr/sbin/asterisk -rx 'pjsip show endpoint proveedor-hotel'
comprobar_salida "Registro SIP configurado" \
  'proveedor-hotel-registro' \
  sudo /usr/sbin/asterisk -rx 'pjsip show registration proveedor-hotel-registro'
comprobar_salida "Registro SIP aceptado por el proveedor" \
  'Registered' \
  sudo /usr/sbin/asterisk -rx 'pjsip show registration proveedor-hotel-registro'
comprobar_salida "Dialplan entrante cargado" \
  '\[ Context .entrante-hotel. created by' \
  sudo /usr/sbin/asterisk -rx 'dialplan show entrante-hotel'
comprobar "Puerto SIP UDP escuchando" sudo ss -lun 'sport = :5060'
comprobar "Rango RTP configurado" sudo grep -Eq \
  '^[[:space:]]*rtp(start|end)[[:space:]]*=' /etc/asterisk/rtp.conf

if (( fallos > 0 )); then
  printf '%d comprobaciones pendientes.\n' "${fallos}"
  exit 1
fi
echo "Servidor listo para una llamada real; verifique también el Security Group de AWS."
