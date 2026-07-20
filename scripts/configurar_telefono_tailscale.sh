#!/usr/bin/env bash
set -Eeuo pipefail

ASTERISK_DIR=/etc/asterisk
PJSIP_PRINCIPAL="${ASTERISK_DIR}/pjsip.conf"
PJSIP_TAILSCALE="${ASTERISK_DIR}/pjsip_tailscale.conf"

command -v tailscale >/dev/null || {
  echo "Tailscale no está instalado" >&2
  exit 1
}

ip_tailscale=$(tailscale ip -4 | head -n 1)
[[ "${ip_tailscale}" =~ ^100\. ]] || {
  echo "El servidor no está conectado a Tailscale" >&2
  exit 1
}

contrasena=$(openssl rand -base64 30 | tr -dc 'A-Za-z0-9' | head -c 32)
temporal=$(mktemp)
trap 'rm -f "${temporal}"' EXIT

cat >"${temporal}" <<EOF
; Generado localmente. No guardar credenciales en Git.
[transporte-tailscale]
type=transport
protocol=udp
bind=${ip_tailscale}:5060

[telefono-prueba]
type=endpoint
transport=transporte-tailscale
context=laboratorio-agente
disallow=all
allow=ulaw,alaw
auth=telefono-prueba-auth
aors=telefono-prueba-aor
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
media_address=${ip_tailscale}

[telefono-prueba-auth]
type=auth
auth_type=userpass
username=telefono-prueba
password=${contrasena}

[telefono-prueba-aor]
type=aor
max_contacts=1
remove_existing=yes
qualify_frequency=30
EOF

sudo install -o root -g asterisk -m 0640 "${temporal}" "${PJSIP_TAILSCALE}"
if ! sudo grep -Fqx '#include pjsip_tailscale.conf' "${PJSIP_PRINCIPAL}"; then
  printf '\n#include pjsip_tailscale.conf\n' | sudo tee -a "${PJSIP_PRINCIPAL}" >/dev/null
fi

sudo systemctl restart asterisk
sudo systemctl restart agente-telefonico

for _ in {1..20}; do
  if sudo /usr/sbin/asterisk -rx 'pjsip show endpoint telefono-prueba' >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
sudo /usr/sbin/asterisk -rx 'pjsip show endpoint telefono-prueba' >/dev/null

printf 'SERVIDOR=%s\n' "${ip_tailscale}"
printf 'USUARIO=telefono-prueba\n'
printf 'CONTRASENA=%s\n' "${contrasena}"
printf 'PUERTO=5060\n'
printf 'EXTENSION=7000\n'
