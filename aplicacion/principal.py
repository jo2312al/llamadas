"""Interfaz CLI para operar y diagnosticar el núcleo."""

import argparse
import asyncio
import contextlib
import logging
import shutil
import signal
import sqlite3
import sys
import time
from pathlib import Path

from aplicacion.base_datos.conexion import conectar, migrar
from aplicacion.configuracion import Configuracion, cargar_configuracion
from aplicacion.conversacion.flujo_reservacion import FlujoReservacion
from aplicacion.disponibilidad.servicio import ServicioDisponibilidad
from aplicacion.lenguaje.cliente_ollama import ClienteOllama
from aplicacion.reconocimiento_voz.servicio_whisper import ServicioWhisper
from aplicacion.sintesis_voz.cache_audio import CacheAudio
from aplicacion.sintesis_voz.publicador_asterisk import PublicadorAudioAsterisk
from aplicacion.sintesis_voz.servicio_piper import ServicioPiper
from aplicacion.telefonia.cliente_asterisk import ClienteAsterisk, ErrorAsterisk
from aplicacion.telefonia.eventos_ari import ReceptorEventosAri
from aplicacion.telefonia.orquestador_ari import OrquestadorAri, ejecutar_eventos_ari
from aplicacion.telefonia.sesion_llamada import GestorSesiones


