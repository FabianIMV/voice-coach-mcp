"""Grabación desde el micrófono con sounddevice (PortAudio).

En macOS, si la app que lanza el servidor (Claude o la terminal) no tiene permiso de micrófono,
CoreAudio suele entregar silencio digital en vez de fallar; por eso se revisan ambos casos.
"""

import re
from datetime import datetime
from pathlib import Path

import numpy as np

from ..config import SAMPLE_RATE, Config
from ..errores import ErrorUsuario
from . import calidad as cal
from .io import guardar_wav

AYUDA_PERMISO = (
    "macOS no está entregando audio del micrófono. Revisa Ajustes del Sistema → Privacidad y "
    "seguridad → Micrófono y habilita la app que ejecuta el servidor (Claude, o la terminal "
    "donde corre Claude Code); luego reinicia esa app."
)


def _sounddevice():
    try:
        import sounddevice as sd
    except OSError as e:  # PortAudio no instalado (Linux sin libportaudio2)
        raise ErrorUsuario(f"No se pudo cargar PortAudio para grabar: {e}") from e
    return sd


def nombre_archivo(nombre: str | None, carpeta: Path) -> Path:
    base = nombre or datetime.now().strftime("grabacion-%Y%m%d-%H%M%S")
    base = re.sub(r"\.wav$", "", base, flags=re.IGNORECASE)
    base = re.sub(r"[^\w\-]+", "_", base, flags=re.UNICODE).strip("_") or "grabacion"
    ruta = carpeta / f"{base}.wav"
    n = 2
    while ruta.exists():
        ruta = carpeta / f"{base}-{n}.wav"
        n += 1
    return ruta


def grabar(segundos: float, nombre: str | None, config: Config) -> dict:
    if not 0 < segundos <= config.max_segundos_grabacion:
        raise ErrorUsuario(
            f"segundos debe estar entre 0 y {config.max_segundos_grabacion:g} "
            "(ajustable con VOICE_COACH_MAX_SEGUNDOS)."
        )
    sd = _sounddevice()
    try:
        dispositivo = sd.query_devices(kind="input")
        sr_disp = int(dispositivo["default_samplerate"])
        datos = sd.rec(int(segundos * sr_disp), samplerate=sr_disp, channels=1, dtype="float32")
        sd.wait()
    except (sd.PortAudioError, ValueError) as e:
        raise ErrorUsuario(
            f"No se pudo abrir el micrófono ({e}). Si estás en macOS: {AYUDA_PERMISO}"
        ) from e

    y = np.asarray(datos, dtype=np.float32).reshape(-1)
    if sr_disp != SAMPLE_RATE:
        import librosa

        y = librosa.resample(y, orig_sr=sr_disp, target_sr=SAMPLE_RATE)

    ruta = nombre_archivo(nombre, config.dir_grabaciones)
    guardar_wav(ruta, y)

    calidad = cal.evaluar(y, duracion_minima=min(1.0, segundos))
    advertencias = calidad.advertencias
    if any(a["codigo"] == "silencio_digital" for a in advertencias):
        advertencias.insert(0, cal.advertencia("sin_permiso_microfono", AYUDA_PERMISO))
    return {
        "audio": str(ruta),
        "duracion_s": calidad.duracion_s,
        "sample_rate": SAMPLE_RATE,
        "dispositivo": dispositivo.get("name"),
        "niveles": calidad.niveles(),
        "confianza": cal.nivel_confianza(calidad.factor),
        "advertencias": advertencias,
    }
