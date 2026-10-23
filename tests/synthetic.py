"""Synthetic audio and MIDI generators with known pitches and timings."""

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 16_000


def midi_hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def tone(
    midi: float,
    dur: float,
    *,
    vibrato_cents: float = 0.0,
    vibrato_hz: float = 5.5,
    jitter_cents: float = 0.0,
    amplitude: float = 0.4,
    seed: int = 0,
) -> np.ndarray:
    """Tone with 3 harmonics (simple vocal timbre), optional sinusoidal vibrato or slow jitter."""
    n = int(round(dur * SR))
    t = np.arange(n) / SR
    cents = vibrato_cents * np.sin(2 * np.pi * vibrato_hz * t)
    if jitter_cents:
        rng = np.random.default_rng(seed)
        noise = rng.standard_normal(n // 160 + 2)
        # smooth walk (~2 Hz) interpolated to the sample rate
        smooth = np.convolve(noise, np.hanning(25), mode="same")
        smooth = smooth / (np.std(smooth) + 1e-12) * jitter_cents
        cents = cents + np.interp(np.arange(n), np.arange(len(smooth)) * 160, smooth)
    f = midi_hz(midi) * 2 ** (cents / 1200)
    phase = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase)
    ramp = min(n // 2, int(0.01 * SR))
    env = np.ones(n)
    env[:ramp] = np.linspace(0, 1, ramp)
    env[n - ramp :] = np.linspace(1, 0, ramp)
    return (amplitude / 1.75 * y * env).astype(np.float32)


def silence(dur: float) -> np.ndarray:
    return np.zeros(int(round(dur * SR)), dtype=np.float32)


def padded(y: np.ndarray, margin: float = 0.3) -> np.ndarray:
    return np.concatenate([silence(margin), y, silence(margin)])


def sequence(notes: list[tuple[float, float]], gap: float = 0.1, start: float = 0.3) -> np.ndarray:
    """notes = [(fractional_midi, duration)], separated by short gaps."""
    parts = [silence(start)]
    for midi, dur in notes:
        parts += [tone(midi, dur), silence(gap)]
    parts.append(silence(0.3))
    return np.concatenate(parts)


def with_noise(y: np.ndarray, snr_db: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    power = np.mean(y[np.abs(y) > 0] ** 2)
    noise = rng.standard_normal(len(y)) * np.sqrt(power / 10 ** (snr_db / 10))
    return (y + noise).astype(np.float32)


def save(path: Path, y: np.ndarray) -> Path:
    sf.write(path, y, SR, subtype="PCM_16")
    return path


def melody_midi(
    path: Path, notes: list[tuple[int, float, float]], accompaniment: bool = False
) -> Path:
    """notes = [(midi, start_s, end_s)]. With accompaniment, adds an overlapping low voice."""
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    voice = pretty_midi.Instrument(program=52, name="Melody")
    for pitch, start, end in notes:
        voice.notes.append(pretty_midi.Note(velocity=90, pitch=pitch, start=start, end=end))
    if accompaniment:
        for _pitch, start, end in notes:
            voice.notes.append(pretty_midi.Note(velocity=60, pitch=48, start=start, end=end))
    pm.instruments.append(voice)
    pm.write(str(path))
    return path
