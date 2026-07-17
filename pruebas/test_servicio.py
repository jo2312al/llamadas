"""Pruebas del ciclo de vida supervisado."""

from pathlib import Path
from unittest.mock import patch

from aplicacion.principal import ejecutar_servicio


def test_servicio_migra_y_atiende_senal(tmp_path: Path) -> None:
    configuracion = tmp_path / "configuracion.yaml"
    configuracion.write_text(f"ruta_base_datos: {tmp_path / 'servicio.db'}\n", encoding="utf-8")
    manejadores: dict[int, object] = {}

    def guardar_manejador(senal: int, manejador: object) -> None:
        manejadores[senal] = manejador

    def terminar_en_espera(_segundos: float) -> None:
        manejador = next(iter(manejadores.values()))
        manejador(15, None)  # type: ignore[operator]

    with (
        patch("aplicacion.principal.signal.signal", side_effect=guardar_manejador),
        patch("aplicacion.principal.time.sleep", side_effect=terminar_en_espera),
        patch("aplicacion.principal.Path", wraps=Path),
    ):
        ejecutar_servicio(configuracion)
    assert (tmp_path / "servicio.db").is_file()
