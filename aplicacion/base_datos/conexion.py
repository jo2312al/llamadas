"""Conexiones y migraciones SQLite seguras."""

import sqlite3
from pathlib import Path


def conectar(ruta: Path) -> sqlite3.Connection:
    """Abre SQLite con claves foráneas, WAL y espera ante bloqueos."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta, timeout=10)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.execute("PRAGMA journal_mode = WAL")
    return conexion


def migrar(conexion: sqlite3.Connection, ruta_migraciones: Path) -> None:
    """Aplica migraciones SQL idempotentes en orden alfabético."""
    conexion.execute(
        """CREATE TABLE IF NOT EXISTS migraciones (
        nombre TEXT PRIMARY KEY, aplicada_en TEXT NOT NULL
    )"""
    )
    aplicadas = {fila[0] for fila in conexion.execute("SELECT nombre FROM migraciones")}
    for archivo in sorted(ruta_migraciones.glob("*.sql")):
        if archivo.name in aplicadas:
            continue
        with conexion:
            conexion.executescript(archivo.read_text(encoding="utf-8"))
            conexion.execute(
                "INSERT INTO migraciones(nombre, aplicada_en) VALUES (?, datetime('now'))",
                (archivo.name,),
            )
