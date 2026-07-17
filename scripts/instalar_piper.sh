#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="1.4.2"
VOZ="es_MX-claude-high"
RUTA="/opt/piper"
MODELOS="/opt/agente-telefonico-hotel/modelos"

if [[ ! -x "${RUTA}/bin/python" ]]; then
  sudo python3.11 -m venv "${RUTA}"
fi
sudo "${RUTA}/bin/pip" install --disable-pip-version-check "piper-tts==${VERSION}"
sudo install -d -o agente-hotel -g agente-hotel -m 0750 "${MODELOS}"
if [[ ! -f "${MODELOS}/${VOZ}.onnx" || ! -f "${MODELOS}/${VOZ}.onnx.json" ]]; then
  sudo "${RUTA}/bin/python" -m piper.download_voices --data-dir "${MODELOS}" "${VOZ}"
fi
sudo chown agente-hotel:agente-hotel "${MODELOS}/${VOZ}.onnx" "${MODELOS}/${VOZ}.onnx.json"
sudo chmod 0640 "${MODELOS}/${VOZ}.onnx" "${MODELOS}/${VOZ}.onnx.json"
sudo install -m 0755 "${RUTA}/bin/piper" /usr/local/bin/piper
/usr/local/bin/piper --help >/dev/null
echo "Piper ${VERSION} y la voz ${VOZ} instalados."
