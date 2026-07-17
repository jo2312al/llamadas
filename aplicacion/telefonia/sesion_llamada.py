"""Registro concurrente y aislado de sesiones telefónicas."""

import threading
from datetime import UTC, datetime, timedelta

from aplicacion.modelos.conversacion import SesionLlamada


class GestorSesiones:
    """Mantiene una sesión por canal y aplica límites de duración."""

    def __init__(self, duracion_maxima_segundos: int = 900) -> None:
        if duracion_maxima_segundos < 30:
            raise ValueError("La duración máxima debe ser al menos 30 segundos")
        self.duracion_maxima = timedelta(seconds=duracion_maxima_segundos)
        self._sesiones: dict[str, SesionLlamada] = {}
        self._bloqueo = threading.RLock()

    def crear(self, identificador_canal: str) -> SesionLlamada:
        """Crea una sesión única para un canal nuevo."""
        with self._bloqueo:
            if identificador_canal in self._sesiones:
                raise ValueError("El canal ya tiene una sesión activa")
            sesion = SesionLlamada(identificador_llamada=identificador_canal)
            self._sesiones[identificador_canal] = sesion
            return sesion

    def obtener(self, identificador_canal: str) -> SesionLlamada | None:
        """Obtiene una sesión sin crearla implícitamente."""
        with self._bloqueo:
            return self._sesiones.get(identificador_canal)

    def finalizar(self, identificador_canal: str) -> SesionLlamada | None:
        """Retira y devuelve una sesión terminada."""
        with self._bloqueo:
            return self._sesiones.pop(identificador_canal, None)

    def sesiones_vencidas(self, ahora: datetime | None = None) -> list[SesionLlamada]:
        """Devuelve sesiones que excedieron el límite sin eliminarlas."""
        instante = ahora or datetime.now(UTC)
        with self._bloqueo:
            return [
                sesion
                for sesion in self._sesiones.values()
                if instante - sesion.fecha_inicio >= self.duracion_maxima
            ]
