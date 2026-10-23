"""Carga y guardado de audio, normalizado a 16 kHz mono float32."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from ..config import SAMPLE_RATE, Config
from ..errores import ErrorUsuario


def resolver_ruta(audio: str, config: Config) -> Path:
    """Acepta rutas absolutas, relativas o el nombre de una grabación en el dir de grabaciones."""
    ruta = Path(audio).expanduser()
    if ruta.is_file():
        return ruta.resolve()
    for candidata in (config.dir_grabaciones / audio, config.dir_grabaciones / f"{audio}.wav"):
        if candidata.is_file():
            return candidata.resolve()
    raise ErrorUsuario(f"No encuentro el archivo de audio: {audio}")


def cargar(ruta: Path, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Lee wav/flac/ogg/mp3 con libsndfile; otros formatos (m4a, aac…) vía ffmpeg."""
    try:
        y, sr_orig = sf.read(ruta, dtype="float32", always_2d=True)
        y = y.mean(axis=1)
    except sf.LibsndfileError:
        return _cargar_ffmpeg(ruta, sr)
    if sr_orig != sr:
        import librosa

        y = librosa.resample(y, orig_sr=sr_orig, target_sr=sr)
    return np.ascontiguousarray(y, dtype=np.float32)


def _cargar_ffmpeg(ruta: Path, sr: int) -> np.ndarray:
    if shutil.which("ffmpeg") is None:
        raise ErrorUsuario(
            f"No puedo leer {ruta.name}: formato no soportado sin ffmpeg (brew install ffmpeg)."
        )
    proceso = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(ruta),
            "-ac",
            "1",
            "-ar",
            str(sr),
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if proceso.returncode != 0:
        raise ErrorUsuario(f"ffmpeg no pudo leer {ruta.name}: {proceso.stderr.decode()[:200]}")
    return np.frombuffer(proceso.stdout, dtype=np.float32).copy()


def guardar_wav(ruta: Path, y: np.ndarray, sr: int = SAMPLE_RATE) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    sf.write(ruta, np.clip(y, -1.0, 1.0), sr, subtype="PCM_16")
