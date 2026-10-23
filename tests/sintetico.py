"""Generadores de audio y MIDI sintéticos con alturas y tiempos conocidos."""

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 16_000


def midi_hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def tono(
    midi: float,
    dur: float,
    *,
    vibrato_cents: float = 0.0,
    vibrato_hz: float = 5.5,
    jitter_cents: float = 0.0,
    amplitud: float = 0.4,
    semilla: int = 0,
) -> np.ndarray:
    """Tono con 3 armónicos (timbre vocal simple), vibrato sinusoidal o jitter lento opcional."""
    n = int(round(dur * SR))
    t = np.arange(n) / SR
    cents = vibrato_cents * np.sin(2 * np.pi * vibrato_hz * t)
    if jitter_cents:
        rng = np.random.default_rng(semilla)
        ruido = rng.standard_normal(n // 160 + 2)
        # paseo suave (~2 Hz) interpolado a la tasa de muestreo
        suave = np.convolve(ruido, np.hanning(25), mode="same")
        suave = suave / (np.std(suave) + 1e-12) * jitter_cents
        cents = cents + np.interp(np.arange(n), np.arange(len(suave)) * 160, suave)
    f = midi_hz(midi) * 2 ** (cents / 1200)
    fase = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(fase) + 0.5 * np.sin(2 * fase) + 0.25 * np.sin(3 * fase)
    rampa = min(n // 2, int(0.01 * SR))
    env = np.ones(n)
    env[:rampa] = np.linspace(0, 1, rampa)
    env[n - rampa :] = np.linspace(1, 0, rampa)
    return (amplitud / 1.75 * y * env).astype(np.float32)


def silencio(dur: float) -> np.ndarray:
    return np.zeros(int(round(dur * SR)), dtype=np.float32)


def aislada(y: np.ndarray, margen: float = 0.3) -> np.ndarray:
    return np.concatenate([silencio(margen), y, silencio(margen)])


def secuencia(
    notas: list[tuple[float, float]], pausa: float = 0.1, inicio: float = 0.3
) -> np.ndarray:
    """notas = [(midi_fraccional, duración)]; separadas por pausas cortas."""
    partes = [silencio(inicio)]
    for midi, dur in notas:
        partes += [tono(midi, dur), silencio(pausa)]
    partes.append(silencio(0.3))
    return np.concatenate(partes)


def con_ruido(y: np.ndarray, snr_db: float, semilla: int = 0) -> np.ndarray:
    rng = np.random.default_rng(semilla)
    potencia = np.mean(y[np.abs(y) > 0] ** 2)
    ruido = rng.standard_normal(len(y)) * np.sqrt(potencia / 10 ** (snr_db / 10))
    return (y + ruido).astype(np.float32)


def guardar(ruta: Path, y: np.ndarray) -> Path:
    sf.write(ruta, y, SR, subtype="PCM_16")
    return ruta


def midi_melodia(
    ruta: Path, notas: list[tuple[int, float, float]], acompanamiento: bool = False
) -> Path:
    """notas = [(midi, inicio_s, fin_s)]. Con acompañamiento agrega una voz grave superpuesta."""
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    voz = pretty_midi.Instrument(program=52, name="Melodia")
    for altura, ini, fin in notas:
        voz.notes.append(pretty_midi.Note(velocity=90, pitch=altura, start=ini, end=fin))
    if acompanamiento:
        for _altura, ini, fin in notas:
            voz.notes.append(pretty_midi.Note(velocity=60, pitch=48, start=ini, end=fin))
    pm.instruments.append(voz)
    pm.write(str(ruta))
    return ruta
