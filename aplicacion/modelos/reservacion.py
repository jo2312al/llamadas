"""Modelos validados para solicitudes de reservación."""

from datetime import UTC, date, datetime, time, timedelta
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


class DetalleHabitacion(BaseModel):
    """Ocupación y precio de una habitación concreta."""

    tipo: str
    adultos: int = Field(ge=1, le=4)
    edades_menores: list[int] = Field(default_factory=list, max_length=4)
    precio_noche: int = Field(ge=0)

    @model_validator(mode="after")
    def validar_ocupacion(self) -> "DetalleHabitacion":
        if any(edad < 0 or edad > 11 for edad in self.edades_menores):
            raise ValueError("Los menores deben tener entre cero y once años")
        total = self.adultos + len(self.edades_menores)
        if total > 4:
            raise ValueError("Una habitación admite máximo cuatro huéspedes")
        if self.tipo == "king" and self.adultos > 2:
            raise ValueError("La king admite máximo dos adultos")
        if self.tipo not in {"doble", "king", "suite"}:
            raise ValueError("Tipo de habitación no reconocido")
        return self


class DatosReservacion(BaseModel):
    """Datos que aporta el huésped y valida Python."""

    nombre_completo: str | None = None
    telefono: str | None = None
    correo: str | None = None
    fecha_entrada: date | None = None
    fecha_salida: date | None = None
    numero_noches: int | None = Field(default=None, ge=1)
    numero_adultos: int | None = Field(default=None, ge=1, le=20)
    numero_menores: int = Field(default=0, ge=0, le=20)
    edades_menores: list[int] = Field(default_factory=list)
    tipo_habitacion: str | None = None
    numero_habitaciones: int | None = Field(default=None, ge=1, le=4)
    habitaciones: list[DetalleHabitacion] = Field(default_factory=list, max_length=4)
    hora_llegada: time | None = None
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
        elif self.fecha_entrada and self.numero_noches:
            self.fecha_salida = self.fecha_entrada + timedelta(days=self.numero_noches)
        if self.numero_habitaciones is not None and self.habitaciones:
            if len(self.habitaciones) > self.numero_habitaciones:
                raise ValueError("Hay más detalles que habitaciones solicitadas")
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
