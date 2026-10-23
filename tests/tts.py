"""Voz sintética con espeak-ng (para ejemplos y tests de integración)."""

import shutil
import subprocess
from pathlib import Path

import numpy as np

from tests import sintetico as s

VOCES = {"es": "es-419", "en": "en-us"}


def disponible() -> bool:
    return shutil.which("espeak-ng") is not None


def sintetizar(texto: str, idioma: str, ruta: Path, velocidad: int = 155) -> Path:
    """Admite SSML (p. ej. <break time="1000ms"/>). Guarda un wav a 16 kHz mono."""
    crudo = ruta.with_suffix(".espeak.wav")
    subprocess.run(
        ["espeak-ng", "-m", "-v", VOCES[idioma], "-s", str(velocidad), "-w", str(crudo), texto],
        check=True,
    )
    from voice_coach_mcp.audio.io import cargar

    y = cargar(crudo)
    crudo.unlink()
    return s.guardar(ruta, np.concatenate([s.silencio(0.3), y, s.silencio(0.3)]))


# Piper (voz neural): el modelo de fonemas entiende mal la voz de formantes de espeak-ng.
# Se usa la voz LJSpeech (dataset de dominio público) y piper se ejecuta con uvx, sin
# agregarlo a las dependencias del proyecto.
VOZ_PIPER = "en_US-ljspeech-medium"
URL_PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ljspeech/medium/"
CACHE_PIPER = Path.home() / ".cache" / "voice-coach-tests" / "piper"


def piper_disponible() -> bool:
    return shutil.which("uvx") is not None


def _voz_piper() -> Path:
    import urllib.request

    CACHE_PIPER.mkdir(parents=True, exist_ok=True)
    for sufijo in (".onnx", ".onnx.json"):
        destino = CACHE_PIPER / f"{VOZ_PIPER}{sufijo}"
        if not destino.exists():
            urllib.request.urlretrieve(f"{URL_PIPER}{VOZ_PIPER}{sufijo}", destino)
    return CACHE_PIPER / f"{VOZ_PIPER}.onnx"


def sintetizar_piper(texto: str, ruta: Path) -> Path:
    crudo = ruta.with_suffix(".piper.wav")
    subprocess.run(
        [
            "uvx",
            "--quiet",
            "--from",
            "piper-tts",
            "piper",
            "-m",
            str(_voz_piper()),
            "-f",
            str(crudo),
        ],
        input=texto.encode(),
        check=True,
        capture_output=True,
    )
    from voice_coach_mcp.audio.io import cargar

    y = cargar(crudo)
    crudo.unlink()
    return s.guardar(ruta, np.concatenate([s.silencio(0.3), y, s.silencio(0.3)]))
