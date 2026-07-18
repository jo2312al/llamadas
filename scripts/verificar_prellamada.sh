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

comprobar "Asterisk activo" sudo systemctl is-active --quiet asterisk
comprobar "Agente activo" sudo systemctl is-active --quiet agente-telefonico
comprobar "ARI limitado a localhost" sudo ss -ltn 'sport = :8088'
comprobar "Endpoint del proveedor cargado" \
  sudo /usr/sbin/asterisk -rx 'pjsip show endpoint proveedor-hotel'
comprobar "Registro SIP configurado" \
  sudo /usr/sbin/asterisk -rx 'pjsip show registration proveedor-hotel-registro'
comprobar "Dialplan entrante cargado" \
  sudo /usr/sbin/asterisk -rx 'dialplan show entrante-hotel'
comprobar "Puerto SIP UDP escuchando" sudo ss -lun 'sport = :5060'
comprobar "Rango RTP configurado" sudo grep -Eq \
  '^[[:space:]]*rtp(start|end)[[:space:]]*=' /etc/asterisk/rtp.conf

if (( fallos > 0 )); then
  printf '%d comprobaciones pendientes.\n' "${fallos}"
  exit 1
fi
echo "Servidor listo para una llamada real; verifique también el Security Group de AWS."
