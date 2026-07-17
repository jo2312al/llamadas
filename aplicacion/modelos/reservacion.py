"""Modelos validados para solicitudes de reservación."""

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class EstadoSolicitud(StrEnum):
    """Estados permitidos de una solicitud."""

    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    REQUIERE_REVISION = "requiere_revision"
    SIN_DISPONIBILIDAD = "sin_disponibilidad"
    ABANDONADA = "abandonada"
    TRANSFERIDA = "transferida"
    ERROR = "error"


class DatosReservacion(BaseModel):
    """Datos que aporta el huésped y valida Python."""

    nombre_completo: str | None = None
    telefono: str | None = None
    correo: str | None = None
    fecha_entrada: date | None = None
    fecha_salida: date | None = None
    numero_noches: int | None = Field(default=None, ge=1, le=90)
    numero_adultos: int | None = Field(default=None, ge=1, le=20)
    numero_menores: int = Field(default=0, ge=0, le=20)
    edades_menores: list[int] = Field(default_factory=list)
    tipo_habitacion: str | None = None
    numero_habitaciones: int = Field(default=1, ge=1, le=10)
    canal_preferido: str | None = None
    observaciones: str | None = None
    solicitudes_especiales: list[str] = Field(default_factory=list)
    consentimiento_contacto: bool | None = None

    @model_validator(mode="after")
    def validar_estancia(self) -> "DatosReservacion":
        """Valida orden de fechas y deriva el número de noches."""
        if self.fecha_entrada and self.fecha_salida:
            if self.fecha_salida <= self.fecha_entrada:
                raise ValueError("La fecha de salida debe ser posterior a la entrada")
            noches = (self.fecha_salida - self.fecha_entrada).days
            if self.numero_noches not in (None, noches):
                raise ValueError("El número de noches no coincide con las fechas")
            self.numero_noches = noches
        return self


class SolicitudReservacion(BaseModel):
    """Solicitud persistible; no representa una reservación confirmada."""

    identificador_solicitud: str = Field(default_factory=lambda: str(uuid4()))
    identificador_llamada: str
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(UTC))
    estado: EstadoSolicitud = EstadoSolicitud.PENDIENTE
    datos: DatosReservacion
    resumen_conversacion: str = ""
    nivel_confianza: float = Field(default=0, ge=0, le=1)
    requiere_revision: bool = False
    motivo_revision: str | None = None
    total_estimado: float | None = Field(default=None, ge=0)
    moneda: str = "MXN"
