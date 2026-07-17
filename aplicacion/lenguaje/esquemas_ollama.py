"""Contrato estricto de salida del modelo Ollama."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatosExtraidos(BaseModel):
    """Valores propuestos por el modelo; aún no son datos autorizados."""

    model_config = ConfigDict(extra="forbid")
    nombre_completo: str | None = None
    telefono: str | None = None
    correo: str | None = None
    fecha_entrada_texto: str | None = None
    fecha_entrada_iso: str | None = None
    fecha_salida_texto: str | None = None
    fecha_salida_iso: str | None = None
    numero_noches: int | None = None
    numero_adultos: int | None = None
    numero_menores: int | None = None
    edades_menores: list[int] = Field(default_factory=list)
    tipo_habitacion: str | None = None
    numero_habitaciones: int | None = None
    canal_preferido: str | None = None
    observaciones: str | None = None
    solicitudes_especiales: list[str] = Field(default_factory=list)
    consentimiento_contacto: bool | None = None


class RespuestaOllama(BaseModel):
    """Respuesta estructurada que debe devolver Ollama."""

    model_config = ConfigDict(extra="forbid")
    intencion: str
    confianza: float = Field(ge=0, le=1)
    datos_extraidos: DatosExtraidos = Field(default_factory=DatosExtraidos)
    correcciones: list[str] = Field(default_factory=list)
    campos_ambiguos: list[str] = Field(default_factory=list)
    campos_faltantes_detectados: list[str] = Field(default_factory=list)
    accion_sugerida: str
    campo_sugerido: str | None = None
    texto_respuesta: str
    requiere_transferencia: bool = False
    motivo_transferencia: str | None = None
    requiere_revision_humana: bool = False
    motivo_revision: str | None = None


AccionOllama = Literal["preguntar_campo", "responder", "transferir", "continuar"]
