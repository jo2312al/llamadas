"""Pruebas del índice local de lenguaje del hotel."""

from time import perf_counter

from aplicacion.conversacion.indice_lenguaje import (
    buscar_respuesta_frecuente,
    buscar_tipo_habitacion,
    es_afirmacion,
    es_negacion,
    es_solicitud_reservacion,
)


def test_indice_reconoce_variantes_de_reservacion_y_habitacion() -> None:
    assert es_solicitud_reservacion("quisiera apartar un cuarto")
    assert es_solicitud_reservacion("necesito alojamiento")
    assert buscar_tipo_habitacion("quiero la matrimonial") == "doble"
    assert buscar_tipo_habitacion("la cama grande") == "king"
    assert buscar_tipo_habitacion("una suit") == "suite"


def test_indice_reconoce_confirmaciones_y_preguntas_frecuentes() -> None:
    assert es_afirmacion("sí, está bien")
    assert es_negacion("no gracias")
    assert "sin costo" in buscar_respuesta_frecuente("¿tienen parking para mi auto?")
    assert "no está incluido" in buscar_respuesta_frecuente("incluye desayuno")
    assert "Andrés Sánchez" in buscar_respuesta_frecuente("¿dónde están ubicados?")


def test_indice_responde_en_microsegundos_sin_red() -> None:
    inicio = perf_counter()
    for _ in range(10_000):
        assert es_solicitud_reservacion("quiero hacer una reservación")
    assert perf_counter() - inicio < 0.25
