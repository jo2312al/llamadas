"""Validación de eventos ARI recibidos desde Asterisk."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TipoEvento(StrEnum):
    """Eventos mínimos que interesan al agente."""

    INICIO = "StasisStart"
    FIN = "StasisEnd"
    CAMBIO_ESTADO = "ChannelStateChange"
    DTMF = "ChannelDtmfReceived"
    REPRODUCCION_TERMINADA = "PlaybackFinished"
    GRABACION_TERMINADA = "RecordingFinished"


class EventoLlamada(BaseModel):
    """Evento ARI normalizado sin conservar el documento completo."""

    model_config = ConfigDict(extra="forbid")
    tipo: TipoEvento
    identificador_canal: str
    fecha: datetime = Field(default_factory=lambda: datetime.now(UTC))
    estado_canal: str | None = None
    digito: str | None = None


def interpretar_evento(datos: dict[str, object]) -> EventoLlamada | None:
    """Convierte un evento ARI conocido y descarta eventos irrelevantes.

    Args:
        datos: Documento JSON entregado por ARI.

    Returns:
        Evento normalizado o ``None`` cuando no requiere acción.

    Raises:
        ValueError: Si un evento conocido no contiene identificador de canal.
    """
    try:
        tipo = TipoEvento(str(datos.get("type")))
    except ValueError:
        return None
    canal = datos.get("channel")
    if not isinstance(canal, dict) or not canal.get("id"):
        raise ValueError("El evento ARI no contiene un canal válido")
    return EventoLlamada(
        tipo=tipo,
        identificador_canal=str(canal["id"]),
        estado_canal=str(canal.get("state")) if canal.get("state") else None,
        digito=str(datos["digit"]) if datos.get("digit") else None,
    )
