"""Configuración leída de variables de entorno en cada llamada (así los tests pueden cambiarlas)."""

import os
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class Config:
    dir_base: Path
    max_segundos_grabacion: float
    a4_hz: float
    max_bytes_respuesta: int
    whisper_modelo: str
    whisper_dispositivo: str
    whisper_tipo_computo: str
    pronunciacion_backend: str
    muletillas: Path | None

    @property
    def dir_grabaciones(self) -> Path:
        return self.dir_base / "grabaciones"

    @property
    def dir_analisis(self) -> Path:
        return self.dir_base / "analisis"


def _float(nombre: str, defecto: float) -> float:
    valor = os.environ.get(nombre)
    return float(valor) if valor else defecto


def cargar_config() -> Config:
    muletillas = os.environ.get("VOICE_COACH_MULETILLAS")
    return Config(
        dir_base=Path(os.environ.get("VOICE_COACH_DIR", "~/VoiceCoach")).expanduser(),
        max_segundos_grabacion=_float("VOICE_COACH_MAX_SEGUNDOS", 120.0),
        a4_hz=_float("VOICE_COACH_A4_HZ", 440.0),
        max_bytes_respuesta=int(_float("VOICE_COACH_MAX_BYTES", 2048)),
        whisper_modelo=os.environ.get("VOICE_COACH_WHISPER_MODEL", "small"),
        whisper_dispositivo=os.environ.get("VOICE_COACH_WHISPER_DEVICE", "cpu"),
        whisper_tipo_computo=os.environ.get("VOICE_COACH_WHISPER_COMPUTE_TYPE", "int8"),
        pronunciacion_backend=os.environ.get("VOICE_COACH_PRONUNCIACION_BACKEND", "local"),
        muletillas=Path(muletillas).expanduser() if muletillas else None,
    )
