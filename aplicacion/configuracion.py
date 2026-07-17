"""Carga y validación de configuración no sensible."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, SecretStr


class Configuracion(BaseModel):
    """Configuración operativa, con secretos tomados del entorno."""

    nombre_hotel: str = "Hotel Villa Margaritas"
    ruta_base_datos: Path = Path("datos/agente.db")
    url_ollama: str = "http://127.0.0.1:11434"
    modelo_ollama: str = "qwen2.5:3b-instruct-q4_K_M"
    espera_ollama_segundos: float = Field(default=60, gt=0, le=180)
    binario_whisper: Path = Path("/usr/local/bin/whisper-cli")
    modelo_whisper: Path = Path("modelos/ggml-small-q5_1.bin")
    binario_piper: Path = Path("/usr/local/bin/piper")
    modelo_piper: Path = Path("modelos/es_MX-claude-high.onnx")
    ruta_cache_audio: Path = Path("datos/cache_audio")
    umbral_voz_rms: int = Field(default=450, ge=1, le=32_767)
    espera_whisper_segundos: float = Field(default=25, gt=0, le=120)
    espera_piper_segundos: float = Field(default=15, gt=0, le=60)
    url_ari: str = "http://127.0.0.1:8088"
    usuario_ari: str = "agente-hotel"
    contrasena_ari: SecretStr | None = None
    aplicacion_ari: str = "agente-hotel"
    sonido_bienvenida: str = "hotel/bienvenida"
    extension_recepcion: str = "recepcion-101"
    duracion_maxima_llamada_segundos: int = Field(default=900, ge=30, le=3600)
    campos_obligatorios: list[str] = Field(default_factory=list)
    modo_simulacion: bool = True


def cargar_configuracion(ruta: Path) -> Configuracion:
    """Lee YAML y permite reemplazar valores operativos por entorno."""
    contenido = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    if valor := os.getenv("AGENTE_RUTA_BASE_DATOS"):
        contenido["ruta_base_datos"] = valor
    if valor := os.getenv("AGENTE_URL_OLLAMA"):
        contenido["url_ollama"] = valor
    if valor := os.getenv("AGENTE_ARI_USUARIO"):
        contenido["usuario_ari"] = valor
    if valor := os.getenv("AGENTE_ARI_PASSWORD"):
        contenido["contrasena_ari"] = valor
    return Configuracion.model_validate(contenido)
