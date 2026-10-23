"""Pitch contour extraction and note segmentation.

pYIN decides which frames are voiced and gives a coarse pitch (10-cent bins). Each voiced frame
is then refined by measuring its harmonics on a zero-padded spectrum with parabolic
interpolation, which yields ~1 cent accuracy across the whole range.
"""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d
from scipy.signal import find_peaks

from ..config import SAMPLE_RATE
from .theory import hz_to_midi

HOP = 160  # 10 ms at 16 kHz
FRAME = 1024
FINE_WINDOW = 1024
FINE_NFFT = 8192
HARMONICS = 8
FMIN, FMAX = 65.4, 1046.5  # C2–C6
MIN_NOTE_DURATION = 0.08
# The analysis window makes the voice "start" earlier and "end" later than it really does.
EDGE_S = FRAME / 4 / SAMPLE_RATE
NOTE_JUMP = 0.5  # semitones sustained for...
MIN_JUMP_S = 0.06  # ...this long to count as a new note
SMOOTHING_WINDOW_S = 0.2  # ~1 vibrato cycle: smoothing cancels it out for segmentation
MIN_VOICING_PROB = 0.2  # notes with a lower mean voicing probability are dropped (noise)
MIN_RELATIVE_ENERGY_DB = -35.0  # relative to the loudest parts of the audio
ENERGY_DIP_DB = 9.0  # a dip like this between two equal notes (consonant, breath) splits them
VIBRATO_HZ = (4.0, 8.0)
MAX_STABLE_CENTS = 15.0


@dataclass
class Contour:
    midi: np.ndarray  # fractional MIDI pitch; nan when unvoiced
    voicing_prob: np.ndarray
    energy_db: np.ndarray
    sr: int = SAMPLE_RATE
    hop: int = HOP

    @property
    def fps(self) -> float:
        return self.sr / self.hop

    def time(self, frame: int) -> float:
        return frame / self.fps


@dataclass
class Note:
    start: float
    end: float
    midi: float  # representative pitch (median of the central part)
    std_cents: float
    stability: str  # "stable" | "vibrato" | "unstable"
    drift_cents: float
    vibrato_hz: float | None = None
    vibrato_pp_cents: float | None = None
    voicing_prob: float = 1.0

    @property
    def duration(self) -> float:
        return self.end - self.start


def extract_contour(y: np.ndarray, sr: int = SAMPLE_RATE, a4: float = 440.0) -> Contour:
    import librosa

    if len(y) < FRAME:
        y = np.pad(y, (0, FRAME - len(y)))
    f0, voiced, prob = librosa.pyin(
        y, fmin=FMIN, fmax=FMAX, sr=sr, frame_length=FRAME, hop_length=HOP, resolution=0.1
    )
    f0 = np.where(voiced, f0, np.nan)
    fine = _refine_hz(y, sr, f0)
    coarse = hz_to_midi(f0, a4)
    refined = hz_to_midi(fine, a4)
    # The refinement is accepted only when it agrees with pYIN (avoids harmonic jumps).
    midi = np.where(np.abs(refined - coarse) < 0.5, refined, coarse)
    rms = librosa.feature.rms(y=y, frame_length=2 * HOP, hop_length=HOP)[0]
    energy = 20 * np.log10(np.maximum(np.pad(rms, (0, max(0, len(midi) - len(rms)))), 1e-5))
    return Contour(midi=midi, voicing_prob=prob, energy_db=energy[: len(midi)], sr=sr)


