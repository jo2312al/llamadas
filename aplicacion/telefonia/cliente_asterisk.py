"""Cliente REST mínimo y seguro para Asterisk ARI."""

from pathlib import Path
from urllib.parse import quote

import httpx


class ErrorAsterisk(RuntimeError):
    """Fallo controlado de comunicación o acción ARI."""


class ClienteAsterisk:
    """Ejecuta acciones ARI permitidas sin exponer una API genérica."""

    def __init__(
        self,
        url: str,
        usuario: str,
        contrasena: str,
        espera_segundos: float = 5,
        transporte: httpx.BaseTransport | None = None,
    ) -> None:
        self._cliente = httpx.Client(
            base_url=f"{url.rstrip('/')}/ari/",
            auth=(usuario, contrasena),
            timeout=espera_segundos,
            transport=transporte,
        )

    def cerrar(self) -> None:
        """Libera conexiones HTTP persistentes."""
        self._cliente.close()

    def comprobar(self) -> bool:
        """Comprueba ARI mediante su recurso de información."""
        self._solicitar("GET", "asterisk/info")
        return True

    def responder(self, canal: str) -> None:
        """Contesta un canal que entró a Stasis."""
        self._solicitar("POST", f"channels/{quote(canal, safe='')}/answer")

    def reproducir(self, canal: str, sonido: str) -> None:
        """Reproduce un sonido autorizado del catálogo de Asterisk."""
        if not sonido or any(caracter in sonido for caracter in ("..", "\\", "\0")):
            raise ValueError("Nombre de sonido no permitido")
        self._solicitar(
            "POST",
            f"channels/{quote(canal, safe='')}/play",
            params={"media": f"sound:{sonido}"},
        )

    def reproducir_archivo(self, canal: str, audio: Path) -> None:
        """Reproduce un archivo ya ubicado en el directorio de sonidos."""
        self.reproducir(canal, audio.stem)

    def grabar(
        self,
        canal: str,
        nombre: str,
        duracion_maxima: int = 20,
        silencio_maximo: int = 3,
    ) -> None:
        """Graba audio del canal hasta silencio o duración máxima."""
        self._validar_nombre_grabacion(nombre)
        self._solicitar(
            "POST",
            f"channels/{quote(canal, safe='')}/record",
            params={
                "name": nombre,
                "format": "wav",
                "maxDurationSeconds": duracion_maxima,
                "maxSilenceSeconds": silencio_maximo,
                "ifExists": "overwrite",
                "beep": "false",
                "terminateOn": "none",
            },
        )

    def descargar_grabacion(self, nombre: str, destino: Path) -> Path:
        """Descarga una grabación almacenada por Asterisk a una ruta controlada."""
        self._validar_nombre_grabacion(nombre)
        respuesta = self._solicitar("GET", f"recordings/stored/{quote(nombre, safe='')}/file")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(respuesta.content)
        return destino

    @staticmethod
    def _validar_nombre_grabacion(nombre: str) -> None:
        if not nombre or not nombre.replace("-", "").isalnum():
            raise ValueError("Nombre de grabación no permitido")

    def transferir(self, canal: str, tecnologia: str, destino: str) -> None:
        """Redirige el canal a un endpoint configurado, sin generar destinos libres."""
        if tecnologia not in {"PJSIP", "SIP"} or not destino.replace("-", "").isalnum():
            raise ValueError("Endpoint de transferencia no permitido")
        self._solicitar(
            "POST",
            f"channels/{quote(canal, safe='')}/redirect",
            params={"endpoint": f"{tecnologia}/{destino}"},
        )

    def colgar(self, canal: str, motivo: str = "normal") -> None:
        """Finaliza un canal con una causa ARI permitida."""
        causas = {"normal": "normal", "ocupado": "busy", "congestion": "congestion"}
        if motivo not in causas:
            raise ValueError("Motivo de colgado no permitido")
        self._solicitar(
            "DELETE",
            f"channels/{quote(canal, safe='')}",
            params={"reason_code": causas[motivo]},
        )

    def _solicitar(self, metodo: str, ruta: str, **argumentos: object) -> httpx.Response:
        try:
            respuesta = self._cliente.request(metodo, ruta, **argumentos)
            respuesta.raise_for_status()
            return respuesta
        except httpx.TimeoutException as error:
            raise ErrorAsterisk("Asterisk excedió el tiempo permitido") from error
        except httpx.HTTPStatusError as error:
            codigo = error.response.status_code
            raise ErrorAsterisk(f"Asterisk rechazó la acción con HTTP {codigo}") from error
        except httpx.RequestError as error:
            raise ErrorAsterisk("No fue posible conectar con Asterisk") from error
