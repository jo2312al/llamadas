#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="v1.8.6"
REVISION="23ee03506a91ac3d3f0071b40e66a430eebdfa1d"
MODELO="ggml-small-q5_1.bin"
SHA_MODELO="ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb"
URL_MODELO="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${MODELO}"
FUENTES="/usr/local/src/whisper.cpp-${VERSION}"
DESTINO_MODELO="/opt/agente-telefonico-hotel/modelos/${MODELO}"

if [[ -x /usr/local/bin/whisper-cli && -f "${DESTINO_MODELO}" ]]; then
  printf '%s  %s\n' "${SHA_MODELO}" "${DESTINO_MODELO}" | sha256sum --check --strict
  echo "Whisper y su modelo ya están instalados."
  exit 0
fi
sudo dnf install -y cmake gcc gcc-c++ make git
temporal="$(mktemp -d)"
trap 'rm -rf "${temporal}"' EXIT
git clone --filter=blob:none --no-checkout https://github.com/ggml-org/whisper.cpp.git "${temporal}/whisper.cpp"
git -C "${temporal}/whisper.cpp" checkout --detach "${REVISION}"
[[ "$(git -C "${temporal}/whisper.cpp" rev-parse HEAD)" == "${REVISION}" ]]
cmake -S "${temporal}/whisper.cpp" -B "${temporal}/compilacion" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF \
  -DWHISPER_BUILD_TESTS=OFF \
  -DWHISPER_BUILD_SERVER=OFF
cmake --build "${temporal}/compilacion" --config Release -j"$(nproc)"
sudo install -m 0755 "${temporal}/compilacion/bin/whisper-cli" /usr/local/bin/whisper-cli
sudo install -d -o agente-hotel -g agente-hotel -m 0750 "$(dirname "${DESTINO_MODELO}")"
curl --fail --location --proto '=https' --tlsv1.2 --output "${temporal}/${MODELO}" "${URL_MODELO}"
printf '%s  %s\n' "${SHA_MODELO}" "${temporal}/${MODELO}" | sha256sum --check --strict
sudo install -m 0640 -o agente-hotel -g agente-hotel "${temporal}/${MODELO}" "${DESTINO_MODELO}"
echo "whisper.cpp ${VERSION} y ${MODELO} instalados."
