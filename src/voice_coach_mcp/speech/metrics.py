"""Speech metrics from the transcript (timed words) and the audio.

Everything here is independent of the transcription model so it can be tested with fake data.
"""

import re
import tomllib
from collections import Counter
from dataclasses import dataclass
from importlib import resources

import numpy as np

from ..config import SAMPLE_RATE, Config
from ..errors import UserError
from .transcription import Transcript, Word

PAUSE_THRESHOLD_S = 0.7
ISOLATION_PAUSE_S = 0.3  # an ambiguous filler counts when surrounded by a pause like this
MONOTONE_ST = 2.0  # pitch standard deviation (semitones) below which speech is monotone
PITCH_WINDOW_S, PITCH_STEP_S = 8.0, 4.0
FLAT_VOLUME_DB = 3.0  # between-word deviation below which volume is flat
_PUNCTUATION = ".,;:!?¿¡…\"'«»()[]-–—"


# --- Pace and pauses -----------------------------------------------------------------------


def pace(words: list[Word], pauses: list[dict]) -> dict:
    if not words:
        return {"words": 0}
    speaking_time = words[-1].end - words[0].start
    without_pauses = speaking_time - sum(p["dur"] for p in pauses)
    data = {"words": len(words), "speaking_time_s": round(speaking_time, 1)}
    if speaking_time > 0:
        data["words_per_minute"] = round(60 * len(words) / speaking_time)
    if without_pauses > 0:
        data["wpm_excluding_long_pauses"] = round(60 * len(words) / without_pauses)
    return data


def pauses(
    words: list[Word],
    threshold: float = PAUSE_THRESHOLD_S,
    y: np.ndarray | None = None,
    sr: int = SAMPLE_RATE,
) -> list[dict]:
    """Silences of at least `threshold` seconds between the first and the last word.

    With the audio, silences are measured by energy: Whisper tends to stretch word endings into
    the silence, so its gaps underestimate pauses. Without audio, gaps between words are used.
    """
    if len(words) < 2:
        return []
    if y is None:
        spans = [(a.end, b.start) for a, b in zip(words, words[1:], strict=False)]
    else:
        spans = _silences(y, sr, words[0].start, words[-1].end)
    items = []
    for start, end in spans:
        if end - start < threshold:
            continue
        before = [w for w in words if w.start < start]
        after = before[-1].text.strip(_PUNCTUATION) if before else ""
        items.append({"t": round(start, 2), "dur": round(end - start, 2), "after": after})
    return items


def _silences(y: np.ndarray, sr: int, start: float, end: float) -> list[tuple[float, float]]:
    hop, frame = int(0.01 * sr), int(0.03 * sr)
    if len(y) < frame:
        return []
    windows = np.lib.stride_tricks.sliding_window_view(y, frame)[::hop]
    db = 10 * np.log10(np.maximum(np.mean(windows**2, axis=1), 1e-12))
    p10, p95 = np.percentile(db, [10, 95])
    threshold_db = max(p10 + 6, p95 - 35)
    i0, i1 = int(start * sr / hop), int(np.ceil(end * sr / hop))
    silent = db[i0:i1] < threshold_db
    edges = np.diff(np.concatenate([[0], silent.astype(int), [0]]))
    return [
        ((i0 + a) * hop / sr + frame / (2 * sr), (i0 + b) * hop / sr + frame / (2 * sr))
        for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True)
    ]


def pause_summary(items: list[dict], minutes: float, threshold: float) -> dict:
    data: dict = {"threshold_s": threshold, "count": len(items)}
    if items:
        data["total_s"] = round(sum(p["dur"] for p in items), 1)
        data["max_s"] = max(p["dur"] for p in items)
    if minutes > 0:
        data["per_minute"] = round(len(items) / minutes, 1)
    data["items"] = items
    return data


# --- Fillers -------------------------------------------------------------------------------


@dataclass
class FillerLists:
    vocalizations: list[re.Pattern]
    phrases: list[tuple[list[str], bool]]  # (normalized tokens, requires "?")
    ambiguous: set[str]


def normalize(text: str) -> str:
    return text.lower().strip().strip(_PUNCTUATION).strip()


def load_filler_lists(config: Config, language: str) -> FillerLists | None:
    base = tomllib.loads(resources.files(__package__).joinpath("fillers.toml").read_text("utf-8"))
    if config.fillers_file:
        try:
            base.update(tomllib.loads(config.fillers_file.read_text("utf-8")))
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise UserError(
                f"Could not read VOICE_COACH_FILLERS ({config.fillers_file}): {e}"
            ) from e
    section = base.get(language)
    if not section:
        return None
    return FillerLists(
        vocalizations=[re.compile(p) for p in section.get("vocalizations", [])],
        phrases=[([normalize(t) for t in p.split()], "?" in p) for p in section.get("phrases", [])],
        ambiguous={normalize(a) for a in section.get("ambiguous", [])},
    )


