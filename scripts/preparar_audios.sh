#!/usr/bin/env bash
set -Eeuo pipefail

MODELO="/opt/agente-telefonico-hotel/modelos/es_MX-claude-high.onnx"
DESTINO="/var/lib/asterisk/sounds/hotel/bienvenida.wav"
FRASE="Buenos días. Gracias por llamar a Hotel Villa Margaritas. ¿En qué puedo ayudarle?"

[[ -x /usr/local/bin/piper ]] || { echo "Piper no está instalado."; exit 1; }
[[ -f "${MODELO}" ]] || { echo "No existe el modelo de voz configurado."; exit 2; }
sudo dnf install -y sox
temporal="$(mktemp -d)"
trap 'rm -rf "${temporal}"' EXIT
/usr/local/bin/piper --model "${MODELO}" --output-file "${temporal}/original.wav" -- "${FRASE}"
sox -v 0.9 "${temporal}/original.wav" -r 8000 -c 1 -b 16 -e signed-integer "${temporal}/bienvenida.wav"
frecuencia="$(soxi -r "${temporal}/bienvenida.wav")"
canales="$(soxi -c "${temporal}/bienvenida.wav")"
[[ "${frecuencia}" == "8000" && "${canales}" == "1" ]] || {
  echo "El audio convertido no cumple el formato telefónico."; exit 3;
}
sudo install -d -o asterisk -g asterisk -m 0750 "$(dirname "${DESTINO}")"
sudo install -m 0640 -o asterisk -g asterisk "${temporal}/bienvenida.wav" "${DESTINO}"
echo "Bienvenida telefónica instalada en ${DESTINO}."
