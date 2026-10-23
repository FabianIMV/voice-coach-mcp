"""Conversión Hz ↔ MIDI ↔ cents, nombres de nota y tonalidades."""

import re
import unicodedata

import numpy as np

from ..errores import ErrorUsuario

NOMBRES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_LETRAS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SOLFEO = {"do": "C", "re": "D", "mi": "E", "fa": "F", "sol": "G", "la": "A", "si": "B"}
_MAYOR = (0, 2, 4, 5, 7, 9, 11)
_MENOR = (0, 2, 3, 5, 7, 8, 10)


def hz_a_midi(hz: float | np.ndarray, a4: float = 440.0) -> float | np.ndarray:
    return 69 + 12 * np.log2(np.asarray(hz) / a4)


def midi_a_hz(midi: float | np.ndarray, a4: float = 440.0) -> float | np.ndarray:
    return a4 * 2 ** ((np.asarray(midi) - 69) / 12)


def nombre_nota(midi: int) -> str:
    """Notación científica en inglés con sostenidos: 60 → C4, 69 → A4."""
    midi = int(midi)
    return f"{NOMBRES[midi % 12]}{midi // 12 - 1}"


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def parsear_tonalidad(texto: str) -> tuple[frozenset[int], str]:
    """Acepta "A minor", "Am", "La menor", "Sol mayor", "F#", "Bb major", "sib menor"…

    Devuelve las clases de altura (0 = C) de la escala (mayor o menor natural) y un nombre
    normalizado como "A menor".
    """
    t = _sin_tildes(texto.strip()).lower()
    m = re.fullmatch(
        r"(do|re|mi|fa|sol|la|si|[a-g])\s*(#|b|♯|♭|sostenido|bemol)?\s*"
        r"(m|min|minor|menor|maj|major|mayor)?",
        t,
    )
    if not m:
        raise ErrorUsuario(
            f"No entiendo la tonalidad '{texto}'. Ejemplos válidos: 'A minor', 'La menor', 'F#', 'Sib mayor'."
        )
    raiz, alteracion, modo = m.groups()
    letra = _SOLFEO.get(raiz, raiz).upper()
    tonica = _LETRAS[letra]
    if alteracion in ("#", "♯", "sostenido"):
        tonica += 1
    elif alteracion in ("b", "♭", "bemol"):
        tonica -= 1
    tonica %= 12
    menor = modo in ("m", "min", "minor", "menor")
    escala = _MENOR if menor else _MAYOR
    clases = frozenset((tonica + i) % 12 for i in escala)
    return clases, f"{NOMBRES[tonica]} {'menor' if menor else 'mayor'}"


def nota_objetivo(midi: float, escala: frozenset[int] | None = None) -> int:
    """Nota temperada más cercana; con escala, la más cercana que pertenezca a ella."""
    if escala is None:
        return int(round(midi))
    base = int(np.floor(midi))
    candidatas = [n for n in range(base - 2, base + 4) if n % 12 in escala]
    return min(candidatas, key=lambda n: abs(n - midi))
