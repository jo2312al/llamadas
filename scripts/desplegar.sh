#!/usr/bin/env bash
set -Eeuo pipefail

RUTA_PROYECTO="${EC2_RUTA_PROYECTO:-/opt/agente-telefonico-hotel}"
REVISION="${REVISION_DESPLIEGUE:-main}"
BLOQUEO="/tmp/agente-telefonico-despliegue.lock"
REVISION_ANTERIOR=""

registrar() { printf '[despliegue] %s\n' "$*"; }
fallar() {
  codigo=$?
  registrar "Falló la etapa; código ${codigo}."
  if [[ -n "${REVISION_ANTERIOR}" ]] && git cat-file -e "${REVISION_ANTERIOR}^{commit}" 2>/dev/null; then
    registrar "Restaurando revisión ${REVISION_ANTERIOR}."
    git checkout --detach "${REVISION_ANTERIOR}"
    sudo systemctl restart agente-telefonico.service || true
  fi
  exit "${codigo}"
}
trap fallar ERR

[[ "$(pwd -P)" == "$(realpath "${RUTA_PROYECTO}")" ]] || {
  registrar "Debe ejecutarse desde ${RUTA_PROYECTO}."; exit 2;
}
exec 9>"${BLOQUEO}"
flock -n 9 || { registrar "Ya existe otro despliegue."; exit 3; }

REVISION_ANTERIOR="$(git rev-parse HEAD)"
registrar "Actualizando repositorio."
git fetch --prune origin
git checkout --detach "${REVISION}"
python3.11 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.txt
.venv/bin/python -m aplicacion.principal migrar --configuracion configuracion/configuracion.yaml
sudo install -d -o agente-hotel -g agente-hotel -m 0770 datos registros respaldos
sudo systemctl enable agente-telefonico.service
sudo systemctl restart agente-telefonico.service
sudo systemctl is-active --quiet agente-telefonico.service
.venv/bin/python -m aplicacion.principal salud --configuracion configuracion/configuracion.yaml
registrar "Revisión desplegada: $(git rev-parse HEAD)"
trap - ERR
