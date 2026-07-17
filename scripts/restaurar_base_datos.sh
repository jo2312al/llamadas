#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${1:-}" == "--confirmar" && -n "${2:-}" ]] || {
  echo "Uso: $0 --confirmar respaldo.db.gz"; exit 2;
}
[[ -f "$2" ]] || { echo "No existe el respaldo."; exit 3; }
BASE="${AGENTE_RUTA_BASE_DATOS:-datos/agente.db}"
TEMPORAL="$(mktemp)"
trap 'rm -f "${TEMPORAL}"' EXIT
gzip -cd -- "$2" >"${TEMPORAL}"
sqlite3 "${TEMPORAL}" "PRAGMA integrity_check" | grep -qx ok
cp -a "${BASE}" "${BASE}.antes-restauracion.$(date -u +%Y%m%dT%H%M%SZ)"
install -m 0640 "${TEMPORAL}" "${BASE}"
echo "Base restaurada; se conservó copia previa."

