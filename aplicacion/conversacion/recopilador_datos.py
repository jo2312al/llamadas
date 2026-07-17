"""Determinación configurable de datos pendientes."""

from aplicacion.modelos.reservacion import DatosReservacion

CAMPOS_OBLIGATORIOS_PREDETERMINADOS = [
    "nombre_completo",
    "telefono",
    "fecha_entrada",
    "fecha_salida",
    "numero_adultos",
    "tipo_habitacion",
    "consentimiento_contacto",
]


def campos_faltantes(datos: DatosReservacion, obligatorios: list[str] | None = None) -> list[str]:
    """Devuelve campos sin valor, conservando el orden de preguntas."""
    campos = obligatorios or CAMPOS_OBLIGATORIOS_PREDETERMINADOS
    valores = datos.model_dump()
    return [campo for campo in campos if valores.get(campo) is None or valores.get(campo) == ""]
