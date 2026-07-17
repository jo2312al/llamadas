"""Conversión segura entre PCM telefónico y contenedores WAV."""

import wave
from pathlib import Path


def guardar_pcm_como_wav(
    pcm: bytes,
    destino: Path,
    frecuencia: int = 16_000,
    canales: int = 1,
) -> Path:
    """Guarda PCM S16LE en WAV apto para whisper.cpp.

    Args:
        pcm: Audio PCM de 16 bits.
        destino: Archivo WAV que se creará.
        frecuencia: Frecuencia de muestreo en Hz.
        canales: Número de canales.

    Returns:
        Ruta del WAV creado.

    Raises:
        ValueError: Si los parámetros o muestras no son válidos.
        OSError: Si no se puede escribir el archivo.
    """
    if not pcm or len(pcm) % 2:
        raise ValueError("El audio PCM está vacío o incompleto")
    if frecuencia not in {8_000, 16_000, 48_000} or canales not in {1, 2}:
        raise ValueError("Formato de audio no permitido")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as archivo:
        archivo.setnchannels(canales)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(pcm)
    return destino
