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
