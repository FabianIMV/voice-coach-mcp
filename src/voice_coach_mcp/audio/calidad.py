"""Indicadores de calidad de una grabación: nivel, clipping, ruido de fondo y duración.

El ruido se estima comparando los frames más fuertes con los más débiles, así que necesita
que la grabación tenga alguna pausa (respiraciones, silencios entre frases).
"""

from dataclasses import dataclass, field

import numpy as np

from ..config import SAMPLE_RATE

UMBRAL_CLIPPING = 0.98
PCT_CLIPPING_MAX = 0.1
SNR_MIN_DB = 15.0
SILENCIO_DBFS = -60.0
EPS = 1e-6  # piso de -120 dBFS


@dataclass
class Calidad:
    duracion_s: float
    pico_dbfs: float
    rms_dbfs: float
    snr_db: float | None
    clipping_pct: float
    advertencias: list[dict] = field(default_factory=list)
    factor: float = 1.0  # multiplicador de confianza en [0, 1]

    def niveles(self) -> dict:
        return {
            "pico_dbfs": self.pico_dbfs,
            "rms_dbfs": self.rms_dbfs,
            "snr_db": self.snr_db,
            "clipping_pct": self.clipping_pct,
        }


def advertencia(codigo: str, detalle: str) -> dict:
    return {"codigo": codigo, "detalle": detalle}


def db(x: float | np.ndarray) -> float | np.ndarray:
    return 20 * np.log10(np.maximum(x, EPS))


def _rms_frames(y: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if len(y) < frame:
        return np.array([np.sqrt(np.mean(y**2))]) if len(y) else np.array([0.0])
    ventanas = np.lib.stride_tricks.sliding_window_view(y, frame)[::hop]
    return np.sqrt(np.mean(ventanas**2, axis=1))


def _planitud(y: np.ndarray) -> float:
    """Planitud espectral (0 = tonal, ~0.56 = ruido blanco) de un fragmento."""
    espectro = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2 + EPS
    return float(np.exp(np.mean(np.log(espectro))) / np.mean(espectro))


def evaluar(y: np.ndarray, sr: int = SAMPLE_RATE, duracion_minima: float = 1.0) -> Calidad:
    duracion = len(y) / sr
    pico = float(np.max(np.abs(y))) if len(y) else 0.0
    rms = float(np.sqrt(np.mean(y**2))) if len(y) else 0.0
    clipping = float(np.mean(np.abs(y) >= UMBRAL_CLIPPING) * 100) if len(y) else 0.0

    frame, hop = int(0.03 * sr), int(0.01 * sr)
    rms_f = _rms_frames(y, frame, hop)
    db_f = db(rms_f)
    fuerte, debil = np.percentile(db_f, 95), np.percentile(db_f, 10)
    snr: float | None = float(min(fuerte - debil, 60.0))

    calidad = Calidad(
        duracion_s=round(duracion, 2),
        pico_dbfs=round(float(db(pico)), 1),
        rms_dbfs=round(float(db(rms)), 1),
        snr_db=None,
        clipping_pct=round(clipping, 3),
    )
    adv = calidad.advertencias

    if pico == 0.0:
        adv.append(advertencia("silencio_digital", "El audio es silencio absoluto (todo ceros)."))
        calidad.factor = 0.0
        return calidad
    if calidad.pico_dbfs < SILENCIO_DBFS:
        adv.append(advertencia("silencio", f"Nivel muy bajo (pico {calidad.pico_dbfs} dBFS)."))
        calidad.factor = 0.0
        return calidad

    # Si los frames débiles son tonales (sin pausas en la grabación) el SNR no es estimable.
    debiles = np.argsort(rms_f)[: max(1, len(rms_f) // 10)]
    muestra = np.concatenate([y[i * hop : i * hop + frame] for i in debiles[:50]])
    if _planitud(muestra) < 0.1 and snr < SNR_MIN_DB:
        snr = None
    calidad.snr_db = None if snr is None else round(snr, 1)

    if clipping > PCT_CLIPPING_MAX:
        adv.append(advertencia("clipping", f"{calidad.clipping_pct}% de muestras saturadas."))
        calidad.factor *= 0.8
    if snr is not None and snr < SNR_MIN_DB:
        adv.append(advertencia("ruido", f"Ruido de fondo alto (SNR estimado {snr:.0f} dB)."))
        calidad.factor *= max(0.3, snr / SNR_MIN_DB)
    if duracion < duracion_minima:
        adv.append(
            advertencia("audio_corto", f"Audio de {duracion:.1f} s (< {duracion_minima} s).")
        )
        calidad.factor *= 0.7
    return calidad


def nivel_confianza(valor: float) -> dict:
    valor = float(np.clip(valor, 0.0, 1.0))
    nivel = "alta" if valor >= 0.75 else "media" if valor >= 0.45 else "baja"
    return {"valor": round(valor, 2), "nivel": nivel}