def fillers(transcript: Transcript, lists: FillerLists, minutes: float) -> dict:
    occurrences = []
    for segment in transcript.segments:
        words = segment.words
        norms = [normalize(w.text) for w in words]
        used: set[int] = set()
        for i, word in enumerate(words):
            if i in used or not norms[i]:
                continue
            found = _phrase(words, norms, i, lists)
            if found:
                n, text = found
                used.update(range(i, i + n))
            elif any(p.fullmatch(norms[i]) for p in lists.vocalizations):
                text = norms[i]
            elif norms[i] in lists.ambiguous and _isolated(words, i):
                text = norms[i]
            else:
                continue
            occurrences.append({"t": round(word.start, 2), "text": text})

    by_type = Counter(_kind(o["text"], lists) for o in occurrences)
    data: dict = {"total": len(occurrences)}
    if minutes > 0:
        data["per_minute"] = round(len(occurrences) / minutes, 1)
    data["by_type"] = dict(by_type.most_common())
    data["occurrences"] = occurrences
    return data


def _kind(text: str, lists: FillerLists) -> str:
    """Groups vocalization variants ("uhh", "uuh") under one pattern."""
    for pattern in lists.vocalizations:
        if pattern.fullmatch(text):
            compact = re.sub(r"(.)\1+", r"\1", text)
            return compact * 3 if len(compact) == 1 else compact  # "mmmm" → "mmm"
    return text


def _phrase(words: list[Word], norms: list[str], i: int, lists: FillerLists):
    for tokens, question in lists.phrases:
        n = len(tokens)
        if norms[i : i + n] != tokens:
            continue
        if question and "?" not in words[i + n - 1].text:
            continue
        return n, " ".join(tokens) + ("?" if question else "")
    return None


def _isolated(words: list[Word], i: int) -> bool:
    word = words[i]
    if i == 0 or word.text.rstrip().endswith((",", "...", "…")):
        return True
    previous = words[i - 1]
    if previous.text.rstrip().endswith((",", ".", "...", "…")):
        return True
    if word.start - previous.end >= ISOLATION_PAUSE_S:
        return True
    return i + 1 < len(words) and words[i + 1].start - word.end >= ISOLATION_PAUSE_S


# --- Pitch and volume ----------------------------------------------------------------------


def _speech_mask(n_frames: int, words: list[Word], fps: float) -> np.ndarray:
    mask = np.zeros(n_frames, dtype=bool)
    for w in words:
        mask[int(w.start * fps) : int(np.ceil(w.end * fps))] = True
    return mask


def pitch(y: np.ndarray, words: list[Word], sr: int = SAMPLE_RATE) -> dict:
    """Variation of the fundamental frequency while speaking, in semitones."""
    import librosa

    hop = 160
    f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=500, sr=sr, frame_length=1024, hop_length=hop)
    fps = sr / hop
    valid = voiced & np.isfinite(f0) & _speech_mask(len(f0), words, fps)
    if valid.sum() < fps:  # less than 1 s of voiced speech
        return {"voiced_s": round(valid.sum() / fps, 1)}
    median = float(np.median(f0[valid]))
    st = np.full(len(f0), np.nan)
    st[valid] = 12 * np.log2(f0[valid] / median)
    std = float(np.nanstd(st))
    p10, p90 = np.nanpercentile(st, [10, 90])
    return {
        "median_f0_hz": round(median),
        "std_semitones": round(std, 2),
        "range_p10_p90_semitones": round(float(p90 - p10), 1),
        "monotone": std < MONOTONE_ST,
        "monotone_stretches": _monotone_stretches(st, fps),
    }


def _monotone_stretches(st: np.ndarray, fps: float) -> list[dict]:
    window, step = int(PITCH_WINDOW_S * fps), int(PITCH_STEP_S * fps)
    stretches: list[dict] = []
    for start in range(0, max(1, len(st) - window + 1), step):
        chunk = st[start : start + window]
        if np.sum(np.isfinite(chunk)) < fps or np.nanstd(chunk) >= MONOTONE_ST:
            continue
        t0, t1 = start / fps, min(len(st), start + window) / fps
        if stretches and t0 <= stretches[-1]["end"]:
            stretches[-1]["end"] = round(t1, 1)
        else:
            stretches.append({"t": round(t0, 1), "end": round(t1, 1)})
    return stretches


def volume(y: np.ndarray, words: list[Word], sr: int = SAMPLE_RATE) -> dict:
    """Per-word level (dBFS) and how much it varies between words."""
    levels = []
    for w in words:
        chunk = y[int(w.start * sr) : int(w.end * sr)]
        if len(chunk):
            levels.append(10 * np.log10(max(float(np.mean(chunk**2)), 1e-12)))
    if len(levels) < 3:
        return {}
    levels = np.array(levels)
    std = float(np.std(levels))
    p10, p90 = np.percentile(levels, [10, 90])
    return {
        "mean_dbfs": round(float(np.mean(levels)), 1),
        "std_between_words_db": round(std, 1),
        "range_p10_p90_db": round(float(p90 - p10), 1),
        "low_variation": std < FLAT_VOLUME_DB,
    }