def configurar_registros() -> None:
    """Inicializa categorías de logging para journald sin datos sensibles."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def ejecutar_servicio(ruta_configuracion: Path) -> None:
    """Mantiene activo el proceso supervisado tras preparar su base de datos.

    Args:
        ruta_configuracion: Archivo YAML validado para el entorno.

    Returns:
        Esta función no retorna durante la operación normal.

    Raises:
        OSError: Si no se puede acceder a la configuración o persistencia.
        ValueError: Si la configuración no es válida.

    Side Effects:
        Aplica migraciones pendientes y permanece a la espera de señales.
    """
    configuracion = cargar_configuracion(ruta_configuracion)
    conexion = conectar(configuracion.ruta_base_datos)
    migrar(conexion, Path("migraciones"))
    conexion.close()
    if configuracion.contrasena_ari:
        asyncio.run(_ejecutar_servicio_ari(configuracion))
        return
    terminar = False

    def solicitar_salida(_senal: int, _marco: object) -> None:
        nonlocal terminar
        terminar = True

    signal.signal(signal.SIGTERM, solicitar_salida)
    signal.signal(signal.SIGINT, solicitar_salida)
    print("Servicio del agente telefónico iniciado", flush=True)
    while not terminar:
        time.sleep(1)
    print("Servicio del agente telefónico detenido", flush=True)


async def _ejecutar_servicio_ari(configuracion: Configuracion) -> None:
    """Ejecuta el consumidor ARI hasta recibir SIGTERM o SIGINT."""
    if not configuracion.contrasena_ari:
        raise ValueError("La configuración ARI está incompleta")
    secreto = configuracion.contrasena_ari.get_secret_value()
    cliente = ClienteAsterisk(configuracion.url_ari, configuracion.usuario_ari, secreto)
    receptor = ReceptorEventosAri(
        configuracion.url_ari,
        configuracion.aplicacion_ari,
        configuracion.usuario_ari,
        secreto,
    )
    gestor = GestorSesiones(configuracion.duracion_maxima_llamada_segundos)
    whisper = ServicioWhisper(
        configuracion.binario_whisper,
        configuracion.modelo_whisper,
        configuracion.espera_whisper_segundos,
    )
    ollama = None
    if not configuracion.modo_simulacion:
        ollama = ClienteOllama(
            configuracion.url_ollama,
            configuracion.modelo_ollama,
            configuracion.espera_ollama_segundos,
        )
    piper = ServicioPiper(
        configuracion.binario_piper,
        configuracion.modelo_piper,
        CacheAudio(configuracion.ruta_cache_audio / "piper"),
        configuracion.espera_piper_segundos,
    )
    publicador = PublicadorAudioAsterisk(Path("/var/lib/asterisk/sounds/hotel/generado"))
    conexion_disponibilidad = conectar(configuracion.ruta_base_datos)
    flujo_reservacion = FlujoReservacion(ServicioDisponibilidad(conexion_disponibilidad))
    detener = asyncio.Event()
    bucle = asyncio.get_running_loop()
    for senal in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            bucle.add_signal_handler(senal, detener.set)
    print("Servicio ARI del agente telefónico iniciado", flush=True)
    try:
        await ejecutar_eventos_ari(
            receptor,
            OrquestadorAri(
                cliente,
                gestor,
                configuracion.sonido_bienvenida,
                whisper,
                configuracion.ruta_cache_audio / "grabaciones",
                ollama,
                piper,
                publicador,
                flujo_reservacion,
            ),
            detener,
        )
    finally:
        cliente.cerrar()
        conexion_disponibilidad.close()
        print("Servicio ARI del agente telefónico detenido", flush=True)


def verificar_salud(ruta_configuracion: Path) -> int:
    """Comprueba configuración, SQLite, binarios y espacio sin exponer secretos."""
    configuracion = cargar_configuracion(ruta_configuracion)
    resultados = {"configuracion": "correcta"}
    try:
        conexion = conectar(configuracion.ruta_base_datos)
        conexion.execute("SELECT 1").fetchone()
        conexion.close()
        resultados["base_datos"] = "correcta"
    except sqlite3.Error as error:
        resultados["base_datos"] = f"error: {error}"
    componentes = {
        "whisper": configuracion.binario_whisper,
        "modelo_whisper": configuracion.modelo_whisper,
        "piper": configuracion.binario_piper,
        "modelo_piper": configuracion.modelo_piper,
    }
    for nombre, ruta in componentes.items():
        resultados[nombre] = "disponible" if ruta.is_file() else "no instalado"
    if configuracion.contrasena_ari:
        cliente_asterisk = ClienteAsterisk(
            configuracion.url_ari,
            configuracion.usuario_ari,
            configuracion.contrasena_ari.get_secret_value(),
        )
        try:
            cliente_asterisk.comprobar()
            resultados["asterisk_ari"] = "correcto"
        except ErrorAsterisk as error:
            resultados["asterisk_ari"] = f"error: {error}"
        finally:
            cliente_asterisk.cerrar()
    else:
        resultados["asterisk_ari"] = "credencial no configurada"
    libre = shutil.disk_usage(configuracion.ruta_base_datos.parent).free // (1024 * 1024)
    resultados["disco_libre_mib"] = str(libre)
    for clave, valor in resultados.items():
        print(f"{clave}: {valor}")
    servicios_correctos = resultados["base_datos"] == "correcta" and not resultados.get(
        "asterisk_ari", ""
    ).startswith("error")
    return 0 if servicios_correctos else 1


def main() -> None:
    """Ejecuta comandos administrativos y el flujo básico por terminal."""
    configurar_registros()
    analizador = argparse.ArgumentParser(description="Agente telefónico del hotel")
    analizador.add_argument("comando", choices=["migrar", "salud", "conversar", "servir"])
    analizador.add_argument("--configuracion", default="configuracion/configuracion_ejemplo.yaml")
    argumentos = analizador.parse_args()
    ruta = Path(argumentos.configuracion)
    configuracion = cargar_configuracion(ruta)
    if argumentos.comando == "migrar":
        conexion = conectar(configuracion.ruta_base_datos)
        migrar(conexion, Path("migraciones"))
        print("Migraciones aplicadas correctamente")
    elif argumentos.comando == "salud":
        sys.exit(verificar_salud(ruta))
    elif argumentos.comando == "conversar":
        print(f"Bienvenido a {configuracion.nombre_hotel}. ¿En qué puedo ayudarle?")
        print("Modo terminal de Fase 1. Escriba 'salir' para terminar.")
        while input("Cliente: ").strip().lower() != "salir":
            print("Agente: Registraré su solicitud; por favor proporcione un dato a la vez.")
    else:
        ejecutar_servicio(ruta)


if __name__ == "__main__":
    main()
