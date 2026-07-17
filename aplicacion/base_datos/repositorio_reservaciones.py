"""Repositorio de solicitudes, aislado de Ollama."""

import sqlite3

from aplicacion.modelos.reservacion import SolicitudReservacion


def guardar_solicitud(
    conexion: sqlite3.Connection, solicitud: SolicitudReservacion
) -> SolicitudReservacion:
    """Persiste una solicitud validada y devuelve el mismo agregado."""
    with conexion:
        conexion.execute(
            """INSERT INTO solicitudes_reservacion
            (identificador_solicitud, identificador_llamada, fecha_creacion, estado,
             datos_json, resumen_conversacion, nivel_confianza, requiere_revision,
             motivo_revision, total_estimado, moneda)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                solicitud.identificador_solicitud,
                solicitud.identificador_llamada,
                solicitud.fecha_creacion.isoformat(),
                solicitud.estado,
                solicitud.datos.model_dump_json(),
                solicitud.resumen_conversacion,
                solicitud.nivel_confianza,
                solicitud.requiere_revision,
                solicitud.motivo_revision,
                solicitud.total_estimado,
                solicitud.moneda,
            ),
        )
    return solicitud
