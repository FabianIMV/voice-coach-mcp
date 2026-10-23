"""Recording quality indicators: level, clipping, background noise and duration.

Noise is estimated by comparing the loudest frames with the quietest ones, so it needs the
recording to contain some pause (breaths, silence between phrases).
"""

from dataclasses import dataclass, field

import numpy as np

from ..config import SAMPLE_RATE

CLIPPING_THRESHOLD = 0.98
MAX_CLIPPING_PCT = 0.1
MIN_SNR_DB = 15.0
SILENCE_DBFS = -60.0
EPS = 1e-6  # -120 dBFS floor


@dataclass
class Quality:
    duration_s: float
    peak_dbfs: float
    rms_dbfs: float
    snr_db: float | None
    clipping_pct: float
    warnings: list[dict] = field(default_factory=list)
    factor: float = 1.0  # confidence multiplier in [0, 1]

    def levels(self) -> dict:
        return {
            "peak_dbfs": self.peak_dbfs,
            "rms_dbfs": self.rms_dbfs,
            "snr_db": self.snr_db,
            "clipping_pct": self.clipping_pct,
        }


def warning(code: str, detail: str) -> dict:
    return {"code": code, "detail": detail}


def db(x: float | np.ndarray) -> float | np.ndarray:
    return 20 * np.log10(np.maximum(x, EPS))


def _frame_rms(y: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if len(y) < frame:
        return np.array([np.sqrt(np.mean(y**2))]) if len(y) else np.array([0.0])
    windows = np.lib.stride_tricks.sliding_window_view(y, frame)[::hop]
    return np.sqrt(np.mean(windows**2, axis=1))


def _flatness(y: np.ndarray) -> float:
    """Spectral flatness of a fragment (0 = tonal, ~0.56 = white noise)."""
    spectrum = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2 + EPS
    return float(np.exp(np.mean(np.log(spectrum))) / np.mean(spectrum))


def assess(y: np.ndarray, sr: int = SAMPLE_RATE, min_duration: float = 1.0) -> Quality:
    duration = len(y) / sr
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    rms = float(np.sqrt(np.mean(y**2))) if len(y) else 0.0
    clipping = float(np.mean(np.abs(y) >= CLIPPING_THRESHOLD) * 100) if len(y) else 0.0

    frame, hop = int(0.03 * sr), int(0.01 * sr)
    frame_rms = _frame_rms(y, frame, hop)
    frame_db = db(frame_rms)
    loud, quiet = np.percentile(frame_db, 95), np.percentile(frame_db, 10)
    snr: float | None = float(min(loud - quiet, 60.0))

    quality = Quality(
        duration_s=round(duration, 2),
        peak_dbfs=round(float(db(peak)), 1),
        rms_dbfs=round(float(db(rms)), 1),
        snr_db=None,
        clipping_pct=round(clipping, 3),
    )
    warnings = quality.warnings

    if peak == 0.0:
        warnings.append(
            warning("digital_silence", "The audio is pure digital silence (all zeros).")
        )
        quality.factor = 0.0
        return quality
    if quality.peak_dbfs < SILENCE_DBFS:
        warnings.append(warning("silence", f"Very low level (peak {quality.peak_dbfs} dBFS)."))
        quality.factor = 0.0
        return quality

    # If the quietest frames are tonal (no pauses in the recording), SNR cannot be estimated.
    quietest = np.argsort(frame_rms)[: max(1, len(frame_rms) // 10)]
    sample = np.concatenate([y[i * hop : i * hop + frame] for i in quietest[:50]])
    if _flatness(sample) < 0.1 and snr < MIN_SNR_DB:
        snr = None
    quality.snr_db = None if snr is None else round(snr, 1)

    if clipping > MAX_CLIPPING_PCT:
        warnings.append(warning("clipping", f"{quality.clipping_pct}% of samples are clipped."))
        quality.factor *= 0.8
    if snr is not None and snr < MIN_SNR_DB:
        warnings.append(warning("noise", f"High background noise (estimated SNR {snr:.0f} dB)."))
        quality.factor *= max(0.3, snr / MIN_SNR_DB)
    if duration < min_duration:
        warnings.append(warning("short_audio", f"Audio is {duration:.1f} s (< {min_duration} s)."))
        quality.factor *= 0.7
    return quality


def confidence(value: float) -> dict:
    value = float(np.clip(value, 0.0, 1.0))
    level = "high" if value >= 0.75 else "medium" if value >= 0.45 else "low"
    return {"value": round(value, 2), "level": level}
