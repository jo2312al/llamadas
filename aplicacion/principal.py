"""Interfaz CLI para operar y diagnosticar el núcleo."""

import argparse
import shutil
import signal
import sqlite3
import sys
import time
from pathlib import Path

from aplicacion.base_datos.conexion import conectar, migrar
from aplicacion.configuracion import cargar_configuracion
from aplicacion.telefonia.cliente_asterisk import ClienteAsterisk, ErrorAsterisk


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
