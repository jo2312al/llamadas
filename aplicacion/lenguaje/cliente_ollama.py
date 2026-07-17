"""Cliente acotado para Ollama con validación y reintentos finitos."""

import json
import re

import httpx
from pydantic import ValidationError

from aplicacion.lenguaje.esquemas_ollama import RespuestaOllama


class ErrorComprension(RuntimeError):
    """Indica que Ollama no produjo una respuesta utilizable."""


class ClienteOllama:
    """Consulta Ollama sin concederle control sobre reglas de negocio."""

    def __init__(self, url: str, modelo: str, espera_segundos: float = 20) -> None:
        self.url = url.rstrip("/")
        self.modelo = modelo
        self.espera_segundos = espera_segundos

    def analizar(self, sistema: str, mensaje: str) -> RespuestaOllama:
        """Analiza un turno y valida como máximo dos respuestas del modelo."""
        ultimo_error = "respuesta inválida"
        for intento in range(2):
            texto = self._consultar(sistema, mensaje, intento > 0)
            try:
                return self._validar(texto)
            except (ValidationError, json.JSONDecodeError, ValueError) as error:
                ultimo_error = str(error)
        raise ErrorComprension(f"Ollama no devolvió JSON válido: {ultimo_error}")

    def _consultar(self, sistema: str, mensaje: str, reparar: bool) -> str:
        instruccion = mensaje
        if reparar:
            instruccion += "\nDevuelve solo JSON válido conforme al esquema indicado."
        try:
            respuesta = httpx.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.modelo,
                    "stream": False,
                    "format": RespuestaOllama.model_json_schema(),
                    "messages": [
                        {"role": "system", "content": sistema},
                        {"role": "user", "content": instruccion},
                    ],
                },
                timeout=self.espera_segundos,
            )
            respuesta.raise_for_status()
            return respuesta.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, TypeError) as error:
            raise ErrorComprension(f"No fue posible consultar Ollama: {error}") from error

    @staticmethod
    def _validar(texto: str) -> RespuestaOllama:
        try:
            return RespuestaOllama.model_validate_json(texto)
        except (ValidationError, json.JSONDecodeError):
            coincidencia = re.search(r"\{.*\}", texto, re.DOTALL)
            if not coincidencia:
                raise ValueError("No se encontró un objeto JSON") from None
            return RespuestaOllama.model_validate_json(coincidencia.group())
