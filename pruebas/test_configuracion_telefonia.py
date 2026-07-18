"""Pruebas estáticas de la troncal SIP sin credenciales reales."""

from pathlib import Path


def test_plantilla_sip_restringe_codec_contexto_y_media() -> None:
    contenido = Path("asterisk/pjsip_troncal.conf.plantilla").read_text(encoding="utf-8")
    assert "context=entrante-hotel" in contenido
    assert "allow=ulaw,alaw" in contenido
    assert "direct_media=no" in contenido
    assert "rtp_symmetric=yes" in contenido
    assert "match=__SIP_CIDR__" in contenido
    assert "password=__SIP_PASSWORD__" in contenido


def test_dialplan_entrante_solo_entrega_a_stasis() -> None:
    contenido = Path("asterisk/extensions_entrante.conf.plantilla").read_text(encoding="utf-8")
    assert "[entrante-hotel]" in contenido
    assert "Stasis(agente-hotel)" in contenido
    assert "System(" not in contenido


def test_repositorio_conserva_marcadores_de_credenciales() -> None:
    plantilla = Path("asterisk/pjsip_troncal.conf.plantilla").read_text(encoding="utf-8")
    assert "__SIP_USUARIO__" in plantilla
    assert "__SIP_PASSWORD__" in plantilla


def test_diagnostico_exige_objetos_reales_y_registro_aceptado() -> None:
    contenido = Path("scripts/verificar_prellamada.sh").read_text(encoding="utf-8")
    assert "comprobar_salida" in contenido
    assert "Endpoint:[[:space:]]+proveedor-hotel/" in contenido
    assert "Registro SIP aceptado por el proveedor" in contenido
    assert "Registered" in contenido
