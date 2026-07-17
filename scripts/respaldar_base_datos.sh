#!/usr/bin/env bash
set -Eeuo pipefail
BASE="${AGENTE_RUTA_BASE_DATOS:-datos/agente.db}"
DESTINO="${AGENTE_RUTA_RESPALDOS:-respaldos}"
mkdir -p "${DESTINO}"
MARCA="$(date -u +%Y%m%dT%H%M%SZ)"
sqlite3 "${BASE}" ".backup '${DESTINO}/agente-${MARCA}.db'"
gzip "${DESTINO}/agente-${MARCA}.db"
echo "Respaldo creado: ${DESTINO}/agente-${MARCA}.db.gz"

