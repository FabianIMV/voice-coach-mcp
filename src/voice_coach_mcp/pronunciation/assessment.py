"""assess_pronunciation tool: picks the backend, assesses and builds the compact response."""

from collections import Counter

from ..audio import quality as q
from ..audio.io import load, resolve_path
from ..config import Config
from ..errors import UserError
from ..output import Trimmable, fit
from .base import PronunciationBackend, WordResult


def backend(config: Config) -> PronunciationBackend:
    if config.pronunciation_backend == "local":
        from .wav2vec2 import Wav2Vec2Backend

        return Wav2Vec2Backend()
    if config.pronunciation_backend == "azure":
        from .azure import AzureBackend

        return AzureBackend()
    raise UserError(
        f"VOICE_COACH_PRONUNCIATION_BACKEND='{config.pronunciation_backend}' does not exist; use 'local' or 'azure'."
    )


def _item(r: WordResult) -> dict:
    item: dict = {"word": r.word, "score": round(r.score)}
    if r.start is not None:
        item["t"] = r.start
    if r.missing:
        item["missing"] = True
    elif r.errors:
        item["expected"] = " ".join(r.expected)
        item["detected"] = " ".join(r.detected)
        item["errors"] = [e.to_dict() for e in r.errors]
    return item


def assess(audio: str, expected_text: str, config: Config, language: str = "en-US") -> str:
    path = resolve_path(audio, config)
    y = load(path)
    quality = q.assess(y, min_duration=0.5)
    result: dict = {"audio": str(path), "duration_s": quality.duration_s, "language": language}
    warnings = list(quality.warnings)
    confidence = 0.0
    if quality.factor > 0:
        r = backend(config).assess(y, expected_text, language, config)
        warnings += r.warnings
        counts = Counter(e.type for w in r.words for e in w.errors)
        confusions = Counter(
            (e.expected, e.detected)
            for w in r.words
            for e in w.errors
            if e.type == "substitution" and e.expected and e.detected
        )
        result["backend"] = r.backend
        result["summary"] = {
            "overall_score": round(r.overall_score),
            "words": len(r.words),
            "words_with_errors": sum(bool(w.errors) for w in r.words),
            "errors": {t: counts.get(t, 0) for t in ("substitution", "deletion", "insertion")},
            "frequent_confusions": [
                {"expected": a, "detected": b, "count": n}
                for (a, b), n in confusions.most_common(5)
            ],
            **r.extra,
        }
        result["words"] = [_item(w) for w in r.words]
        result["phonemes"] = {
            "expected": " ".join(r.expected_phonemes),
            "detected": " ".join(r.detected_phonemes),
        }
        confidence = quality.factor * min(1.0, r.model_confidence / 0.8)
        if r.relative_distance > 0.6:
            confidence *= 0.3
    result["confidence"] = q.confidence(confidence)
    result["warnings"] = warnings
    return fit(
        result,
        audio=path,
        tool="pronunciation",
        config=config,
        trimmable=[
            "phonemes.detected",
            "phonemes.expected",
            Trimmable("words", lambda w: 100 - w["score"]),
        ],
    )
