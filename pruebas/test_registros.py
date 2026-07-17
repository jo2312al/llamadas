"""Pruebas de inicialización de registros."""

import logging
from unittest.mock import patch

from aplicacion.principal import configurar_registros


def test_configura_logging_informativo() -> None:
    with patch("logging.basicConfig") as configurar:
        configurar_registros()
    configurar.assert_called_once()
    assert configurar.call_args.kwargs["level"] == logging.INFO
    assert "%(name)s" in configurar.call_args.kwargs["format"]
