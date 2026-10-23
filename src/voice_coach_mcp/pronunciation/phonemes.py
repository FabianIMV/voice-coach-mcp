"""Expected phonemes (phonemizer + espeak-ng) and normalization of the IPA inventory."""

import os
import re
import sys
import threading
from pathlib import Path

from ..errors import UserError

_ESPEAK_LANGUAGES = {
    "en": "en-us",
    "en-us": "en-us",
    "en-gb": "en-gb",
    "es": "es",
    "es-419": "es-419",
}
_MAC_LIBRARIES = ("/opt/homebrew/lib/libespeak-ng.dylib", "/usr/local/lib/libespeak-ng.dylib")

# Compound tokens that the model or espeak emit together and are better compared separately.
_COMPOUNDS = {
    "ɑːɹ": ["ɑː", "ɹ"], "ɔːɹ": ["ɔː", "ɹ"], "oːɹ": ["oː", "ɹ"], "ɪɹ": ["ɪ", "ɹ"],
    "ʊɹ": ["ʊ", "ɹ"], "ɛɹ": ["ɛ", "ɹ"], "əl": ["ə", "l"], "aɪɚ": ["aɪ", "ɚ"],
    "aɪə": ["aɪ", "ə"], "iə": ["i", "ə"], "n̩": ["ə", "n"], "l̩": ["ə", "l"],
}  # fmt: skip
# Variants that do not count as errors (allophones or espeak transcription differences).
_EQUIVALENTS = {"ɐ": "ə", "ᵻ": "ɪ", "ɜː": "ɚ", "ɜ": "ɚ", "ɫ": "l", "r": "ɹ", "g": "ɡ", "oː": "oʊ"}
_TOLERATED = {
    frozenset(p) for p in [("ɾ", "t"), ("ɾ", "d"), ("i", "iː"), ("i", "ɪ"), ("ə", "ɪ"), ("ə", "ʌ"),
                           ("ɑː", "ɑ"), ("ɔː", "ɑː"), ("u", "uː"), ("ʔ", "t"), ("ə", "ɚ"),
                           ("ə", "i"), ("ə", "iː")]
}  # fmt: skip
VOWELS = set("aeiouyæɑɒɐəɛɜɚɪɨʉʊʌɔøœɯɤ")

_backends: dict[str, object] = {}
_lock = threading.Lock()


def espeak_language(language: str) -> str:
    key = language.strip().lower().replace("_", "-")
    if key in _ESPEAK_LANGUAGES:
        return _ESPEAK_LANGUAGES[key]
    if key.split("-")[0] == "en":
        return "en-us"
    raise UserError(f"Unsupported pronunciation language: '{language}'. Use 'en-US' or 'en-GB'.")


def words_of(text: str) -> list[str]:
    """Words of the expected text, without surrounding punctuation."""
    words = [w.strip('.,;:!?¿¡…"“”«»()[]—–') for w in text.split()]
    return [w for w in words if w and re.search(r"\w", w)]


def _configure_espeak() -> None:
    if os.environ.get("PHONEMIZER_ESPEAK_LIBRARY") or sys.platform != "darwin":
        return
    for path in _MAC_LIBRARIES:
        if Path(path).exists():
            from phonemizer.backend.espeak.wrapper import EspeakWrapper

            EspeakWrapper.set_library(path)
            return


def _backend(language: str):
    with _lock:
        if language not in _backends:
            try:
                from phonemizer.backend import EspeakBackend
            except ImportError as e:
                raise UserError(
                    "phonemizer is missing. Install it with: uv sync --extra pronunciation"
                ) from e
            _configure_espeak()
            try:
                _backends[language] = EspeakBackend(
                    language,
                    with_stress=False,
                    preserve_punctuation=False,
                    language_switch="remove-flags",
                )
            except RuntimeError as e:
                raise UserError(
                    f"espeak-ng not found ({e}). Install it with: brew install espeak-ng"
                ) from e
        return _backends[language]


def expected_by_word(words: list[str], language: str) -> list[list[str]]:
    """Normalized phonemes of each word (each word is phonemized separately)."""
    from phonemizer.separator import Separator

    backend = _backend(espeak_language(language))
    with _lock:
        raw = backend.phonemize(
            words, separator=Separator(phone=" ", word="|", syllable=""), strip=True
        )
    # A "word" can expand into several ("1984"): their phonemes are joined.
    return [normalize(r.replace("|", " ").split()) for r in raw]


def normalize(phonemes: list[str]) -> list[str]:
    out = []
    for p in phonemes:
        p = p.replace("ˈ", "").replace("ˌ", "").strip()
        if not p:
            continue
        for part in _COMPOUNDS.get(p, [p]):
            out.append(_EQUIVALENTS.get(part, part))
    return out


def tolerated(a: str, b: str) -> bool:
    return a == b or frozenset((a, b)) in _TOLERATED


def is_vowel(p: str) -> bool:
    return bool(p) and p[0] in VOWELS