def _refine_hz(y: np.ndarray, sr: int, f0: np.ndarray) -> np.ndarray:
    """Fine fundamental frequency per frame, from the peaks of its harmonics."""
    fine = np.full(len(f0), np.nan)
    frames = np.flatnonzero(np.isfinite(f0))
    if len(frames) == 0:
        return fine
    half = FINE_WINDOW // 2
    padded = np.pad(y, half)
    window = np.hanning(FINE_WINDOW)
    bin_hz = sr / FINE_NFFT
    for batch in np.array_split(frames, max(1, len(frames) // 256)):
        segments = np.stack([padded[f * HOP : f * HOP + FINE_WINDOW] for f in batch]) * window
        magnitude = np.abs(np.fft.rfft(segments, FINE_NFFT, axis=1)) + 1e-12
        log_mag = np.log(magnitude)
        for k, frame in enumerate(batch):
            estimates, weights = [], []
            for h in range(1, HARMONICS + 1):
                center = h * f0[frame] / bin_hz
                if center * 1.03 >= FINE_NFFT // 2 - 1:
                    break
                lo, hi = int(center * 0.97), int(np.ceil(center * 1.03)) + 1
                j = lo + int(np.argmax(log_mag[k, lo:hi]))
                if j in (lo, hi - 1):  # no local maximum inside the search window
                    continue
                a, b, c = log_mag[k, j - 1 : j + 2]
                curvature = a - 2 * b + c
                delta = 0.5 * (a - c) / curvature if curvature < 0 else 0.0
                estimates.append((j + delta) * bin_hz / h)
                weights.append(magnitude[k, j])
            if estimates:
                fine[frame] = np.average(estimates, weights=weights)
    return fine


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) intervals where the mask is true."""
    edges = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True))


def _voiced_runs(
    voiced: np.ndarray, energy_db: np.ndarray, min_frames: int
) -> list[tuple[int, int]]:
    """Voiced runs, also split at clear energy dips (repeated notes)."""
    runs = []
    for a, b in _runs(voiced):
        dips, _ = find_peaks(-energy_db[a:b], prominence=ENERGY_DIP_DB, distance=max(1, min_frames))
        bounds = [a, *(a + d for d in dips), b]
        runs += list(zip(bounds[:-1], bounds[1:], strict=True))
    return runs


def _splits(smooth: np.ndarray, raw: np.ndarray, min_frames: int) -> list[int]:
    """Note-change points inside a voiced run."""
    splits, ref, note_start, outside = [], smooth[0], 0, 0
    for i in range(1, len(smooth)):
        if abs(smooth[i] - ref) > NOTE_JUMP:
            outside += 1
            if outside >= min_frames:
                candidate = i - outside + 1
                splits.append(_refine_split(raw, candidate, note_start, ref, smooth[i]))
                note_start, ref, outside = splits[-1], smooth[i], 0
        else:
            outside = 0
            ref = np.median(smooth[note_start : i + 1])
    return splits


def _refine_split(
    raw: np.ndarray, candidate: int, minimum: int, before: float, after: float
) -> int:
    """Places the change where the raw contour crosses the midpoint between both notes."""
    midpoint = (before + after) / 2
    sign = np.sign(after - before)
    radius = 15
    for i in range(max(minimum + 1, candidate - radius), min(len(raw), candidate + radius)):
        if sign * (raw[i] - midpoint) > 0:
            return i
    return candidate


def _stats(cents: np.ndarray, fps: float) -> dict:
    """Stability of the contour (in cents) of a note's central part."""
    t = np.arange(len(cents)) / fps
    slope, intercept = np.polyfit(t, cents, 1) if len(cents) > 2 else (0.0, float(np.mean(cents)))
    residual = cents - (slope * t + intercept)
    std = float(np.std(residual))
    data = {"std": std, "drift": float(slope * t[-1]) if len(t) else 0.0, "stability": None}

    if len(cents) / fps >= 0.3 and std > 5:
        n_fft = max(1024, len(residual))
        power = np.abs(np.fft.rfft(residual * np.hanning(len(residual)), n_fft)) ** 2
        freqs = np.fft.rfftfreq(n_fft, 1 / fps)
        band = (freqs >= VIBRATO_HZ[0]) & (freqs <= VIBRATO_HZ[1])
        total = power[1:].sum()
        if total > 0 and power[band].sum() / total > 0.5:
            peak = freqs[band][np.argmax(power[band])]
            pp = 2 * np.sqrt(2) * std  # peak-to-peak of a sinusoid with that deviation
            if 20 <= pp <= 300:
                data.update(stability="vibrato", vibrato_hz=float(peak), vibrato_pp=float(pp))
    if data["stability"] is None:
        data["stability"] = "stable" if std <= MAX_STABLE_CENTS else "unstable"
    return data


def segment(contour: Contour) -> list[Note]:
    fps = contour.fps
    midi = contour.midi
    voiced = np.isfinite(midi)
    min_frames = max(1, round(MIN_JUMP_S * fps))
    window = max(1, round(SMOOTHING_WINDOW_S * fps))
    notes: list[Note] = []
    energy_floor = np.percentile(contour.energy_db, 95) + MIN_RELATIVE_ENERGY_DB

    for a, b in _voiced_runs(voiced, contour.energy_db, round(MIN_NOTE_DURATION * fps)):
        raw = median_filter(midi[a:b], size=5, mode="nearest")
        smooth = uniform_filter1d(raw, size=window, mode="nearest")
        bounds = [0, *_splits(smooth, raw, min_frames), b - a]
        for i0, i1 in zip(bounds[:-1], bounds[1:], strict=True):
            voice_starts = i0 == 0 and (a == 0 or not voiced[a - 1])
            voice_ends = a + i1 == b and (b == len(voiced) or not voiced[b])
            start = contour.time(a + i0) + (EDGE_S if voice_starts else 0.0)
            end = contour.time(a + i1) - (EDGE_S if voice_ends else 0.0)
            prob = float(np.mean(contour.voicing_prob[a + i0 : a + i1]))
            if (
                end - start < MIN_NOTE_DURATION
                or prob < MIN_VOICING_PROB
                or np.median(contour.energy_db[a + i0 : a + i1]) < energy_floor
            ):
                continue
            segment_midi = midi[a + i0 : a + i1]
            n = len(segment_midi)
            core = segment_midi[int(0.2 * n) : max(int(0.2 * n) + 1, int(0.9 * n))]
            pitch = float(np.median(core))
            stats = _stats((core - pitch) * 100, fps)
            notes.append(
                Note(
                    start=start,
                    end=end,
                    midi=pitch,
                    std_cents=stats["std"],
                    stability=stats["stability"],
                    drift_cents=stats["drift"],
                    vibrato_hz=stats.get("vibrato_hz"),
                    vibrato_pp_cents=stats.get("vibrato_pp"),
                    voicing_prob=prob,
                )
            )
    return notes
