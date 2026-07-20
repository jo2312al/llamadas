"""Ejecución acotada de whisper.cpp como proceso local."""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class ErrorWhisper(RuntimeError):
    """Error controlado al transcribir audio."""


@dataclass(frozen=True)
class Transcripcion:
    """Texto reconocido con metadatos mínimos."""

    texto: str
    idioma: str = "es"


class ServicioWhisper:
    """Invoca whisper.cpp sin shell y con límite estricto de tiempo."""

    def __init__(
        self,
        binario: Path,
        modelo: Path,
        espera_segundos: float = 25,
        hilos: int = 2,
    ) -> None:
        self.binario = binario
        self.modelo = modelo
        self.espera_segundos = espera_segundos
        self.hilos = hilos

    def transcribir(self, audio_wav: Path, sesion=None) -> Transcripcion:
        """Transcribe un WAV y elimina siempre la salida temporal.

        Args:
            audio_wav: WAV mono compatible con whisper.cpp.

        Returns:
            Texto no vacío reconocido en español.

        Raises:
            ErrorWhisper: Ante timeout, archivos ausentes o salida inválida.
        """
        self._validar_archivos(audio_wav)
        with tempfile.TemporaryDirectory(prefix="whisper-") as temporal:
            salida = Path(temporal) / "transcripcion"
            comando = self._crear_comando(audio_wav, salida)
            try:
                subprocess.run(
                    comando,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.espera_segundos,
                )
                return self._leer_resultado(salida.with_suffix(".json"))
            except subprocess.TimeoutExpired as error:
                raise ErrorWhisper("Whisper excedió el tiempo permitido") from error
            except subprocess.CalledProcessError as error:
                detalle = (error.stderr or "error sin detalle")[-300:]
                raise ErrorWhisper(f"Whisper falló: {detalle}") from error

    def _validar_archivos(self, audio_wav: Path) -> None:
        for etiqueta, ruta in {
            "binario": self.binario,
            "modelo": self.modelo,
            "audio": audio_wav,
        }.items():
            if not ruta.is_file():
                raise ErrorWhisper(f"No existe el {etiqueta} de Whisper: {ruta}")

    def _crear_comando(self, audio_wav: Path, salida: Path) -> list[str]:
        contexto = (
            "Reservación de Hotel Villa Margaritas en español mexicano. "
            "Habitación doble, king o suite; fecha de entrada, noches, "
            "habitaciones, adultos, niños, edades, hora de llegada, "
            "sí confirmo, nombre completo y número de teléfono."
        )
        return [
            str(self.binario),
            "-m",
            str(self.modelo),
            "-f",
            str(audio_wav),
            "-l",
            "es",
            "-t",
            str(self.hilos),
            "-oj",
            "-nt",
            "--prompt",
            contexto,
            "-of",
            str(salida),
            "--no-prints",
        ]

    @staticmethod
    def _leer_resultado(ruta: Path) -> Transcripcion:
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            texto = " ".join(segmento["text"].strip() for segmento in datos["transcription"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ErrorWhisper("Whisper produjo una salida inválida") from error
        if not texto:
            raise ErrorWhisper("Whisper no reconoció voz")
        return Transcripcion(texto=texto)
