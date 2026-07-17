"""Pruebas del procesamiento local de audio."""

import json
import struct
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from aplicacion.audio.convertidor_audio import guardar_pcm_como_wav
from aplicacion.audio.detector_voz import ConfiguracionVoz, DetectorVoz, calcular_rms
from aplicacion.reconocimiento_voz.servicio_whisper import ErrorWhisper, ServicioWhisper
from aplicacion.sintesis_voz.cache_audio import CacheAudio
from aplicacion.sintesis_voz.servicio_piper import ServicioPiper


def muestras(valor: int, cantidad: int = 160) -> bytes:
    """Crea un cuadro PCM uniforme para pruebas."""
    return struct.pack(f"<{cantidad}h", *([valor] * cantidad))


def test_detector_inicio_y_fin() -> None:
    detector = DetectorVoz(
        ConfiguracionVoz(umbral_rms=400, cuadros_inicio=2, cuadros_silencio_fin=2)
    )
    assert detector.procesar(muestras(1_000)) is None
    assert detector.procesar(muestras(1_000)) == "inicio"
    assert detector.procesar(muestras(0)) is None
    assert detector.procesar(muestras(0)) == "fin"


def test_rms_y_pcm_invalido() -> None:
    assert calcular_rms(muestras(1_000)) == 1_000
    with pytest.raises(ValueError):
        calcular_rms(b"\x00")


def test_crea_wav_valido(tmp_path: Path) -> None:
    ruta = guardar_pcm_como_wav(muestras(500), tmp_path / "audio.wav")
    with wave.open(str(ruta), "rb") as archivo:
        assert archivo.getframerate() == 16_000
        assert archivo.getnchannels() == 1
        assert archivo.getsampwidth() == 2


def test_whisper_lee_json(tmp_path: Path) -> None:
    binario, modelo, audio = [
        tmp_path / nombre for nombre in ("whisper", "modelo.bin", "audio.wav")
    ]
    for ruta in (binario, modelo, audio):
        ruta.touch()

    def simular(comando: list[str], **_: object) -> None:
        salida = Path(comando[comando.index("-of") + 1]).with_suffix(".json")
        salida.write_text(json.dumps({"transcription": [{"text": " hola"}]}), encoding="utf-8")

    with patch("subprocess.run", side_effect=simular):
        resultado = ServicioWhisper(binario, modelo).transcribir(audio)
    assert resultado.texto == "hola"


def test_whisper_rechaza_archivos_ausentes(tmp_path: Path) -> None:
    with pytest.raises(ErrorWhisper):
        ServicioWhisper(tmp_path / "no", tmp_path / "modelo").transcribir(tmp_path / "audio")


def test_piper_genera_y_reutiliza_cache(tmp_path: Path) -> None:
    binario, modelo = tmp_path / "piper", tmp_path / "voz.onnx"
    binario.touch()
    modelo.touch()
    servicio = ServicioPiper(binario, modelo, CacheAudio(tmp_path / "cache"))

    def simular(comando: list[str], **_: object) -> None:
        destino = Path(comando[comando.index("--output_file") + 1])
        destino.write_bytes(b"R" * 45)

    with patch("subprocess.run", side_effect=simular) as proceso:
        primera = servicio.sintetizar("Buenos días")
        segunda = servicio.sintetizar("  buenos   DÍAS ")
    assert primera == segunda
    assert proceso.call_count == 1
