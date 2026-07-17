"""Pruebas del webhook de solicitudes de reservación."""

import json

import httpx
import pytest

from aplicacion.integraciones.api_reservas import ClienteApiReservas, ErrorApiReservas
from aplicacion.modelos.reservacion import DatosReservacion, SolicitudReservacion


def test_envia_json_autorizado_e_idempotente() -> None:
    solicitudes: list[httpx.Request] = []

    def responder(solicitud_http: httpx.Request) -> httpx.Response:
        solicitudes.append(solicitud_http)
        return httpx.Response(202, request=solicitud_http)

    cliente = ClienteApiReservas(
        "https://reservas.example/api/solicitudes",
        "token-prueba",
        transporte=httpx.MockTransport(responder),
    )
    solicitud = SolicitudReservacion(
        identificador_llamada="llamada-1",
        datos=DatosReservacion(nombre_completo="Ana Pérez", numero_adultos=2),
    )
    cliente.enviar(solicitud)
    cliente.cerrar()
    enviada = solicitudes[0]
    assert enviada.headers["Authorization"] == "Bearer token-prueba"
    assert enviada.headers["Idempotency-Key"] == solicitud.identificador_solicitud
    assert json.loads(enviada.content)["datos"]["nombre_completo"] == "Ana Pérez"


def test_reporta_error_http_sin_exponer_respuesta() -> None:
    transporte = httpx.MockTransport(lambda request: httpx.Response(500, request=request))
    cliente = ClienteApiReservas("https://reservas.example/api", transporte=transporte)
    solicitud = SolicitudReservacion(identificador_llamada="llamada-2", datos=DatosReservacion())
    with pytest.raises(ErrorApiReservas, match="HTTP 500"):
        cliente.enviar(solicitud)
    cliente.cerrar()
