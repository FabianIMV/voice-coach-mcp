"""Transcription with faster-whisper: lazy, cached model with word-level timestamps."""

import threading
from dataclasses import dataclass, field

import numpy as np

from ..config import Config
from ..errors import UserError

_LANGUAGES = {
    "en": "en", "english": "en", "inglés": "en", "ingles": "en",
    "es": "es", "spanish": "es", "español": "es", "espanol": "es", "castellano": "es",
}  # fmt: skip

# An initial prompt full of fillers makes Whisper transcribe them instead of "cleaning them up".
FILLER_PROMPTS = {
    "en": "Umm, uh, so, like, you know, I mean, uh... hmm.",
    "es": "Eh, bueno, este... o sea, mmm, ¿no? Pues, eh, digamos que...",
}

_models: dict[tuple[str, str, str], object] = {}
_lock = threading.Lock()


@dataclass
class Word:
    text: str
    start: float
    end: float
    prob: float


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcript:
    language: str
    language_prob: float
    segments: list[Segment]

    @property
    def words(self) -> list[Word]:
        return [w for s in self.segments for w in s.words]

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments).strip()


def language_code(language: str | None) -> str | None:
    """ "en", "en-US", "es-CL", "English", "español"… → Whisper code; None = auto-detect."""
    if not language:
        return None
    key = language.strip().lower()
    code = _LANGUAGES.get(key) or _LANGUAGES.get(key.split("-")[0].split("_")[0])
    if code:
        return code
    base = key.split("-")[0]
    if len(base) == 2 and base.isalpha():
        return base  # Whisper supports many more languages; pass it through
    raise UserError(f"Unrecognized language: '{language}'. Use a code such as 'en' or 'es-CL'.")


def model(config: Config):
    key = (config.whisper_model, config.whisper_device, config.whisper_compute_type)
    with _lock:
        if key not in _models:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise UserError(
                    "faster-whisper is missing. Install it with: uv sync --extra speech"
                ) from e
            options = {"device": config.whisper_device, "compute_type": config.whisper_compute_type}
            try:  # local cache first, no network; download only if missing
                _models[key] = WhisperModel(config.whisper_model, local_files_only=True, **options)
            except Exception:  # faster-whisper has no specific "not cached" error type
                _models[key] = WhisperModel(config.whisper_model, **options)
        return _models[key]


def transcribe(
    y: np.ndarray, config: Config, language: str | None = None, keep_fillers: bool = False
) -> Transcript:
    code = language_code(language)
    whisper = model(config)
    prompt = FILLER_PROMPTS.get(code or "") if keep_fillers else None
    with _lock:  # one transcription at a time: the model already uses every core
        segments, info = whisper.transcribe(
            y,
            language=code,
            word_timestamps=True,
            vad_filter=True,
            initial_prompt=prompt,
            condition_on_previous_text=False,
        )
        result = [
            Segment(
                start=s.start,
                end=s.end,
                text=s.text.strip(),
                words=[Word(w.word.strip(), w.start, w.end, w.probability) for w in s.words or []],
            )
            for s in segments
        ]
    return Transcript(
        language=info.language, language_prob=info.language_probability, segments=result
    )
