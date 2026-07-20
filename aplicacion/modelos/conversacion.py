"""Estado aislado de cada conversación."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from aplicacion.modelos.reservacion import DatosReservacion


class EstadoConversacion(StrEnum):
    """Estados explícitos controlados exclusivamente por Python."""

    BIENVENIDA = "BIENVENIDA"
    IDENTIFICAR_INTENCION = "IDENTIFICAR_INTENCION"
    RECOPILAR_DATOS = "RECOPILAR_DATOS"
    VALIDAR_DATOS = "VALIDAR_DATOS"
    CONSULTAR_DISPONIBILIDAD = "CONSULTAR_DISPONIBILIDAD"
    PRESENTAR_OPCIONES = "PRESENTAR_OPCIONES"
    CONFIRMAR_DATOS = "CONFIRMAR_DATOS"
    GUARDAR_SOLICITUD = "GUARDAR_SOLICITUD"
    ENVIAR_NOTIFICACION = "ENVIAR_NOTIFICACION"
    TRANSFERIR = "TRANSFERIR"
    FINALIZAR = "FINALIZAR"
    LLAMADA_ABANDONADA = "LLAMADA_ABANDONADA"
    ERROR = "ERROR"


class SesionLlamada(BaseModel):
    """Contexto independiente y auditable de una llamada."""

    identificador_llamada: str
    fecha_inicio: datetime = Field(default_factory=lambda: datetime.now(UTC))
    estado_actual: EstadoConversacion = EstadoConversacion.BIENVENIDA
    intencion: str = "desconocida"
    datos: DatosReservacion = Field(default_factory=DatosReservacion)
    datos_confirmados: bool = False
    campos_faltantes: list[str] = Field(default_factory=list)
    numero_intentos: int = 0
    errores: list[str] = Field(default_factory=list)
    resumen_conversacion: str = ""
    ultimo_mensaje: str = ""
    opciones_presentadas: list[dict[str, object]] = Field(default_factory=list)
    identificador_solicitud: str | None = None
    requiere_revision: bool = False
    motivo_revision: str | None = None
    transferencia_solicitada: bool = False
    tipo_habitacion_actual: str | None = None
    adultos_habitacion_actual: int | None = None
    menores_habitacion_actual: int | None = None
    modo_teclado: bool = False
    campo_teclado: str | None = None
