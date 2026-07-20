"""Pruebas de selección y respaldo del reconocedor híbrido."""

from pathlib import Path
from unittest.mock import Mock

from aplicacion.modelos.conversacion import EstadoConversacion, SesionLlamada
from aplicacion.reconocimiento_voz.servicio_hibrido import (
    ErrorVosk,
    ServicioReconocimientoHibrido,
    frases_esperadas,
)
from aplicacion.reconocimiento_voz.servicio_whisper import Transcripcion


def test_usa_gramatica_para_tipo_de_habitacion() -> None:
    sesion = SesionLlamada(identificador_llamada="hibrida")
    sesion.estado_actual = EstadoConversacion.RECOPILAR_DATOS
    sesion.datos.fecha_entrada = __import__("datetime").date(2027, 8, 10)
    sesion.datos.numero_noches = 2
    sesion.datos.numero_habitaciones = 1

    assert "doble" in frases_esperadas(sesion)


def test_recurre_a_whisper_si_vosk_tiene_baja_confianza() -> None:
    vosk = Mock()
    vosk.transcribir.side_effect = ErrorVosk("baja confianza")
    whisper = Mock()
    whisper.transcribir.return_value = Transcripcion("doble")
    servicio = ServicioReconocimientoHibrido(vosk, whisper)
    sesion = SesionLlamada(identificador_llamada="respaldo")
    sesion.estado_actual = EstadoConversacion.PRESENTAR_OPCIONES

    resultado = servicio.transcribir(Path("audio.wav"), sesion)

    assert resultado.texto == "doble"
    whisper.transcribir.assert_called_once_with(Path("audio.wav"))
