"""Pruebas del orquestador de sesiones ARI."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from aplicacion.telefonia.cliente_asterisk import ErrorAsterisk
from aplicacion.telefonia.eventos_llamada import EventoLlamada, TipoEvento
from aplicacion.telefonia.orquestador_ari import OrquestadorAri
from aplicacion.telefonia.sesion_llamada import GestorSesiones


def evento(tipo: TipoEvento, canal: str = "canal-1") -> EventoLlamada:
    """Crea un evento mínimo para pruebas."""
    return EventoLlamada(tipo=tipo, identificador_canal=canal)


def test_inicio_contesta_una_sola_vez_y_fin_retira() -> None:
    cliente = Mock()
    gestor = GestorSesiones()
    orquestador = OrquestadorAri(cliente, gestor)
    orquestador.procesar(evento(TipoEvento.INICIO))
    orquestador.procesar(evento(TipoEvento.INICIO))
    cliente.responder.assert_called_once_with("canal-1")
    assert gestor.obtener("canal-1") is not None
    orquestador.procesar(evento(TipoEvento.FIN))
    assert gestor.obtener("canal-1") is None


def test_inicio_reproduce_bienvenida_configurada() -> None:
    cliente = Mock()
    orquestador = OrquestadorAri(cliente, GestorSesiones(), "hotel/bienvenida")
    orquestador.procesar(evento(TipoEvento.INICIO))
    cliente.responder.assert_called_once_with("canal-1")
    cliente.reproducir.assert_called_once_with("canal-1", "hotel/bienvenida")


def test_error_al_responder_no_deja_sesion_huerfana() -> None:
    cliente = Mock()
    cliente.responder.side_effect = ErrorAsterisk("fallo")
    gestor = GestorSesiones()
    with pytest.raises(ErrorAsterisk):
        OrquestadorAri(cliente, gestor).procesar(evento(TipoEvento.INICIO))
    assert gestor.obtener("canal-1") is None


def test_finaliza_llamada_vencida() -> None:
    cliente = Mock()
    gestor = GestorSesiones(duracion_maxima_segundos=30)
    sesion = gestor.crear("canal-1")
    sesion.fecha_inicio = datetime.now(UTC) - timedelta(seconds=31)
    cantidad = OrquestadorAri(cliente, gestor).finalizar_vencidas()
    assert cantidad == 1
    cliente.colgar.assert_called_once_with("canal-1")
    assert gestor.obtener("canal-1") is None
