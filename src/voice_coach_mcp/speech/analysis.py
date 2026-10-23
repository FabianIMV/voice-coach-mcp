"""Speech tools: transcribe and speech_metrics."""

import numpy as np

from ..audio import quality as q
from ..audio.io import load, resolve_path
from ..config import Config
from ..output import Trimmable, fit
from . import metrics
from .transcription import Transcript, language_code, transcribe

MIN_SPEECH_DURATION_S = 5.0


def _segments(t: Transcript) -> list[dict]:
    return [{"t": round(s.start, 2), "end": round(s.end, 2), "text": s.text} for s in t.segments]


def _confidence_and_warnings(t: Transcript, requested_language: str | None, quality_factor: float):
    warnings = []
    words = t.words
    if not words:
        warnings.append(q.warning("no_speech", "No speech detected in the audio."))
        return 0.0, warnings
    prob = float(np.mean([w.prob for w in words]))
    confidence = quality_factor * min(1.0, prob / 0.85)
    if prob < 0.6:
        warnings.append(q.warning("uncertain_transcription", f"Mean word probability {prob:.2f}."))
    if requested_language is None and t.language_prob < 0.6:
        warnings.append(
            q.warning(
                "uncertain_language",
                f"Detected language '{t.language}' with probability {t.language_prob:.2f}.",
            )
        )
        confidence *= 0.7
    return confidence, warnings


def transcribe_audio(audio: str, config: Config, language: str | None = None) -> str:
    path = resolve_path(audio, config)
    y = load(path)
    quality = q.assess(y, min_duration=1.0)
    result: dict = {"audio": str(path), "duration_s": quality.duration_s}
    warnings = list(quality.warnings)
    confidence = 0.0
    if quality.factor > 0:
        t = transcribe(y, config, language)
        confidence, extra = _confidence_and_warnings(t, language_code(language), quality.factor)
        warnings += extra
        result |= {
            "language": t.language,
            "language_prob": round(t.language_prob, 2),
            "text": t.text,
            "segments": _segments(t),
            "words": [
                {"w": w.text, "t": round(w.start, 2), "end": round(w.end, 2)} for w in t.words
            ],
        }
    result["confidence"] = q.confidence(confidence)
    result["warnings"] = warnings
    return fit(
        result,
        audio=path,
        tool="transcript",
        config=config,
        trimmable=[Trimmable("words"), Trimmable("segments"), "text"],
    )


def speech_metrics(
    audio: str, config: Config, language: str, pause_threshold_s: float = metrics.PAUSE_THRESHOLD_S
) -> str:
    path = resolve_path(audio, config)
    y = load(path)
    quality = q.assess(y, min_duration=MIN_SPEECH_DURATION_S)
    code = language_code(language)
    result: dict = {"audio": str(path), "duration_s": quality.duration_s, "language": code}
    warnings = list(quality.warnings)
    confidence = 0.0

    if quality.factor > 0:
        t = transcribe(y, config, code, keep_fillers=True)
        confidence, extra = _confidence_and_warnings(t, code, quality.factor)
        warnings += extra
        words = t.words
        pause_items = metrics.pauses(words, pause_threshold_s, y)
        pace = metrics.pace(words, pause_items)
        minutes = pace.get("speaking_time_s", 0.0) / 60
        result["pace"] = pace
        result["pauses"] = metrics.pause_summary(pause_items, minutes, pause_threshold_s)
        lists = metrics.load_filler_lists(config, code)
        if lists:
            result["fillers"] = metrics.fillers(t, lists, minutes)
        else:
            warnings.append(q.warning("no_filler_list", f"No filler list for '{code}'."))
        if words:
            result["pitch"] = metrics.pitch(y, words)
            result["volume"] = metrics.volume(y, words)
        result["segments"] = _segments(t)

    result["confidence"] = q.confidence(confidence)
    result["warnings"] = warnings
    return fit(
        result,
        audio=path,
        tool="speech",
        config=config,
        trimmable=[
            Trimmable("segments"),
            Trimmable("fillers.occurrences"),
            Trimmable("pauses.items", lambda p: p["dur"]),
            Trimmable("pitch.monotone_stretches"),
        ],
    )
