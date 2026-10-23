"""Microphone recording with sounddevice (PortAudio).

On macOS, when the app that launches the server (Claude or the terminal) has no microphone
permission, CoreAudio usually delivers digital silence instead of failing, so both cases are
checked.
"""

import re
from datetime import datetime
from pathlib import Path

import numpy as np

from ..config import SAMPLE_RATE, Config
from ..errors import UserError
from . import quality as q
from .io import save_wav

PERMISSION_HELP = (
    "macOS is not delivering microphone audio. Open System Settings → Privacy & Security → "
    "Microphone and enable the app running the server (Claude, or the terminal where Claude "
    "Code runs); then restart that app."
)


def _sounddevice():
    try:
        import sounddevice as sd
    except OSError as e:  # PortAudio missing (Linux without libportaudio2)
        raise UserError(f"Could not load PortAudio to record: {e}") from e
    return sd


def file_name(name: str | None, folder: Path) -> Path:
    base = name or datetime.now().strftime("recording-%Y%m%d-%H%M%S")
    base = re.sub(r"\.wav$", "", base, flags=re.IGNORECASE)
    base = re.sub(r"[^\w\-]+", "_", base, flags=re.UNICODE).strip("_") or "recording"
    path = folder / f"{base}.wav"
    n = 2
    while path.exists():
        path = folder / f"{base}-{n}.wav"
        n += 1
    return path


def record(seconds: float, name: str | None, config: Config) -> dict:
    if not 0 < seconds <= config.max_recording_seconds:
        raise UserError(
            f"seconds must be between 0 and {config.max_recording_seconds:g} "
            "(configurable with VOICE_COACH_MAX_SECONDS)."
        )
    sd = _sounddevice()
    try:
        device = sd.query_devices(kind="input")
        device_sr = int(device["default_samplerate"])
        data = sd.rec(int(seconds * device_sr), samplerate=device_sr, channels=1, dtype="float32")
        sd.wait()
    except (sd.PortAudioError, ValueError) as e:
        raise UserError(f"Could not open the microphone ({e}). On macOS: {PERMISSION_HELP}") from e

    y = np.asarray(data, dtype=np.float32).reshape(-1)
    if device_sr != SAMPLE_RATE:
        import librosa

        y = librosa.resample(y, orig_sr=device_sr, target_sr=SAMPLE_RATE)

    path = file_name(name, config.recordings_dir)
    save_wav(path, y)

    quality = q.assess(y, min_duration=min(1.0, seconds))
    warnings = quality.warnings
    if any(w["code"] == "digital_silence" for w in warnings):
        warnings.insert(0, q.warning("no_microphone_permission", PERMISSION_HELP))
    return {
        "audio": str(path),
        "duration_s": quality.duration_s,
        "sample_rate": SAMPLE_RATE,
        "device": device.get("name"),
        "levels": quality.levels(),
        "confidence": q.confidence(quality.factor),
        "warnings": warnings,
    }
