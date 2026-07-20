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
    identificador_recurso: str | None = None
    numero_origen: str | None = None


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
    recurso: dict[str, object] | None = None
    if tipo == TipoEvento.REPRODUCCION_TERMINADA:
        posible = datos.get("playback")
        recurso = posible if isinstance(posible, dict) else None
    elif tipo == TipoEvento.GRABACION_TERMINADA:
        posible = datos.get("recording")
        recurso = posible if isinstance(posible, dict) else None
    identificador_canal = canal.get("id") if isinstance(canal, dict) else None
    if not identificador_canal and recurso:
        objetivo = recurso.get("target_uri")
        if isinstance(objetivo, str) and objetivo.startswith("channel:"):
            identificador_canal = objetivo.removeprefix("channel:")
    if not identificador_canal:
        raise ValueError("El evento ARI no contiene un canal válido")
    return EventoLlamada(
        tipo=tipo,
        identificador_canal=str(identificador_canal),
        estado_canal=(
            str(canal.get("state")) if isinstance(canal, dict) and canal.get("state") else None
        ),
        digito=str(datos["digit"]) if datos.get("digit") else None,
        identificador_recurso=(str(recurso["name"]) if recurso and recurso.get("name") else None),
        numero_origen=(
            str(canal["caller"]["number"])
            if isinstance(canal, dict)
            and isinstance(canal.get("caller"), dict)
            and canal["caller"].get("number")
            else None
        ),
    )
