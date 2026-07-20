"""Pruebas del inventario y sus traslapes."""

from datetime import date
from pathlib import Path

import pytest

from aplicacion.base_datos.conexion import conectar, migrar
from aplicacion.disponibilidad.servicio import ServicioDisponibilidad, TipoHabitacion


@pytest.fixture
def servicio(tmp_path: Path) -> ServicioDisponibilidad:
    conexion = conectar(tmp_path / "inventario.db")
    migrar(conexion, Path("migraciones"))
    return ServicioDisponibilidad(conexion)


def test_inventario_inicial_establecido(servicio: ServicioDisponibilidad) -> None:
    resultado = servicio.consultar(date(2027, 1, 10), date(2027, 1, 12))
    assert [(item.tipo, item.disponibles) for item in resultado] == [
        (TipoHabitacion.DOBLE, 15),
        (TipoHabitacion.KING, 5),
        (TipoHabitacion.SUITE, 5),
    ]


def test_bloquea_traslapes_y_libera(servicio: ServicioDisponibilidad) -> None:
    bloqueo = servicio.bloquear("dobles", date(2027, 1, 10), date(2027, 1, 12), cantidad=3)
    durante = servicio.consultar(date(2027, 1, 11), date(2027, 1, 13))[0]
    siguiente = servicio.consultar(date(2027, 1, 12), date(2027, 1, 13))[0]
    assert durante.disponibles == 12
    assert siguiente.disponibles == 15
    assert servicio.liberar(bloqueo) is True
    assert servicio.liberar(bloqueo) is False
    assert servicio.consultar(date(2027, 1, 11), date(2027, 1, 13))[0].disponibles == 15


def test_impide_sobreventa(servicio: ServicioDisponibilidad) -> None:
    entrada, salida = date(2027, 2, 1), date(2027, 2, 3)
    servicio.bloquear("suite", entrada, salida, cantidad=5)
    with pytest.raises(ValueError, match="suficientes"):
        servicio.bloquear("suite", entrada, salida)


def test_bloqueo_multiple_es_atomico(servicio: ServicioDisponibilidad) -> None:
    entrada, salida = date(2027, 10, 1), date(2027, 10, 2)
    servicio.bloquear("suite", entrada, salida, cantidad=5)

    with pytest.raises(ValueError, match="suficientes"):
        servicio.bloquear_varios({"doble": 1, "suite": 1}, entrada, salida)

    resultados = {item.tipo.value: item for item in servicio.consultar(entrada, salida)}
    assert resultados["doble"].disponibles == 15


def test_rechaza_tipo_y_fechas_invalidas(servicio: ServicioDisponibilidad) -> None:
    with pytest.raises(ValueError, match="no reconocido"):
        servicio.bloquear("presidencial", date(2027, 1, 1), date(2027, 1, 2))
    with pytest.raises(ValueError, match="posterior"):
        servicio.consultar(date(2027, 1, 2), date(2027, 1, 2))
