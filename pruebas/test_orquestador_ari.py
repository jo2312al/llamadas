"""Pruebas del orquestador de sesiones ARI."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from aplicacion.lenguaje.esquemas_ollama import RespuestaOllama
from aplicacion.reconocimiento_voz.servicio_whisper import Transcripcion
from aplicacion.telefonia.cliente_asterisk import ErrorAsterisk
from aplicacion.telefonia.eventos_llamada import EventoLlamada, TipoEvento
from aplicacion.telefonia.orquestador_ari import OrquestadorAri, clasificar_turno_local
from aplicacion.telefonia.sesion_llamada import GestorSesiones


def evento(tipo: TipoEvento, canal: str = "canal-1") -> EventoLlamada:
    """Crea un evento mínimo para pruebas."""
    return EventoLlamada(tipo=tipo, identificador_canal=canal)


def test_inicio_contesta_una_sola_vez_y_fin_retira() -> None:
    cliente = Mock()
    gestor = GestorSesiones()
    orquestador = OrquestadorAri(cliente, gestor)
    orquestador.procesar(evento(TipoEvento.INICIO))
    orquestador.procesar(evento(TipoEvento.INICIO))
    cliente.responder.assert_called_once_with("canal-1")
    assert gestor.obtener("canal-1") is not None
    orquestador.procesar(evento(TipoEvento.FIN))
    assert gestor.obtener("canal-1") is None


def test_inicio_reproduce_bienvenida_configurada() -> None:
    cliente = Mock()
    orquestador = OrquestadorAri(cliente, GestorSesiones(), "hotel/bienvenida")
    orquestador.procesar(evento(TipoEvento.INICIO))
    cliente.responder.assert_called_once_with("canal-1")
    cliente.reproducir.assert_called_once_with("canal-1", "hotel/bienvenida")


def test_error_al_responder_no_deja_sesion_huerfana() -> None:
    cliente = Mock()
    cliente.responder.side_effect = ErrorAsterisk("fallo")
    gestor = GestorSesiones()
    with pytest.raises(ErrorAsterisk):
        OrquestadorAri(cliente, gestor).procesar(evento(TipoEvento.INICIO))
    assert gestor.obtener("canal-1") is None


def test_finaliza_llamada_vencida() -> None:
    cliente = Mock()
    gestor = GestorSesiones(duracion_maxima_segundos=30)
    sesion = gestor.crear("canal-1")
    sesion.fecha_inicio = datetime.now(UTC) - timedelta(seconds=31)
    cantidad = OrquestadorAri(cliente, gestor).finalizar_vencidas()
    assert cantidad == 1
    cliente.colgar.assert_called_once_with("canal-1")
    assert gestor.obtener("canal-1") is None


def test_fin_de_bienvenida_inicia_grabacion() -> None:
    cliente = Mock()
    whisper = Mock()
    gestor = GestorSesiones()
    orquestador = OrquestadorAri(cliente, gestor, "hotel/bienvenida", whisper)
    orquestador.procesar(evento(TipoEvento.INICIO))
    orquestador.procesar(evento(TipoEvento.REPRODUCCION_TERMINADA))
    cliente.grabar.assert_called_once()
    assert cliente.grabar.call_args.args[0] == "canal-1"
    assert cliente.grabar.call_args.args[1].startswith("hotel-")


def test_fin_de_grabacion_transcribe_y_actualiza_sesion(tmp_path) -> None:
    cliente = Mock()
    whisper = Mock()
    whisper.transcribir.return_value = Transcripcion("Quiero reservar una habitación")
    gestor = GestorSesiones()
    gestor.crear("canal-1")
    orquestador = OrquestadorAri(cliente, gestor, whisper=whisper, ruta_grabaciones=tmp_path)
    terminado = EventoLlamada(
        tipo=TipoEvento.GRABACION_TERMINADA,
        identificador_canal="canal-1",
        identificador_recurso="hotel-abc",
    )
    orquestador.procesar(terminado)
    cliente.descargar_grabacion.assert_called_once_with("hotel-abc", tmp_path / "hotel-abc.wav")
    cliente.eliminar_grabacion.assert_called_once_with("hotel-abc")
    assert gestor.obtener("canal-1").ultimo_mensaje == "Quiero reservar una habitación"


def test_transcripcion_genera_y_reproduce_respuesta(tmp_path) -> None:
    cliente, whisper, ollama, piper, publicador = (Mock() for _ in range(5))
    whisper.transcribir.return_value = Transcripcion("Quiero reservar")
    ollama.analizar.return_value = RespuestaOllama(
        intencion="reservacion",
        confianza=0.95,
        accion_sugerida="preguntar_campo",
        texto_respuesta="Con gusto. ¿Para qué fecha desea reservar?",
    )
    piper.sintetizar.return_value = tmp_path / ("a" * 64 + ".wav")
    publicador.publicar.return_value = "hotel/generado/abc"
    gestor = GestorSesiones()
    gestor.crear("canal-1")
    orquestador = OrquestadorAri(
        cliente,
        gestor,
        whisper=whisper,
        ruta_grabaciones=tmp_path,
        ollama=ollama,
        piper=piper,
        publicador=publicador,
    )
    orquestador.procesar(
        EventoLlamada(
            tipo=TipoEvento.GRABACION_TERMINADA,
            identificador_canal="canal-1",
            identificador_recurso="hotel-abc",
        )
    )
    sesion = gestor.obtener("canal-1")
    assert sesion is not None
    assert sesion.intencion == "reservacion"
    piper.sintetizar.assert_called_once_with("Con gusto. ¿Para qué fecha desea reservar?")
    cliente.reproducir.assert_called_once_with("canal-1", "hotel/generado/abc")


def test_clasificador_local_no_inventa_datos() -> None:
    intencion, respuesta = clasificar_turno_local("Quiero reservar una habitación")
    assert intencion == "reservacion"
    assert respuesta == "Con gusto. ¿Para qué fecha desea reservar?"
