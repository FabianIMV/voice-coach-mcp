"""sounddevice stand-in to test recording without a microphone."""

import sys
import types

import numpy as np


class PortAudioError(Exception):
    pass


def install(monkeypatch, *, mode: str = "tone", samplerate: int = 48_000):
    """mode: "tone" (records an A4), "silence" (permission denied on macOS) or "error"."""
    calls: dict = {}

    def query_devices(kind=None):
        if mode == "error":
            raise PortAudioError("Error querying device -1")
        return {"name": "Fake microphone", "default_samplerate": float(samplerate)}

    def rec(frames, samplerate, channels, dtype):
        calls.update(frames=frames, samplerate=samplerate, channels=channels)
        if mode == "silence":
            return np.zeros((frames, channels), dtype=dtype)
        t = np.arange(frames) / samplerate
        y = 0.3 * np.sin(2 * np.pi * 440 * t)
        y[: samplerate // 2] = 0  # leading silence so the SNR can be estimated
        return y.reshape(-1, 1).astype(dtype)

    module = types.SimpleNamespace(
        PortAudioError=PortAudioError, query_devices=query_devices, rec=rec, wait=lambda: None
    )
    monkeypatch.setitem(sys.modules, "sounddevice", module)
    return calls
