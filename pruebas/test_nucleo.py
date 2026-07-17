"""Pruebas unitarias del núcleo determinístico."""

from datetime import date
from pathlib import Path

import pytest

from aplicacion.base_datos.conexion import conectar, migrar
from aplicacion.base_datos.repositorio_reservaciones import guardar_solicitud
from aplicacion.conversacion.maquina_estados import TransicionInvalida, transicionar
from aplicacion.conversacion.recopilador_datos import campos_faltantes
from aplicacion.modelos.conversacion import EstadoConversacion, SesionLlamada
from aplicacion.modelos.reservacion import DatosReservacion, SolicitudReservacion


def test_transicion_valida() -> None:
    sesion = SesionLlamada(identificador_llamada="prueba")
    transicionar(sesion, EstadoConversacion.IDENTIFICAR_INTENCION)
    assert sesion.estado_actual == EstadoConversacion.IDENTIFICAR_INTENCION


def test_transicion_invalida() -> None:
    sesion = SesionLlamada(identificador_llamada="prueba")
    with pytest.raises(TransicionInvalida):
        transicionar(sesion, EstadoConversacion.GUARDAR_SOLICITUD)


def test_calcula_noches_y_detecta_campos() -> None:
    datos = DatosReservacion(
        fecha_entrada=date(2027, 1, 2), fecha_salida=date(2027, 1, 4), numero_adultos=2
    )
    assert datos.numero_noches == 2
    assert "nombre_completo" in campos_faltantes(datos)
    assert "numero_adultos" not in campos_faltantes(datos)


def test_rechaza_fechas_invertidas() -> None:
    with pytest.raises(ValueError):
        DatosReservacion(fecha_entrada=date(2027, 1, 4), fecha_salida=date(2027, 1, 2))


def test_persistencia(tmp_path: Path) -> None:
    conexion = conectar(tmp_path / "prueba.db")
    migrar(conexion, Path("migraciones"))
    solicitud = SolicitudReservacion(
        identificador_llamada="llamada-1",
        datos=DatosReservacion(numero_adultos=2),
    )
    guardar_solicitud(conexion, solicitud)
    total = conexion.execute("SELECT count(*) FROM solicitudes_reservacion").fetchone()[0]
    conexion.close()
    assert total == 1
