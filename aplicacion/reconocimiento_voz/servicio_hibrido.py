"""Reconocimiento híbrido: Vosk para respuestas cerradas y Whisper como respaldo."""

import json
import wave
from pathlib import Path

from aplicacion.modelos.conversacion import EstadoConversacion, SesionLlamada
from aplicacion.reconocimiento_voz.servicio_whisper import ServicioWhisper, Transcripcion


class ErrorVosk(RuntimeError):
    """Vosk no obtuvo una respuesta estructurada suficientemente confiable."""


class ServicioVosk:
    """Carga una vez el modelo pequeño español y aplica gramáticas por turno."""

    def __init__(self, ruta_modelo: Path) -> None:
        from vosk import Model, SetLogLevel

        if not ruta_modelo.is_dir():
            raise FileNotFoundError(f"No existe el modelo Vosk: {ruta_modelo}")
        SetLogLevel(-1)
        self.modelo = Model(str(ruta_modelo))

    def transcribir(self, audio: Path, frases: list[str]) -> Transcripcion:
        from vosk import KaldiRecognizer

        with wave.open(str(audio), "rb") as wav:
            reconocedor = KaldiRecognizer(
                self.modelo,
                wav.getframerate(),
                json.dumps([*frases, "[unk]"], ensure_ascii=False),
            )
            reconocedor.SetWords(True)
            while datos := wav.readframes(4000):
                reconocedor.AcceptWaveform(datos)
        resultado = json.loads(reconocedor.FinalResult())
        texto = resultado.get("text", "").strip()
        palabras = resultado.get("result", [])
        confianza = sum(item.get("conf", 0) for item in palabras) / max(len(palabras), 1)
        if not texto or "[unk]" in texto or confianza < 0.65:
            raise ErrorVosk("Resultado Vosk vacío, desconocido o de baja confianza")
        return Transcripcion(texto=texto)


class ServicioReconocimientoHibrido:
    """Selecciona Vosk únicamente cuando el estado espera opciones limitadas."""

    def __init__(self, vosk: ServicioVosk, whisper: ServicioWhisper) -> None:
        self.vosk = vosk
        self.whisper = whisper

    def transcribir(self, audio: Path, sesion: SesionLlamada) -> Transcripcion:
        frases = frases_esperadas(sesion)
        if frases:
            try:
                return self.vosk.transcribir(audio, frases)
            except (ErrorVosk, OSError, ValueError, json.JSONDecodeError):
                pass
        return self.whisper.transcribir(audio)


def frases_esperadas(sesion: SesionLlamada) -> list[str] | None:
    """Devuelve solo alternativas válidas para el turno actual."""
    if sesion.estado_actual == EstadoConversacion.PRESENTAR_OPCIONES:
        return [
            "sí",
            "si confirmo",
            "confirmo",
            "continuar",
            "no",
            "cancelar",
            "cambiar fechas",
            "cambiar habitación",
            "cambiar huéspedes",
        ]
    if sesion.estado_actual != EstadoConversacion.RECOPILAR_DATOS:
        return None
    datos = sesion.datos
    if datos.fecha_entrada is None or datos.numero_noches is None:
        return None
    numeros = ["cero", "uno", "una", "dos", "tres", "cuatro"]
    if datos.numero_habitaciones is None:
        return numeros[1:]
    if sesion.tipo_habitacion_actual is None:
        return ["doble", "king", "suite", "habitación doble", "habitación king"]
    if sesion.adultos_habitacion_actual is None:
        return numeros[1:]
    if sesion.menores_habitacion_actual is None:
        return numeros
    return None
