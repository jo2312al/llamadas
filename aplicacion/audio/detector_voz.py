"""Detección de actividad de voz basada en energía, sin dependencias nativas."""

import math
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfiguracionVoz:
    """Umbrales temporales y de energía para audio PCM de 16 bits."""

    umbral_rms: int = 450
    cuadros_inicio: int = 2
    cuadros_silencio_fin: int = 12


class DetectorVoz:
    """Detecta inicio y fin de una intervención mediante RMS."""

    def __init__(self, configuracion: ConfiguracionVoz | None = None) -> None:
        self.configuracion = configuracion or ConfiguracionVoz()
        self._cuadros_con_voz = 0
        self._cuadros_silencio = 0
        self.hablando = False

    def procesar(self, pcm: bytes) -> str | None:
        """Procesa un cuadro PCM y devuelve ``inicio`` o ``fin`` cuando aplica.

        Args:
            pcm: Muestras PCM mono little-endian con signo de 16 bits.

        Returns:
            Evento detectado o ``None`` si no cambió el estado.

        Raises:
            ValueError: Si el cuadro está vacío o tiene longitud impar.
        """
        energia = calcular_rms(pcm)
        if energia >= self.configuracion.umbral_rms:
            self._cuadros_silencio = 0
            self._cuadros_con_voz += 1
            if not self.hablando and self._cuadros_con_voz >= self.configuracion.cuadros_inicio:
                self.hablando = True
                return "inicio"
            return None
        self._cuadros_con_voz = 0
        if self.hablando:
            self._cuadros_silencio += 1
            if self._cuadros_silencio >= self.configuracion.cuadros_silencio_fin:
                self.hablando = False
                self._cuadros_silencio = 0
                return "fin"
        return None


def calcular_rms(pcm: bytes) -> int:
    """Calcula energía RMS de muestras PCM S16LE sin usar ``audioop``."""
    if not pcm or len(pcm) % 2:
        raise ValueError("El cuadro PCM debe contener muestras completas")
    cantidad = len(pcm) // 2
    muestras = struct.unpack(f"<{cantidad}h", pcm)
    cuadrados = sum(muestra * muestra for muestra in muestras)
    return round(math.sqrt(cuadrados / cantidad))
