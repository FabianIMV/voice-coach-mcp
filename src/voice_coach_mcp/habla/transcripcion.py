"""Transcripción con faster-whisper: modelo perezoso, en caché y con timestamps por palabra."""

import threading
from dataclasses import dataclass, field

import numpy as np

from ..config import Config
from ..errores import ErrorUsuario

_IDIOMAS = {
    "es": "es", "español": "es", "espanol": "es", "spanish": "es", "castellano": "es",
    "en": "en", "inglés": "en", "ingles": "en", "english": "en",
}  # fmt: skip

# Un prompt inicial con muletillas hace que Whisper las transcriba en vez de "limpiarlas".
PROMPT_MULETILLAS = {
    "es": "Eh, bueno, este... o sea, mmm, ¿no? Pues, eh, digamos que...",
    "en": "Umm, uh, so, like, you know, I mean, uh... hmm.",
}

_modelos: dict[tuple[str, str, str], object] = {}
_candado = threading.Lock()


@dataclass
class Palabra:
    texto: str
    inicio: float
    fin: float
    prob: float


@dataclass
class Segmento:
    inicio: float
    fin: float
    texto: str
    palabras: list[Palabra] = field(default_factory=list)


@dataclass
class Transcripcion:
    idioma: str
    prob_idioma: float
    segmentos: list[Segmento]

    @property
    def palabras(self) -> list[Palabra]:
        return [p for s in self.segmentos for p in s.palabras]

    @property
    def texto(self) -> str:
        return " ".join(s.texto for s in self.segmentos).strip()


def codigo_idioma(idioma: str | None) -> str | None:
    """ "es", "es-CL", "en-US", "español", "English"… → código de Whisper; None = autodetectar."""
    if not idioma:
        return None
    clave = idioma.strip().lower()
    codigo = _IDIOMAS.get(clave) or _IDIOMAS.get(clave.split("-")[0].split("_")[0])
    if codigo:
        return codigo
    base = clave.split("-")[0]
    if len(base) == 2 and base.isalpha():
        return base  # Whisper admite muchos más idiomas; se pasa tal cual
    raise ErrorUsuario(f"Idioma no reconocido: '{idioma}'. Usa un código como 'es' o 'en-US'.")


def modelo(config: Config):
    clave = (config.whisper_modelo, config.whisper_dispositivo, config.whisper_tipo_computo)
    with _candado:
        if clave not in _modelos:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise ErrorUsuario(
                    "Falta faster-whisper. Instálalo con: uv sync --extra habla"
                ) from e
            _modelos[clave] = WhisperModel(
                config.whisper_modelo,
                device=config.whisper_dispositivo,
                compute_type=config.whisper_tipo_computo,
            )
        return _modelos[clave]


def transcribir(
    y: np.ndarray, config: Config, idioma: str | None = None, conservar_muletillas: bool = False
) -> Transcripcion:
    codigo = codigo_idioma(idioma)
    whisper = modelo(config)
    prompt = PROMPT_MULETILLAS.get(codigo or "") if conservar_muletillas else None
    with _candado:  # una transcripción a la vez: el modelo ya usa todos los núcleos
        segmentos, info = whisper.transcribe(
            y,
            language=codigo,
            word_timestamps=True,
            vad_filter=True,
            initial_prompt=prompt,
            condition_on_previous_text=False,
        )
        resultado = [
            Segmento(
                inicio=s.start,
                fin=s.end,
                texto=s.text.strip(),
                palabras=[
                    Palabra(w.word.strip(), w.start, w.end, w.probability) for w in s.words or []
                ],
            )
            for s in segmentos
        ]
    return Transcripcion(
        idioma=info.language, prob_idioma=info.language_probability, segmentos=resultado
    )
