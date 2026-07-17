"""Política determinística de transferencia a recepción."""

from aplicacion.modelos.conversacion import SesionLlamada
from aplicacion.telefonia.cliente_asterisk import ClienteAsterisk


def transferir_a_recepcion(
    cliente: ClienteAsterisk,
    sesion: SesionLlamada,
    extension: str,
) -> None:
    """Transfiere una sesión y registra el resultado en memoria.

    Args:
        cliente: Adaptador ARI autorizado.
        sesion: Sesión independiente de la llamada.
        extension: Endpoint PJSIP configurado para recepción.

    Returns:
        No devuelve valor.

    Raises:
        ErrorAsterisk: Si Asterisk rechaza la transferencia.
        ValueError: Si la extensión no es segura.
    """
    cliente.transferir(sesion.identificador_llamada, "PJSIP", extension)
    sesion.transferencia_solicitada = True
