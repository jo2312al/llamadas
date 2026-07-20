"""Pruebas del diálogo determinístico conectado al inventario."""

from datetime import date
from pathlib import Path

from aplicacion.base_datos.conexion import conectar, migrar
from aplicacion.conversacion.flujo_reservacion import (
    FlujoReservacion,
    calcular_precio_noche,
    extraer_fecha,
    extraer_hora,
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
    assert extraer_hora("seis de la tarde").hour == 18
    assert calcular_precio_noche("doble", 2) == 700
    assert calcular_precio_noche("doble", 3) == 800


def test_extrae_fechas_relativas_sin_ano_y_con_dia_hablado() -> None:
    referencia = date(2026, 7, 20)
    assert extraer_fecha("hoy", referencia) == date(2026, 7, 20)
    assert extraer_fecha("mañana", referencia) == date(2026, 7, 21)
    assert extraer_fecha("pasado mañana", referencia) == date(2026, 7, 22)
    assert extraer_fecha("el veinte de julio", referencia) == date(2026, 7, 20)
    assert extraer_fecha("treinta y uno de julio", referencia) == date(2026, 7, 31)
    assert extraer_fecha("15 de agosto", referencia) == date(2026, 8, 15)
    assert extraer_fecha("10/7", referencia) == date(2027, 7, 10)


def test_varias_habitaciones_ninos_y_total(tmp_path: Path) -> None:
    flujo, _ = crear_flujo(tmp_path)
    sesion = SesionLlamada(identificador_llamada="llamada-multiple")
    mensajes = (
        "Quiero reservar",
        "10 de agosto de 2027",
        "dos noches",
        "dos habitaciones",
        "doble",
        "dos adultos",
        "dos niños",
        "5 y 8",
        "suite",
        "cuatro adultos",
        "cero niños",
        "5 am",
    )
    respuesta = ""
    for mensaje in mensajes:
        respuesta = flujo.procesar(sesion, mensaje)[1]

    assert "Sí hay disponibilidad" in respuesta
    assert "3200 pesos" in respuesta
    assert "llegada anticipada" in respuesta
    assert len(sesion.datos.habitaciones) == 2
    assert sesion.datos.numero_menores == 2


def test_recopila_un_dato_por_turno_y_consulta_inventario(tmp_path: Path) -> None:
    flujo, disponibilidad = crear_flujo(tmp_path)
    disponibilidad.bloquear("doble", date(2027, 8, 10), date(2027, 8, 12))
    sesion = SesionLlamada(identificador_llamada="llamada-1")

    assert "fecha" in flujo.procesar(sesion, "Quiero reservar")[1]
    assert "noches" in flujo.procesar(sesion, "10 de agosto de 2027")[1]
    assert "habitaciones" in flujo.procesar(sesion, "dos noches")[1]
    assert "tipo" in flujo.procesar(sesion, "una habitación")[1]
    assert "adultos" in flujo.procesar(sesion, "habitación doble")[1]
    assert "niños" in flujo.procesar(sesion, "dos adultos")[1]
    assert "hora" in flujo.procesar(sesion, "cero niños")[1]
    intencion, respuesta = flujo.procesar(sesion, "6 de la tarde")

    assert intencion == "reservacion"
    assert "Sí hay disponibilidad" in respuesta
    assert "1400 pesos" in respuesta
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
    flujo.procesar(sesion, "dos noches")
    flujo.procesar(sesion, "una habitación")
    flujo.procesar(sesion, "suite")
    flujo.procesar(sesion, "2")
    flujo.procesar(sesion, "cero")
    respuesta = flujo.procesar(sesion, "6 pm")[1]
    assert respuesta == "No hay disponibilidad para toda la reservación solicitada."


def test_confirma_contacto_guarda_y_bloquea_inventario(tmp_path: Path) -> None:
    flujo, disponibilidad = crear_flujo(tmp_path)
    sesion = SesionLlamada(identificador_llamada="llamada-3")
    for mensaje in (
        "Quiero reservar",
        "10 de agosto de 2027",
        "dos noches",
        "una habitación",
        "king",
        "dos adultos",
        "cero niños",
        "6 pm",
    ):
        flujo.procesar(sesion, mensaje)

    assert "nombre" in flujo.procesar(sesion, "sí, continuar")[1]
    assert "teléfono" in flujo.procesar(sesion, "Ana Pérez López")[1]
    respuesta = flujo.procesar(sesion, "5512345678")[1]

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


def test_no_bloquea_si_cancela_antes_de_confirmar(tmp_path: Path) -> None:
    flujo, disponibilidad = crear_flujo(tmp_path)
    sesion = SesionLlamada(identificador_llamada="llamada-4")
    for mensaje in (
        "Quiero reservar",
        "10 de agosto de 2027",
        "dos noches",
        "una habitación",
        "suite",
        "2",
        "cero",
        "6 pm",
    ):
        flujo.procesar(sesion, mensaje)
    respuesta = flujo.procesar(sesion, "no")[1]
    assert "no registraré" in respuesta
    assert (
        disponibilidad.conexion.execute("SELECT count(*) FROM solicitudes_reservacion").fetchone()[
            0
        ]
        == 0
    )


def test_cambia_fechas_desde_la_confirmacion_sin_quedar_en_bucle(tmp_path: Path) -> None:
    flujo, _ = crear_flujo(tmp_path)
    sesion = SesionLlamada(identificador_llamada="llamada-cambio")
    for mensaje in (
        "Quiero reservar",
        "10 de agosto de 2027",
        "dos noches",
        "una habitación",
        "doble",
        "dos adultos",
        "cero niños",
        "6 pm",
    ):
        flujo.procesar(sesion, mensaje)

    respuesta = flujo.procesar(sesion, "sí, quiero cambiar las fechas")[1]

    assert "nueva fecha de entrada" in respuesta
    assert sesion.estado_actual == EstadoConversacion.RECOPILAR_DATOS
    assert sesion.datos.fecha_entrada is None
    assert sesion.datos.fecha_salida is None
    assert "noches" in flujo.procesar(sesion, "20 de agosto de 2027")[1]


def test_rechaza_la_opcion_y_finaliza_sin_repetir_la_pregunta(tmp_path: Path) -> None:
    flujo, disponibilidad = crear_flujo(tmp_path)
    sesion = SesionLlamada(identificador_llamada="llamada-cancelada")
    for mensaje in (
        "Quiero reservar",
        "10 de agosto de 2027",
        "dos noches",
        "una habitación",
        "suite",
        "dos adultos",
        "cero niños",
        "6 pm",
    ):
        flujo.procesar(sesion, mensaje)

    respuesta = flujo.procesar(sesion, "no, gracias")[1]

    assert "no registraré" in respuesta
    assert sesion.estado_actual == EstadoConversacion.FINALIZAR
    assert (
        disponibilidad.conexion.execute("SELECT count(*) FROM solicitudes_reservacion").fetchone()[
            0
        ]
        == 0
    )
