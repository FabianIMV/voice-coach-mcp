"""Synthetic speech for examples and integration tests."""

import shutil
import subprocess
from pathlib import Path

import numpy as np

from tests import synthetic as s

VOICES = {"es": "es-419", "en": "en-us"}


def espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None


def espeak(text: str, language: str, path: Path, speed: int = 155) -> Path:
    """espeak-ng voice. Accepts SSML (e.g. <break time="1000ms"/>). Saves a 16 kHz mono wav."""
    raw = path.with_suffix(".espeak.wav")
    subprocess.run(
        ["espeak-ng", "-m", "-v", VOICES[language], "-s", str(speed), "-w", str(raw), text],
        check=True,
    )
    return _finish(raw, path)


# Piper (neural voice): the phoneme model understands espeak-ng's formant voice poorly. The
# LJSpeech voice (public-domain dataset) is used and piper runs through uvx, without adding
# it to the project dependencies.
PIPER_VOICE = "en_US-ljspeech-medium"
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ljspeech/medium/"
PIPER_CACHE = Path.home() / ".cache" / "voice-coach-tests" / "piper"


def piper_available() -> bool:
    return shutil.which("uvx") is not None


def _piper_voice() -> Path:
    import urllib.request

    PIPER_CACHE.mkdir(parents=True, exist_ok=True)
    for suffix in (".onnx", ".onnx.json"):
        destination = PIPER_CACHE / f"{PIPER_VOICE}{suffix}"
        if not destination.exists():
            urllib.request.urlretrieve(f"{PIPER_URL}{PIPER_VOICE}{suffix}", destination)
    return PIPER_CACHE / f"{PIPER_VOICE}.onnx"


def piper(text: str, path: Path) -> Path:
    raw = path.with_suffix(".piper.wav")
    subprocess.run(
        [
            "uvx",
            "--quiet",
            "--from",
            "piper-tts",
            "piper",
            "-m",
            str(_piper_voice()),
            "-f",
            str(raw),
        ],
        input=text.encode(),
        check=True,
        capture_output=True,
    )
    return _finish(raw, path)


def _finish(raw: Path, path: Path) -> Path:
    from voice_coach_mcp.audio.io import load

    y = load(raw)
    raw.unlink()
    return s.save(path, np.concatenate([s.silence(0.3), y, s.silence(0.3)]))
