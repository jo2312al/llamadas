"""Recepción asíncrona y autenticada de eventos WebSocket de ARI."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from pydantic import ValidationError
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from aplicacion.telefonia.cliente_asterisk import ErrorAsterisk
from aplicacion.telefonia.eventos_llamada import EventoLlamada, interpretar_evento


class ReceptorEventosAri:
    """Recibe eventos conocidos mediante WebSocket con reintentos acotados."""

    def __init__(
        self,
        url_ari: str,
        aplicacion: str,
        usuario: str,
        contrasena: str,
        espera_segundos: float = 30,
        reintentos: int = 3,
    ) -> None:
        self.url = construir_url_eventos(url_ari, aplicacion)
        credencial = base64.b64encode(f"{usuario}:{contrasena}".encode()).decode()
        self.cabeceras = {"Authorization": f"Basic {credencial}"}
        self.espera_segundos = espera_segundos
        self.reintentos = reintentos

    async def eventos(self) -> AsyncIterator[EventoLlamada]:
        """Entrega eventos válidos y reconecta un número finito de veces.

        Yields:
            Eventos normalizados de llamada.

        Raises:
            ErrorAsterisk: Si no se logra mantener la conexión ARI.
        """
        ultimo_error: Exception | None = None
        for intento in range(self.reintentos + 1):
            try:
                async with connect(
                    self.url,
                    additional_headers=self.cabeceras,
                    open_timeout=5,
                    ping_interval=20,
                    ping_timeout=10,
                ) as websocket:
                    while True:
                        # La ausencia de llamadas no es un fallo. El propio WebSocket
                        # comprueba la conexión mediante ping/pong y recv espera hasta
                        # un evento o el cierre del servidor.
                        mensaje = await websocket.recv()
                        evento = decodificar_evento(mensaje)
                        if evento:
                            yield evento
            except (TimeoutError, ConnectionClosed, OSError, WebSocketException) as error:
                ultimo_error = error
                if intento < self.reintentos:
                    await asyncio.sleep(min(2**intento, 5))
        raise ErrorAsterisk("Se agotaron los reintentos del WebSocket ARI") from ultimo_error


def construir_url_eventos(url_ari: str, aplicacion: str) -> str:
    """Construye la URL WebSocket sin incluir credenciales."""
    partes = urlsplit(url_ari)
    esquema = "wss" if partes.scheme == "https" else "ws"
    consulta = urlencode({"app": aplicacion, "subscribeAll": "false"})
    return urlunsplit((esquema, partes.netloc, "/ari/events", consulta, ""))


def decodificar_evento(mensaje: str | bytes) -> EventoLlamada | None:
    """Decodifica un mensaje ARI y descarta JSON inválido o irrelevante."""
    try:
        if isinstance(mensaje, bytes):
            mensaje = mensaje.decode("utf-8")
        datos = json.loads(mensaje)
        if not isinstance(datos, dict):
            return None
        return interpretar_evento(datos)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError):
        return None


ManejadorEvento = Callable[[EventoLlamada], None]
