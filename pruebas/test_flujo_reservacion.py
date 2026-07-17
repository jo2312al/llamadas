"""Pruebas del diálogo determinístico conectado al inventario."""

from datetime import date
from pathlib import Path

from aplicacion.base_datos.conexion import conectar, migrar
from aplicacion.conversacion.flujo_reservacion import (
    FlujoReservacion,
    extraer_fecha,
    extraer_numero,
)
from aplicacion.disponibilidad.servicio import ServicioDisponibilidad
from aplicacion.modelos.conversacion import EstadoConversacion, SesionLlamada


def crear_flujo(tmp_path: Path) -> tuple[FlujoReservacion, ServicioDisponibilidad]:
    conexion = conectar(tmp_path / "dialogo.db")
    migrar(conexion, Path("migraciones"))
    disponibilidad = ServicioDisponibilidad(conexion)
    return FlujoReservacion(disponibilidad), disponibilidad


def test_extrae_fechas_y_numeros_hablados() -> None:
    assert extraer_fecha("el 10 de agosto de 2027") == date(2027, 8, 10)
    assert extraer_fecha("12 de agosto", date(2027, 8, 10)) == date(2027, 8, 12)
    assert extraer_fecha("2027-09-03") == date(2027, 9, 3)
    assert extraer_numero("seríamos dos adultos") == 2


def test_recopila_un_dato_por_turno_y_consulta_inventario(tmp_path: Path) -> None:
    flujo, disponibilidad = crear_flujo(tmp_path)
    disponibilidad.bloquear("doble", date(2027, 8, 10), date(2027, 8, 12))
    sesion = SesionLlamada(identificador_llamada="llamada-1")

    assert "fecha" in flujo.procesar(sesion, "Quiero reservar")[1]
    assert "salida" in flujo.procesar(sesion, "10 de agosto de 2027")[1]
    assert "doble" in flujo.procesar(sesion, "12 de agosto de 2027")[1]
    assert "adultos" in flujo.procesar(sesion, "habitación doble")[1]
    intencion, respuesta = flujo.procesar(sesion, "dos adultos")

    assert intencion == "reservacion"
    assert respuesta == "Hay 14 habitaciones doble disponibles. ¿Desea continuar con la solicitud?"
    assert sesion.datos.numero_noches == 2
    assert sesion.datos.numero_adultos == 2
    assert sesion.estado_actual == EstadoConversacion.PRESENTAR_OPCIONES


def test_repregunta_fecha_invalida_y_reporta_sin_cupo(tmp_path: Path) -> None:
    flujo, disponibilidad = crear_flujo(tmp_path)
    disponibilidad.bloquear("suite", date(2027, 9, 1), date(2027, 9, 3), cantidad=5)
    sesion = SesionLlamada(identificador_llamada="llamada-2")
    flujo.procesar(sesion, "Necesito una habitación")
    assert "No comprendí" in flujo.procesar(sesion, "el próximo mes")[1]
    flujo.procesar(sesion, "1 de septiembre de 2027")
    flujo.procesar(sesion, "3 de septiembre de 2027")
    flujo.procesar(sesion, "suite")
    respuesta = flujo.procesar(sesion, "2")[1]
    assert respuesta == "No hay habitaciones suite disponibles en esas fechas."


def test_confirma_contacto_guarda_y_bloquea_inventario(tmp_path: Path) -> None:
    flujo, disponibilidad = crear_flujo(tmp_path)
    sesion = SesionLlamada(identificador_llamada="llamada-3")
    for mensaje in (
        "Quiero reservar",
        "10 de agosto de 2027",
        "12 de agosto de 2027",
        "king",
        "dos adultos",
    ):
        flujo.procesar(sesion, mensaje)

    assert "nombre" in flujo.procesar(sesion, "sí, continuar")[1]
    assert "teléfono" in flujo.procesar(sesion, "Ana Pérez López")[1]
    assert "Autoriza" in flujo.procesar(sesion, "5512345678")[1]
    respuesta = flujo.procesar(sesion, "sí autorizo")[1]

    assert "registrada correctamente" in respuesta
    assert sesion.estado_actual == EstadoConversacion.FINALIZAR
    assert sesion.identificador_solicitud is not None
    assert (
        disponibilidad.conexion.execute("SELECT count(*) FROM solicitudes_reservacion").fetchone()[
            0
        ]
        == 1
    )
    assert disponibilidad.consultar(date(2027, 8, 10), date(2027, 8, 12))[1].disponibles == 4


def test_no_envia_ni_bloquea_sin_consentimiento(tmp_path: Path) -> None:
    flujo, disponibilidad = crear_flujo(tmp_path)
    sesion = SesionLlamada(identificador_llamada="llamada-4")
    for mensaje in (
        "Quiero reservar",
        "10 de agosto de 2027",
        "12 de agosto de 2027",
        "suite",
        "2",
        "sí",
        "Luis Hernández Soto",
        "5512345678",
    ):
        flujo.procesar(sesion, mensaje)
    respuesta = flujo.procesar(sesion, "no")[1]
    assert "no enviaré sus datos" in respuesta
    assert (
        disponibilidad.conexion.execute("SELECT count(*) FROM solicitudes_reservacion").fetchone()[
            0
        ]
        == 0
    )
