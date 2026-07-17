"""Pruebas del transporte WebSocket ARI sin conexiones reales."""

from aplicacion.telefonia.eventos_ari import construir_url_eventos, decodificar_evento
from aplicacion.telefonia.eventos_llamada import TipoEvento


def test_construye_websocket_sin_credenciales() -> None:
    url = construir_url_eventos("http://127.0.0.1:8088", "agente-hotel")
    assert url == "ws://127.0.0.1:8088/ari/events?app=agente-hotel&subscribeAll=false"
    assert "password" not in url


def test_decodifica_evento_websocket() -> None:
    evento = decodificar_evento(b'{"type":"StasisStart","channel":{"id":"canal-1"}}')
    assert evento is not None
    assert evento.tipo == TipoEvento.INICIO


def test_descarta_mensajes_invalidos() -> None:
    assert decodificar_evento("no es json") is None
    assert decodificar_evento("[]") is None
