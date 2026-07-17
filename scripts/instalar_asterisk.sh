#!/usr/bin/env bash
set -Eeuo pipefail

ASTERISK_VERSION="22.10.1"
ASTERISK_SHA256="0953564c44fa49827f3c9d70ca6e80db83828c9848440852c6be44c961855353"
ASTERISK_ARCHIVO="asterisk-${ASTERISK_VERSION}.tar.gz"
ASTERISK_URL="https://downloads.asterisk.org/pub/telephony/asterisk/${ASTERISK_ARCHIVO}"
FUENTES="/usr/local/src/asterisk-${ASTERISK_VERSION}"
RUTA_PROYECTO="${EC2_RUTA_PROYECTO:-/opt/agente-telefonico-hotel}"
UNIDAD="${ASTERISK_UNIDAD:-${RUTA_PROYECTO}/systemd/asterisk.service}"

registrar() { printf '[asterisk] %s\n' "$*"; }

preparar_servicio() {
  if ! id asterisk >/dev/null 2>&1; then
    sudo useradd --system --home-dir /var/lib/asterisk --shell /sbin/nologin asterisk
  fi
  for ruta in /var/lib/asterisk /var/log/asterisk /var/spool/asterisk /var/run/asterisk; do
    sudo install -d -o asterisk -g asterisk -m 0750 "${ruta}"
  done
  sudo chown -R asterisk:asterisk /etc/asterisk
  [[ -f "${UNIDAD}" ]] || { registrar "No existe la unidad systemd: ${UNIDAD}"; exit 4; }
  sudo install -m 0644 "${UNIDAD}" /etc/systemd/system/asterisk.service
  sudo systemctl daemon-reload
}

[[ -r /etc/os-release ]] || { registrar "No se identificó el sistema operativo."; exit 1; }
. /etc/os-release
[[ "${ID}" == "amzn" && "${VERSION_ID}" == "2023" ]] || {
  registrar "Este instalador solo admite Amazon Linux 2023."; exit 2;
}
if [[ -x /usr/sbin/asterisk ]] && /usr/sbin/asterisk -V | grep -Fq "${ASTERISK_VERSION}"; then
  registrar "Asterisk ${ASTERISK_VERSION} ya está instalado."
  preparar_servicio
  exit 0
fi

registrar "Instalando herramientas y bibliotecas de compilación."
sudo dnf install -y \
  gcc gcc-c++ make tar patch perl \
  ncurses-devel libxml2-devel sqlite-devel openssl-devel \
  libuuid-devel jansson-devel libedit-devel libsrtp-devel

temporal="$(mktemp -d)"
trap 'rm -rf "${temporal}"' EXIT
registrar "Descargando ${ASTERISK_ARCHIVO} desde el servidor oficial."
curl --fail --location --proto '=https' --tlsv1.2 --output "${temporal}/${ASTERISK_ARCHIVO}" "${ASTERISK_URL}"
printf '%s  %s\n' "${ASTERISK_SHA256}" "${temporal}/${ASTERISK_ARCHIVO}" | sha256sum --check --strict

sudo install -d -m 0755 /usr/local/src
sudo rm -rf "${FUENTES}.nuevo"
sudo mkdir "${FUENTES}.nuevo"
sudo tar -xzf "${temporal}/${ASTERISK_ARCHIVO}" --strip-components=1 -C "${FUENTES}.nuevo"
cd "${FUENTES}.nuevo"
registrar "Configurando una compilación sin hardware DAHDI."
sudo ./configure \
  --libdir=/usr/lib64 \
  --with-jansson \
  --with-pjproject-bundled \
  --without-dahdi \
  --without-pri \
  --without-ss7
sudo make menuselect.makeopts
sudo menuselect/menuselect --disable BUILD_NATIVE menuselect.makeopts
sudo menuselect/menuselect --enable app_stasis --enable res_ari \
  --enable res_ari_applications --enable res_http_websocket \
  --enable chan_pjsip --enable format_wav --enable codec_ulaw \
  --enable codec_alaw menuselect.makeopts
registrar "Compilando con los núcleos disponibles."
sudo make -j"$(nproc)"
sudo make install
sudo make samples
preparar_servicio
sudo rm -rf "${FUENTES}"
sudo mv "${FUENTES}.nuevo" "${FUENTES}"
registrar "Asterisk ${ASTERISK_VERSION} instalado; falta aplicar la configuración privada de ARI."
