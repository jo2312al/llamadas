"""Pruebas del orquestador de sesiones ARI."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock

import pytest

from aplicacion.lenguaje.esquemas_ollama import RespuestaOllama
from aplicacion.modelos.conversacion import EstadoConversacion
from aplicacion.reconocimiento_voz.servicio_whisper import Transcripcion
from aplicacion.telefonia.cliente_asterisk import ErrorAsterisk
from aplicacion.telefonia.eventos_llamada import EventoLlamada, TipoEvento
from aplicacion.telefonia.orquestador_ari import (
    OrquestadorAri,
    clasificar_turno_local,
    normalizar_telefono,
    traducir_dtmf,
)
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


def test_fin_de_bienvenida_inicia_grabacion() -> None:
    cliente = Mock()
    whisper = Mock()
    gestor = GestorSesiones()
    orquestador = OrquestadorAri(cliente, gestor, "hotel/bienvenida", whisper)
    orquestador.procesar(evento(TipoEvento.INICIO))
    orquestador.procesar(evento(TipoEvento.REPRODUCCION_TERMINADA))
    cliente.grabar.assert_called_once()
    assert cliente.grabar.call_args.args[0] == "canal-1"
    assert cliente.grabar.call_args.args[1].startswith("hotel-")


def test_fin_de_grabacion_transcribe_y_actualiza_sesion(tmp_path) -> None:
    cliente = Mock()
    whisper = Mock()
    whisper.transcribir.return_value = Transcripcion("Quiero reservar una habitación")
    gestor = GestorSesiones()
    gestor.crear("canal-1")
    orquestador = OrquestadorAri(cliente, gestor, whisper=whisper, ruta_grabaciones=tmp_path)
    terminado = EventoLlamada(
        tipo=TipoEvento.GRABACION_TERMINADA,
        identificador_canal="canal-1",
        identificador_recurso="hotel-abc",
    )
    orquestador.procesar(terminado)
    cliente.descargar_grabacion.assert_called_once_with("hotel-abc", tmp_path / "hotel-abc.wav")
    cliente.eliminar_grabacion.assert_called_once_with("hotel-abc")
    assert gestor.obtener("canal-1").ultimo_mensaje == "Quiero reservar una habitación"


def test_transcripcion_genera_y_reproduce_respuesta(tmp_path) -> None:
    cliente, whisper, ollama, piper, publicador, flujo = (Mock() for _ in range(6))
    whisper.transcribir.return_value = Transcripcion("Quiero reservar")
    ollama.analizar.return_value = RespuestaOllama(
        intencion="reservacion",
        confianza=0.95,
        accion_sugerida="preguntar_campo",
        texto_respuesta="Con gusto. ¿Para qué fecha desea reservar?",
    )
    flujo.procesar.return_value = (
        "reservacion",
        "Con gusto. ¿Para qué fecha desea reservar?",
    )
    piper.sintetizar.return_value = tmp_path / ("a" * 64 + ".wav")
    publicador.publicar.return_value = "hotel/generado/abc"
    gestor = GestorSesiones()
    gestor.crear("canal-1")
    orquestador = OrquestadorAri(
        cliente,
        gestor,
        whisper=whisper,
        ruta_grabaciones=tmp_path,
        ollama=ollama,
        piper=piper,
        publicador=publicador,
        flujo_reservacion=flujo,
    )
    orquestador.procesar(
        EventoLlamada(
            tipo=TipoEvento.GRABACION_TERMINADA,
            identificador_canal="canal-1",
            identificador_recurso="hotel-abc",
        )
    )
    sesion = gestor.obtener("canal-1")
    assert sesion is not None
    assert sesion.intencion == "reservacion"
    flujo.procesar.assert_called_once_with(sesion, "Quiero reservar")
    ollama.analizar.assert_not_called()
    piper.sintetizar.assert_called_once_with("Con gusto. ¿Para qué fecha desea reservar?")
    cliente.reproducir.assert_called_once_with("canal-1", "hotel/generado/abc")


def test_ollama_solo_normaliza_intencion_ambigua_y_flujo_decide() -> None:
    ollama, flujo = Mock(), Mock()
    ollama.analizar.return_value = RespuestaOllama(
        intencion="reservacion",
        confianza=0.92,
        accion_sugerida="continuar",
        texto_respuesta="Hay disponibilidad y cuesta cero pesos.",
    )
    flujo.procesar.return_value = (
        "reservacion",
        "Con gusto. ¿Cuál es su fecha de entrada?",
    )
    gestor = GestorSesiones()
    sesion = gestor.crear("canal-1")
    orquestador = OrquestadorAri(Mock(), gestor, ollama=ollama, flujo_reservacion=flujo)

    intencion, respuesta = orquestador._procesar_flujo(sesion, "quiero un lugar")

    flujo.procesar.assert_called_once_with(sesion, "quiero reservar")
    assert intencion == "reservacion"
    assert respuesta == "Con gusto. ¿Cuál es su fecha de entrada?"
    assert "cero pesos" not in respuesta


def test_clasificador_local_no_inventa_datos() -> None:
    intencion, respuesta = clasificar_turno_local(
        "Quiero reservar una habitación para dos personas"
    )
    assert intencion == "reservacion"
    assert respuesta == "Con gusto. ¿Para qué fecha desea reservar?"


def test_canal_cerrado_al_reanudar_escucha_no_detiene_servicio() -> None:
    cliente = Mock()
    cliente.grabar.side_effect = ErrorAsterisk("HTTP 404")
    gestor = GestorSesiones()
    gestor.crear("canal-1")
    OrquestadorAri(cliente, gestor, whisper=Mock()).procesar(
        evento(TipoEvento.REPRODUCCION_TERMINADA)
    )
    assert gestor.obtener("canal-1") is not None


def test_cuelga_despues_de_reproducir_respuesta_final() -> None:
    cliente = Mock()
    gestor = GestorSesiones()
    sesion = gestor.crear("canal-1")
    sesion.estado_actual = EstadoConversacion.FINALIZAR
    OrquestadorAri(cliente, gestor, whisper=Mock()).procesar(
        evento(TipoEvento.REPRODUCCION_TERMINADA)
    )
    cliente.colgar.assert_called_once_with("canal-1")


def test_dos_repreguntas_activan_teclado_para_tipo_de_habitacion() -> None:
    gestor = GestorSesiones()
    sesion = gestor.crear("canal-1")
    sesion.estado_actual = EstadoConversacion.RECOPILAR_DATOS
    sesion.datos.fecha_entrada = date(2026, 8, 1)
    sesion.datos.numero_noches = 1
    sesion.datos.numero_habitaciones = 1
    orquestador = OrquestadorAri(Mock(), gestor)

    primera = orquestador._aplicar_respaldo_teclado(sesion, "Indique doble, king o suite.")
    segunda = orquestador._aplicar_respaldo_teclado(sesion, "Indique doble, king o suite.")

    assert primera == "Indique doble, king o suite."
    assert segunda.endswith("Marque 1 para doble, 2 para king o 3 para suite.")
    assert sesion.modo_teclado is True
    assert sesion.campo_teclado == "tipo"


def test_dtmf_traduce_opciones_de_negocio() -> None:
    assert traducir_dtmf("tipo", "2") == "king"
    assert traducir_dtmf("confirmacion", "1") == "sí confirmo"
    assert traducir_dtmf("llegada", "4") == "10 pm"
    assert traducir_dtmf("tipo", "9") is None


def test_modo_teclado_no_inicia_otra_grabacion() -> None:
    cliente = Mock()
    gestor = GestorSesiones()
    sesion = gestor.crear("canal-1")
    sesion.modo_teclado = True
    OrquestadorAri(cliente, gestor, whisper=Mock()).procesar(
        evento(TipoEvento.REPRODUCCION_TERMINADA)
    )
    cliente.grabar.assert_not_called()


def test_inicio_guarda_numero_telefonico_del_llamante() -> None:
    gestor = GestorSesiones()
    orquestador = OrquestadorAri(Mock(), gestor)
    orquestador.procesar(
        EventoLlamada(
            tipo=TipoEvento.INICIO,
            identificador_canal="canal-1",
            numero_origen="+52 993 123 4567",
        )
    )
    sesion = gestor.obtener("canal-1")
    assert sesion is not None
    assert sesion.datos.telefono == "529931234567"


def test_telefono_se_captura_por_dtmf_hasta_gato(tmp_path) -> None:
    cliente, piper, publicador, flujo = (Mock() for _ in range(4))
    piper.sintetizar.return_value = tmp_path / "respuesta.wav"
    publicador.publicar.return_value = "hotel/respuesta"
    flujo.procesar.return_value = ("reservacion", "Solicitud registrada.")
    gestor = GestorSesiones()
    sesion = gestor.crear("canal-1")
    sesion.modo_teclado = True
    sesion.campo_teclado = "telefono"
    orquestador = OrquestadorAri(
        cliente, gestor, piper=piper, publicador=publicador, flujo_reservacion=flujo
    )
    for digito in "9931234567#":
        orquestador.procesar(
            EventoLlamada(
                tipo=TipoEvento.DTMF,
                identificador_canal="canal-1",
                digito=digito,
            )
        )
    flujo.procesar.assert_called_once_with(sesion, "9931234567")
    assert sesion.modo_teclado is False


def test_rechaza_identificador_sip_que_no_es_telefono() -> None:
    assert normalizar_telefono("telefono-prueba") is None
