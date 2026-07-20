"""Máquina de estados del flujo de reservación."""

from aplicacion.modelos.conversacion import EstadoConversacion, SesionLlamada

TRANSICIONES: dict[EstadoConversacion, set[EstadoConversacion]] = {
    EstadoConversacion.BIENVENIDA: {EstadoConversacion.IDENTIFICAR_INTENCION},
    EstadoConversacion.IDENTIFICAR_INTENCION: {
        EstadoConversacion.RECOPILAR_DATOS,
        EstadoConversacion.TRANSFERIR,
        EstadoConversacion.FINALIZAR,
    },
    EstadoConversacion.RECOPILAR_DATOS: {
        EstadoConversacion.VALIDAR_DATOS,
        EstadoConversacion.TRANSFERIR,
        EstadoConversacion.LLAMADA_ABANDONADA,
    },
    EstadoConversacion.VALIDAR_DATOS: {
        EstadoConversacion.RECOPILAR_DATOS,
        EstadoConversacion.CONSULTAR_DISPONIBILIDAD,
        EstadoConversacion.ERROR,
    },
    EstadoConversacion.CONSULTAR_DISPONIBILIDAD: {
        EstadoConversacion.PRESENTAR_OPCIONES,
        EstadoConversacion.FINALIZAR,
        EstadoConversacion.ERROR,
    },
    EstadoConversacion.PRESENTAR_OPCIONES: {
        EstadoConversacion.CONFIRMAR_DATOS,
        EstadoConversacion.RECOPILAR_DATOS,
        EstadoConversacion.FINALIZAR,
    },
    EstadoConversacion.CONFIRMAR_DATOS: {
        EstadoConversacion.GUARDAR_SOLICITUD,
        EstadoConversacion.RECOPILAR_DATOS,
    },
    EstadoConversacion.GUARDAR_SOLICITUD: {EstadoConversacion.ENVIAR_NOTIFICACION},
    EstadoConversacion.ENVIAR_NOTIFICACION: {EstadoConversacion.FINALIZAR},
    EstadoConversacion.TRANSFERIR: {EstadoConversacion.FINALIZAR},
    EstadoConversacion.ERROR: {EstadoConversacion.TRANSFERIR, EstadoConversacion.FINALIZAR},
    EstadoConversacion.LLAMADA_ABANDONADA: set(),
    EstadoConversacion.FINALIZAR: set(),
}


class TransicionInvalida(ValueError):
    """Señala un salto no permitido en la máquina de estados."""


def transicionar(sesion: SesionLlamada, destino: EstadoConversacion) -> None:
    """Mueve una sesión únicamente si la transición está autorizada."""
    if destino not in TRANSICIONES[sesion.estado_actual]:
        raise TransicionInvalida(f"No se permite {sesion.estado_actual} -> {destino}")
    sesion.estado_actual = destino
