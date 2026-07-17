"""Pruebas de integración simulada con Asterisk ARI."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from aplicacion.telefonia.cliente_asterisk import ClienteAsterisk, ErrorAsterisk
from aplicacion.telefonia.eventos_llamada import TipoEvento, interpretar_evento
from aplicacion.telefonia.sesion_llamada import GestorSesiones
from aplicacion.telefonia.transferencia import transferir_a_recepcion


def crear_cliente(
    respuestas: list[int] | None = None,
) -> tuple[ClienteAsterisk, list[httpx.Request]]:
    """Crea un cliente ARI con transporte HTTP simulado."""
    solicitudes: list[httpx.Request] = []
    codigos = iter(respuestas or [204] * 10)

    def responder(solicitud: httpx.Request) -> httpx.Response:
        solicitudes.append(solicitud)
        return httpx.Response(next(codigos), request=solicitud)

    transporte = httpx.MockTransport(responder)
    return (
        ClienteAsterisk("http://127.0.0.1:8088", "agente", "secreto", transporte=transporte),
        solicitudes,
    )


def test_acciones_ari_y_transferencia() -> None:
    cliente, solicitudes = crear_cliente()
    gestor = GestorSesiones()
    sesion = gestor.crear("canal/1")
    cliente.responder("canal/1")
    cliente.reproducir("canal/1", "hotel/bienvenida")
    transferir_a_recepcion(cliente, sesion, "recepcion-101")
    cliente.colgar("canal/1")
    cliente.cerrar()
    assert [solicitud.method for solicitud in solicitudes] == ["POST", "POST", "POST", "DELETE"]
    assert solicitudes[0].url.raw_path.endswith(b"channels/canal%2F1/answer")
    assert sesion.transferencia_solicitada is True


def test_rechaza_sonido_y_endpoint_inseguros() -> None:
    cliente, _ = crear_cliente()
    with pytest.raises(ValueError):
        cliente.reproducir("canal", "../secreto")
    with pytest.raises(ValueError):
        cliente.transferir("canal", "Local", "recepcion;comando")
    cliente.cerrar()


def test_error_http_no_expone_respuesta() -> None:
    cliente, _ = crear_cliente([401])
    with pytest.raises(ErrorAsterisk, match="HTTP 401"):
        cliente.comprobar()
    cliente.cerrar()


def test_interpreta_evento_y_descarta_desconocido() -> None:
    evento = interpretar_evento(
        {"type": "ChannelDtmfReceived", "digit": "5", "channel": {"id": "abc", "state": "Up"}}
    )
    assert evento is not None
    assert evento.tipo == TipoEvento.DTMF
    assert evento.digito == "5"
    assert interpretar_evento({"type": "DeviceStateChanged"}) is None


def test_interpreta_eventos_de_reproduccion_y_grabacion() -> None:
    reproduccion = interpretar_evento(
        {
            "type": "PlaybackFinished",
            "playback": {"target_uri": "channel:canal-1", "id": "audio-1"},
        }
    )
    grabacion = interpretar_evento(
        {
            "type": "RecordingFinished",
            "recording": {"target_uri": "channel:canal-1", "name": "hotel-abc"},
        }
    )
    assert reproduccion is not None
    assert reproduccion.identificador_canal == "canal-1"
    assert grabacion is not None
    assert grabacion.identificador_canal == "canal-1"
    assert grabacion.identificador_recurso == "hotel-abc"


def test_graba_descarga_y_elimina_audio_por_ari(tmp_path) -> None:
    cliente, solicitudes = crear_cliente([201, 200, 204])
    cliente.grabar("canal/1", "hotel-abc", duracion_maxima=10, silencio_maximo=2)
    destino = cliente.descargar_grabacion("hotel-abc", tmp_path / "audio.wav")
    cliente.eliminar_grabacion("hotel-abc")
    cliente.cerrar()
    assert solicitudes[0].url.path.endswith("channels/canal/1/record")
    assert solicitudes[0].url.params["format"] == "wav"
    assert solicitudes[1].url.raw_path.endswith(b"recordings/stored/hotel-abc/file")
    assert solicitudes[2].method == "DELETE"
    assert solicitudes[2].url.path.endswith("recordings/stored/hotel-abc")
    assert destino.is_file()


def test_rechaza_nombre_de_grabacion_inseguro() -> None:
    cliente, _ = crear_cliente()
    with pytest.raises(ValueError):
        cliente.grabar("canal", "../grabacion")
    cliente.cerrar()


def test_sesiones_independientes_y_limite() -> None:
    gestor = GestorSesiones(duracion_maxima_segundos=60)
    primera = gestor.crear("uno")
    segunda = gestor.crear("dos")
    assert primera is not segunda
    futuro = datetime.now(UTC) + timedelta(seconds=61)
    assert {sesion.identificador_llamada for sesion in gestor.sesiones_vencidas(futuro)} == {
        "uno",
        "dos",
    }
    assert gestor.finalizar("uno") is primera
    assert gestor.obtener("uno") is None
