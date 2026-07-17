"""Orquestación determinística de sesiones a partir de eventos ARI."""

import asyncio
import contextlib
import logging
from pathlib import Path
from uuid import uuid4

from aplicacion.reconocimiento_voz.servicio_whisper import ErrorWhisper, ServicioWhisper
from aplicacion.telefonia.cliente_asterisk import ClienteAsterisk, ErrorAsterisk
from aplicacion.telefonia.eventos_ari import ReceptorEventosAri
from aplicacion.telefonia.eventos_llamada import EventoLlamada, TipoEvento
from aplicacion.telefonia.sesion_llamada import GestorSesiones

REGISTRO = logging.getLogger("telefonia.ari")


class OrquestadorAri:
    """Relaciona eventos ARI con sesiones sin delegar negocio al modelo."""

    def __init__(
        self,
        cliente: ClienteAsterisk,
        gestor: GestorSesiones,
        sonido_bienvenida: str | None = None,
        whisper: ServicioWhisper | None = None,
        ruta_grabaciones: Path = Path("datos/grabaciones"),
    ) -> None:
        self.cliente = cliente
        self.gestor = gestor
        self.sonido_bienvenida = sonido_bienvenida
        self.whisper = whisper
        self.ruta_grabaciones = ruta_grabaciones

    def procesar(self, evento: EventoLlamada) -> None:
        """Procesa un evento conocido con operaciones idempotentes.

        Args:
            evento: Evento ARI previamente validado.

        Returns:
            No devuelve valor.

        Raises:
            ErrorAsterisk: Si Asterisk rechaza una acción necesaria.
        """
        canal = evento.identificador_canal
        if evento.tipo == TipoEvento.INICIO:
            if self.gestor.obtener(canal) is not None:
                REGISTRO.warning("Se ignoró StasisStart duplicado", extra={"llamada": canal})
                return
            self.gestor.crear(canal)
            try:
                self.cliente.responder(canal)
                if self.sonido_bienvenida:
                    self.cliente.reproducir(canal, self.sonido_bienvenida)
                elif self.whisper:
                    self._iniciar_grabacion(canal)
            except ErrorAsterisk:
                self.gestor.finalizar(canal)
                raise
            REGISTRO.info("Llamada contestada", extra={"llamada": canal})
        elif evento.tipo == TipoEvento.FIN:
            if self.gestor.finalizar(canal):
                REGISTRO.info("Sesión de llamada finalizada", extra={"llamada": canal})
        elif evento.tipo == TipoEvento.REPRODUCCION_TERMINADA and self.whisper:
            if self.gestor.obtener(canal):
                self._iniciar_grabacion(canal)
        elif evento.tipo == TipoEvento.GRABACION_TERMINADA and self.whisper:
            self._transcribir(evento)

    def _iniciar_grabacion(self, canal: str) -> None:
        nombre = f"hotel-{uuid4().hex}"
        self.cliente.grabar(canal, nombre)
        REGISTRO.info("Escucha iniciada", extra={"llamada": canal})

    def _transcribir(self, evento: EventoLlamada) -> None:
        sesion = self.gestor.obtener(evento.identificador_canal)
        nombre = evento.identificador_recurso
        if sesion is None or not nombre or self.whisper is None:
            return
        audio = self.ruta_grabaciones / f"{nombre}.wav"
        try:
            self.cliente.descargar_grabacion(nombre, audio)
            transcripcion = self.whisper.transcribir(audio)
            sesion.ultimo_mensaje = transcripcion.texto
            REGISTRO.info(
                "Transcripción obtenida (%d caracteres)",
                len(transcripcion.texto),
                extra={"llamada": evento.identificador_canal},
            )
        except (ErrorAsterisk, ErrorWhisper, OSError):
            sesion.errores.append("No fue posible transcribir la intervención")
            REGISTRO.exception(
                "Falló la transcripción", extra={"llamada": evento.identificador_canal}
            )
        finally:
            audio.unlink(missing_ok=True)
            try:
                self.cliente.eliminar_grabacion(nombre)
            except ErrorAsterisk:
                REGISTRO.warning(
                    "No fue posible eliminar la grabación procesada",
                    extra={"llamada": evento.identificador_canal},
                )

    def finalizar_vencidas(self) -> int:
        """Cuelga y retira llamadas que excedieron el límite configurado."""
        finalizadas = 0
        for sesion in self.gestor.sesiones_vencidas():
            try:
                self.cliente.colgar(sesion.identificador_llamada)
            except ErrorAsterisk:
                REGISTRO.exception(
                    "No fue posible colgar una llamada vencida",
                    extra={"llamada": sesion.identificador_llamada},
                )
            finally:
                self.gestor.finalizar(sesion.identificador_llamada)
                finalizadas += 1
        return finalizadas


async def ejecutar_eventos_ari(
    receptor: ReceptorEventosAri,
    orquestador: OrquestadorAri,
    detener: asyncio.Event,
) -> None:
    """Consume eventos y vigila límites hasta recibir una orden de salida."""
    consumidor = asyncio.create_task(_consumir(receptor, orquestador))
    vigilancia = asyncio.create_task(_vigilar_limites(orquestador, detener))
    espera_salida = asyncio.create_task(detener.wait())
    tareas = {consumidor, vigilancia, espera_salida}
    terminadas, _pendientes = await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
    error = next((tarea.exception() for tarea in terminadas if not tarea.cancelled()), None)
    for tarea in tareas:
        if not tarea.done():
            tarea.cancel()
    for tarea in tareas:
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
    if error:
        raise error


async def _consumir(receptor: ReceptorEventosAri, orquestador: OrquestadorAri) -> None:
    async for evento in receptor.eventos():
        orquestador.procesar(evento)


async def _vigilar_limites(orquestador: OrquestadorAri, detener: asyncio.Event) -> None:
    while not detener.is_set():
        orquestador.finalizar_vencidas()
        try:
            await asyncio.wait_for(detener.wait(), timeout=5)
        except TimeoutError:
            continue
