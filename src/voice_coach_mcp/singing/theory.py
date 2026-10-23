"""Hz ↔ MIDI ↔ cents conversion, note names and keys."""

import re
import unicodedata

import numpy as np

from ..errors import UserError

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SOLFEGE = {"do": "C", "re": "D", "mi": "E", "fa": "F", "sol": "G", "la": "A", "si": "B"}
_MAJOR = (0, 2, 4, 5, 7, 9, 11)
_MINOR = (0, 2, 3, 5, 7, 8, 10)


def hz_to_midi(hz: float | np.ndarray, a4: float = 440.0) -> float | np.ndarray:
    return 69 + 12 * np.log2(np.asarray(hz) / a4)


def midi_to_hz(midi: float | np.ndarray, a4: float = 440.0) -> float | np.ndarray:
    return a4 * 2 ** ((np.asarray(midi) - 69) / 12)


def note_name(midi: int) -> str:
    """Scientific pitch notation with sharps: 60 → C4, 69 → A4."""
    midi = int(midi)
    return f"{NAMES[midi % 12]}{midi // 12 - 1}"


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def parse_key(text: str) -> tuple[frozenset[int], str]:
    """Accepts "A minor", "Am", "Bb major", "F#", and Spanish names ("La menor", "Sol mayor").

    Returns the pitch classes (0 = C) of the scale (major or natural minor) and a normalized
    name such as "A minor".
    """
    t = _strip_accents(text.strip()).lower()
    m = re.fullmatch(
        r"(do|re|mi|fa|sol|la|si|[a-g])\s*(#|b|♯|♭|sharp|flat|sostenido|bemol)?\s*"
        r"(m|min|minor|menor|maj|major|mayor)?",
        t,
    )
    if not m:
        raise UserError(
            f"Unrecognized key '{text}'. Valid examples: 'A minor', 'Am', 'F#', 'Bb major'."
        )
    root, accidental, mode = m.groups()
    letter = _SOLFEGE.get(root, root).upper()
    tonic = _LETTERS[letter]
    if accidental in ("#", "♯", "sharp", "sostenido"):
        tonic += 1
    elif accidental in ("b", "♭", "flat", "bemol"):
        tonic -= 1
    tonic %= 12
    minor = mode in ("m", "min", "minor", "menor")
    scale = _MINOR if minor else _MAJOR
    classes = frozenset((tonic + i) % 12 for i in scale)
    return classes, f"{NAMES[tonic]} {'minor' if minor else 'major'}"


def target_note(midi: float, scale: frozenset[int] | None = None) -> int:
    """Nearest equal-tempered note; with a scale, the nearest note that belongs to it."""
    if scale is None:
        return int(round(midi))
    base = int(np.floor(midi))
    candidates = [n for n in range(base - 2, base + 4) if n % 12 in scale]
    return min(candidates, key=lambda n: abs(n - midi))
