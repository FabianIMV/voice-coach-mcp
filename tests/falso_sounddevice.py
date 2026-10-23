"""Sustituto de sounddevice para probar la grabación sin micrófono."""

import sys
import types

import numpy as np

from tests import sintetico as s


class PortAudioError(Exception):
    pass


def instalar(monkeypatch, *, modo: str = "tono", samplerate: int = 48_000):
    """modo: "tono" (graba un A4), "silencio" (permiso denegado en macOS) o "error"."""
    llamadas: dict = {}

    def query_devices(kind=None):
        if modo == "error":
            raise PortAudioError("Error querying device -1")
        return {"name": "Micrófono falso", "default_samplerate": float(samplerate)}

    def rec(frames, samplerate, channels, dtype):
        llamadas.update(frames=frames, samplerate=samplerate, channels=channels)
        if modo == "silencio":
            return np.zeros((frames, channels), dtype=dtype)
        t = np.arange(frames) / samplerate
        y = 0.3 * np.sin(2 * np.pi * 440 * t)
        y[: samplerate // 2] = 0  # silencio inicial para que el SNR sea estimable
        return y.reshape(-1, 1).astype(dtype)

    modulo = types.SimpleNamespace(
        PortAudioError=PortAudioError, query_devices=query_devices, rec=rec, wait=lambda: None
    )
    monkeypatch.setitem(sys.modules, "sounddevice", modulo)
    return llamadas


__all__ = ["instalar", "s"]
