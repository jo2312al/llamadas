"""Consulta y bloqueo transaccional de inventario por estancia."""

import sqlite3
from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class TipoHabitacion(StrEnum):
    """Tipos de habitación administrados por el hotel."""

    DOBLE = "doble"
    KING = "king"
    SUITE = "suite"


class DisponibilidadTipo(BaseModel):
    """Existencias calculadas para un tipo y rango concreto."""

    tipo: TipoHabitacion
    total: int = Field(ge=0)
    ocupadas: int = Field(ge=0)
    disponibles: int = Field(ge=0)


def normalizar_tipo(valor: str | TipoHabitacion) -> TipoHabitacion:
    """Normaliza nombres admitidos sin aceptar categorías desconocidas."""
    if isinstance(valor, TipoHabitacion):
        return valor
    normalizado = valor.strip().casefold()
    alias = {
        "doble": TipoHabitacion.DOBLE,
        "dobles": TipoHabitacion.DOBLE,
        "king": TipoHabitacion.KING,
        "suite": TipoHabitacion.SUITE,
        "suites": TipoHabitacion.SUITE,
    }
    try:
        return alias[normalizado]
    except KeyError as error:
        raise ValueError("Tipo de habitación no reconocido") from error


class ServicioDisponibilidad:
    """Administra cupo mediante transacciones SQLite serializadas."""

    def __init__(self, conexion: sqlite3.Connection) -> None:
        self.conexion = conexion

    def consultar(self, fecha_entrada: date, fecha_salida: date) -> list[DisponibilidadTipo]:
        """Devuelve disponibilidad para todas las categorías."""
        self._validar_fechas(fecha_entrada, fecha_salida)
        filas = self.conexion.execute(
            """
            SELECT i.tipo, i.cantidad_total, COALESCE(SUM(b.cantidad), 0)
            FROM inventario_habitaciones AS i
            LEFT JOIN bloqueos_inventario AS b
              ON b.tipo = i.tipo
             AND b.estado = 'activo'
             AND b.fecha_entrada < ?
             AND b.fecha_salida > ?
            GROUP BY i.tipo, i.cantidad_total
            ORDER BY CASE i.tipo WHEN 'doble' THEN 1 WHEN 'king' THEN 2 ELSE 3 END
            """,
            (fecha_salida.isoformat(), fecha_entrada.isoformat()),
        ).fetchall()
        return [
            DisponibilidadTipo(
                tipo=tipo,
                total=total,
                ocupadas=ocupadas,
                disponibles=max(total - ocupadas, 0),
            )
            for tipo, total, ocupadas in filas
        ]

    def bloquear(
        self,
        tipo: str | TipoHabitacion,
        fecha_entrada: date,
        fecha_salida: date,
        cantidad: int = 1,
        referencia: str | None = None,
    ) -> str:
        """Bloquea cupo solo si toda la cantidad continúa disponible."""
        categoria = normalizar_tipo(tipo)
        self._validar_fechas(fecha_entrada, fecha_salida)
        if cantidad < 1:
            raise ValueError("La cantidad debe ser positiva")
        identificador = str(uuid4())
        try:
            self.conexion.execute("BEGIN IMMEDIATE")
            disponibilidad = {
                item.tipo: item for item in self.consultar(fecha_entrada, fecha_salida)
            }[categoria]
            if disponibilidad.disponibles < cantidad:
                raise ValueError("No hay suficientes habitaciones disponibles")
            self.conexion.execute(
                """
                INSERT INTO bloqueos_inventario
                (identificador_bloqueo, tipo, fecha_entrada, fecha_salida,
                 cantidad, estado, referencia, fecha_creacion)
                VALUES (?, ?, ?, ?, ?, 'activo', ?, ?)
                """,
                (
                    identificador,
                    categoria,
                    fecha_entrada.isoformat(),
                    fecha_salida.isoformat(),
                    cantidad,
                    referencia,
                    datetime.now(UTC).isoformat(),
                ),
            )
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return identificador

    def liberar(self, identificador_bloqueo: str) -> bool:
        """Libera idempotentemente un bloqueo existente."""
        with self.conexion:
            cursor = self.conexion.execute(
                """UPDATE bloqueos_inventario SET estado = 'liberado'
                   WHERE identificador_bloqueo = ? AND estado = 'activo'""",
                (identificador_bloqueo,),
            )
        return cursor.rowcount == 1

    @staticmethod
    def _validar_fechas(fecha_entrada: date, fecha_salida: date) -> None:
        if fecha_salida <= fecha_entrada:
            raise ValueError("La fecha de salida debe ser posterior a la entrada")
