"""Caché determinística de respuestas sintetizadas."""

import hashlib
from pathlib import Path


class CacheAudio:
    """Asocia texto y voz con un WAV sin usar el texto como nombre de archivo."""

    def __init__(self, directorio: Path) -> None:
        self.directorio = directorio

    def ruta(self, texto: str, identificador_voz: str) -> Path:
        """Devuelve una ruta estable SHA-256 para una frase y modelo."""
        normalizado = " ".join(texto.casefold().split())
        huella = hashlib.sha256(f"{identificador_voz}\0{normalizado}".encode()).hexdigest()
        return self.directorio / f"{huella}.wav"
