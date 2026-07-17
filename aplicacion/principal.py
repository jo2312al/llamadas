"""Interfaz CLI para operar y diagnosticar el núcleo."""

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

from aplicacion.base_datos.conexion import conectar, migrar
from aplicacion.configuracion import cargar_configuracion


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
    for nombre, binario in {"whisper": "whisper-cli", "piper": "piper"}.items():
        resultados[nombre] = "disponible" if shutil.which(binario) else "no instalado"
    libre = shutil.disk_usage(configuracion.ruta_base_datos.parent).free // (1024 * 1024)
    resultados["disco_libre_mib"] = str(libre)
    for clave, valor in resultados.items():
        print(f"{clave}: {valor}")
    return 0 if resultados["base_datos"] == "correcta" else 1


def main() -> None:
    """Ejecuta comandos administrativos y el flujo básico por terminal."""
    analizador = argparse.ArgumentParser(description="Agente telefónico del hotel")
    analizador.add_argument("comando", choices=["migrar", "salud", "conversar"])
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
    else:
        print(f"Bienvenido a {configuracion.nombre_hotel}. ¿En qué puedo ayudarle?")
        print("Modo terminal de Fase 1. Escriba 'salir' para terminar.")
        while input("Cliente: ").strip().lower() != "salir":
            print("Agente: Registraré su solicitud; por favor proporcione un dato a la vez.")


if __name__ == "__main__":
    main()
