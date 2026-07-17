"""Entrega idempotente de solicitudes a una API de reservaciones."""

import httpx

from aplicacion.modelos.reservacion import SolicitudReservacion


class ErrorApiReservas(RuntimeError):
    """Fallo controlado al entregar una solicitud."""


class ClienteApiReservas:
    """Envía únicamente solicitudes validadas a un endpoint configurado."""

    def __init__(
        self,
        url: str,
        token: str | None = None,
        espera_segundos: float = 10,
        transporte: httpx.BaseTransport | None = None,
    ) -> None:
        cabeceras = {"Accept": "application/json"}
        if token:
            cabeceras["Authorization"] = f"Bearer {token}"
        self._cliente = httpx.Client(
            timeout=espera_segundos,
            headers=cabeceras,
            transport=transporte,
        )
        self.url = url

    def enviar(self, solicitud: SolicitudReservacion) -> None:
        """Envía una solicitud con identificador estable para evitar duplicados."""
        try:
            respuesta = self._cliente.post(
                self.url,
                json=solicitud.model_dump(mode="json"),
                headers={"Idempotency-Key": solicitud.identificador_solicitud},
            )
            respuesta.raise_for_status()
        except httpx.TimeoutException as error:
            raise ErrorApiReservas("La API de reservas excedió el tiempo permitido") from error
        except httpx.HTTPStatusError as error:
            raise ErrorApiReservas(
                f"La API de reservas respondió HTTP {error.response.status_code}"
            ) from error
        except httpx.RequestError as error:
            raise ErrorApiReservas("No fue posible conectar con la API de reservas") from error

    def cerrar(self) -> None:
        self._cliente.close()
