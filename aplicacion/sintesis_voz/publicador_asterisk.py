"""Publicación segura de audio sintetizado en el catálogo local de Asterisk."""

import subprocess
from pathlib import Path


class ErrorPublicacionAudio(RuntimeError):
    """Fallo al convertir o publicar audio telefónico."""


class PublicadorAudioAsterisk:
    """Convierte WAV a 8 kHz mono y devuelve su identificador Asterisk."""

    def __init__(self, directorio: Path, prefijo: str = "hotel/generado") -> None:
        self.directorio = directorio
        self.prefijo = prefijo.strip("/")

    def publicar(self, origen: Path) -> str:
        """Publica un WAV cuyo nombre ya es una huella segura."""
        nombre = origen.stem
        if not nombre or not nombre.isalnum():
            raise ErrorPublicacionAudio("Nombre de audio no permitido")
        destino = self.directorio / f"{nombre}.wav"
        temporal = destino.with_suffix(".temporal.wav")
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.is_file() and destino.stat().st_size > 44:
                return f"{self.prefijo}/{nombre}"
            subprocess.run(
                [
                    "sox",
                    "-v",
                    "0.9",
                    str(origen),
                    "-r",
                    "8000",
                    "-c",
                    "1",
                    "-b",
                    "16",
                    "-e",
                    "signed-integer",
                    str(temporal),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if not temporal.is_file() or temporal.stat().st_size <= 44:
                raise ErrorPublicacionAudio("SoX no produjo audio telefónico válido")
            temporal.replace(destino)
            return f"{self.prefijo}/{nombre}"
        except (subprocess.SubprocessError, OSError) as error:
            raise ErrorPublicacionAudio("No fue posible publicar el audio telefónico") from error
        finally:
            temporal.unlink(missing_ok=True)
