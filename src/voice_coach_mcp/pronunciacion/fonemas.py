"""Fonemas esperados (phonemizer + espeak-ng) y normalización del inventario IPA."""

import os
import re
import sys
import threading
from pathlib import Path

from ..errores import ErrorUsuario

_IDIOMAS_ESPEAK = {
    "en": "en-us",
    "en-us": "en-us",
    "en-gb": "en-gb",
    "es": "es",
    "es-419": "es-419",
}
_LIBRERIAS_MAC = ("/opt/homebrew/lib/libespeak-ng.dylib", "/usr/local/lib/libespeak-ng.dylib")

# Tokens compuestos que el modelo o espeak emiten juntos y conviene comparar por separado.
_COMPUESTOS = {
    "ɑːɹ": ["ɑː", "ɹ"], "ɔːɹ": ["ɔː", "ɹ"], "oːɹ": ["oː", "ɹ"], "ɪɹ": ["ɪ", "ɹ"],
    "ʊɹ": ["ʊ", "ɹ"], "ɛɹ": ["ɛ", "ɹ"], "əl": ["ə", "l"], "aɪɚ": ["aɪ", "ɚ"],
    "aɪə": ["aɪ", "ə"], "iə": ["i", "ə"], "n̩": ["ə", "n"], "l̩": ["ə", "l"],
}  # fmt: skip
# Variantes que no cuentan como error (alófonos o diferencias de transcripción de espeak).
_EQUIVALENTES = {"ɐ": "ə", "ᵻ": "ɪ", "ɜː": "ɚ", "ɜ": "ɚ", "ɫ": "l", "r": "ɹ", "g": "ɡ", "oː": "oʊ"}
_TOLERADOS = {
    frozenset(p) for p in [("ɾ", "t"), ("ɾ", "d"), ("i", "iː"), ("i", "ɪ"), ("ə", "ɪ"), ("ə", "ʌ"),
                           ("ɑː", "ɑ"), ("ɔː", "ɑː"), ("u", "uː"), ("ʔ", "t"), ("ə", "ɚ"),
                           ("ə", "i"), ("ə", "iː")]
}  # fmt: skip
VOCALES = set("aeiouyæɑɒɐəɛɜɚɪɨʉʊʌɔøœɯɤ")

_backends: dict[str, object] = {}
_candado = threading.Lock()


def idioma_espeak(idioma: str) -> str:
    clave = idioma.strip().lower().replace("_", "-")
    if clave in _IDIOMAS_ESPEAK:
        return _IDIOMAS_ESPEAK[clave]
    if clave.split("-")[0] == "en":
        return "en-us"
    raise ErrorUsuario(
        f"Idioma no soportado para pronunciación: '{idioma}'. Usa 'en-US' o 'en-GB'."
    )


def palabras_de(texto: str) -> list[str]:
    """Palabras del texto esperado, sin la puntuación que las rodea."""
    palabras = [p.strip('.,;:!?¿¡…"“”«»()[]—–') for p in texto.split()]
    return [p for p in palabras if p and re.search(r"\w", p)]


def _configurar_espeak() -> None:
    if os.environ.get("PHONEMIZER_ESPEAK_LIBRARY") or sys.platform != "darwin":
        return
    for ruta in _LIBRERIAS_MAC:
        if Path(ruta).exists():
            from phonemizer.backend.espeak.wrapper import EspeakWrapper

            EspeakWrapper.set_library(ruta)
            return


def _backend(idioma: str):
    with _candado:
        if idioma not in _backends:
            try:
                from phonemizer.backend import EspeakBackend
            except ImportError as e:
                raise ErrorUsuario(
                    "Falta phonemizer. Instálalo con: uv sync --extra pronunciacion"
                ) from e
            _configurar_espeak()
            try:
                _backends[idioma] = EspeakBackend(
                    idioma,
                    with_stress=False,
                    preserve_punctuation=False,
                    language_switch="remove-flags",
                )
            except RuntimeError as e:
                raise ErrorUsuario(
                    f"No encuentro espeak-ng ({e}). Instálalo con: brew install espeak-ng"
                ) from e
        return _backends[idioma]


def esperados_por_palabra(palabras: list[str], idioma: str) -> list[list[str]]:
    """Fonemas normalizados de cada palabra (cada palabra se fonetiza por separado)."""
    from phonemizer.separator import Separator

    backend = _backend(idioma_espeak(idioma))
    with _candado:
        crudos = backend.phonemize(
            palabras, separator=Separator(phone=" ", word="|", syllable=""), strip=True
        )
    # Un "palabra" puede expandirse a varias ("1984"): se unen sus fonemas.
    return [normalizar(c.replace("|", " ").split()) for c in crudos]


def normalizar(fonemas: list[str]) -> list[str]:
    salida = []
    for f in fonemas:
        f = f.replace("ˈ", "").replace("ˌ", "").strip()
        if not f:
            continue
        for parte in _COMPUESTOS.get(f, [f]):
            salida.append(_EQUIVALENTES.get(parte, parte))
    return salida


def tolerado(a: str, b: str) -> bool:
    return a == b or frozenset((a, b)) in _TOLERADOS


def es_vocal(f: str) -> bool:
    return bool(f) and f[0] in VOCALES
