"""Síntesis local mediante Piper con caché y timeout."""

import subprocess
from pathlib import Path

from aplicacion.sintesis_voz.cache_audio import CacheAudio


class ErrorPiper(RuntimeError):
    """Error controlado al generar voz."""


class ServicioPiper:
    """Invoca Piper sin shell y reutiliza frases idénticas."""

    def __init__(
        self,
        binario: Path,
        modelo: Path,
        cache: CacheAudio,
        espera_segundos: float = 15,
    ) -> None:
        self.binario = binario
        self.modelo = modelo
        self.cache = cache
        self.espera_segundos = espera_segundos

    def sintetizar(self, texto: str) -> Path:
        """Genera un WAV o devuelve el existente en caché.

        Args:
            texto: Respuesta breve en español.

        Returns:
            Ruta del WAV generado.

        Raises:
            ErrorPiper: Si faltan archivos, el texto está vacío o Piper falla.
        """
        texto = " ".join(texto.split())
        if not texto:
            raise ErrorPiper("No se puede sintetizar un texto vacío")
        self._validar_archivos()
        destino = self.cache.ruta(texto, self.modelo.name)
        if destino.is_file() and destino.stat().st_size > 44:
            return destino
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(".temporal.wav")
        try:
            subprocess.run(
                [
                    str(self.binario),
                    "--model",
                    str(self.modelo),
                    "--output-file",
                    str(temporal),
                    "--",
                    texto,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.espera_segundos,
            )
            if not temporal.is_file() or temporal.stat().st_size <= 44:
                raise ErrorPiper("Piper no produjo audio válido")
            temporal.replace(destino)
            return destino
        except subprocess.TimeoutExpired as error:
            raise ErrorPiper("Piper excedió el tiempo permitido") from error
        except subprocess.CalledProcessError as error:
            detalle = (error.stderr or "error sin detalle")[-300:]
            raise ErrorPiper(f"Piper falló: {detalle}") from error
        finally:
            temporal.unlink(missing_ok=True)

    def _validar_archivos(self) -> None:
        if not self.binario.is_file():
            raise ErrorPiper(f"No existe el binario Piper: {self.binario}")
        if not self.modelo.is_file():
            raise ErrorPiper(f"No existe el modelo Piper: {self.modelo}")
