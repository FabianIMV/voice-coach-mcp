"""Métricas de discurso a partir de la transcripción (palabras con tiempos) y del audio.

Todo aquí es independiente del modelo de transcripción, para poder probarlo con datos falsos.
"""

import re
import tomllib
from collections import Counter
from dataclasses import dataclass
from importlib import resources

import numpy as np

from ..config import SAMPLE_RATE, Config
from ..errores import ErrorUsuario
from .transcripcion import Palabra, Transcripcion

UMBRAL_PAUSA_S = 0.7
PAUSA_AISLAMIENTO_S = 0.3  # una muletilla ambigua cuenta si la rodea una pausa así
MONOTONO_ST = 2.0  # desviación estándar del tono (semitonos) por debajo de la cual es monótono
VENTANA_TONO_S, PASO_TONO_S = 8.0, 4.0
VOLUMEN_PLANO_DB = 3.0  # desviación entre palabras por debajo de la cual el volumen es plano
_PUNTUACION = ".,;:!?¿¡…\"'«»()[]-–—"


# --- Ritmo y pausas ------------------------------------------------------------------------


def ritmo(palabras: list[Palabra], pausas: list[dict]) -> dict:
    if not palabras:
        return {"palabras": 0}
    tiempo_habla = palabras[-1].fin - palabras[0].inicio
    sin_pausas = tiempo_habla - sum(p["dur"] for p in pausas)
    datos = {"palabras": len(palabras), "tiempo_habla_s": round(tiempo_habla, 1)}
    if tiempo_habla > 0:
        datos["palabras_por_minuto"] = round(60 * len(palabras) / tiempo_habla)
    if sin_pausas > 0:
        datos["ppm_sin_pausas_largas"] = round(60 * len(palabras) / sin_pausas)
    return datos


def pausas(
    palabras: list[Palabra],
    umbral: float = UMBRAL_PAUSA_S,
    y: np.ndarray | None = None,
    sr: int = SAMPLE_RATE,
) -> list[dict]:
    """Silencios de al menos `umbral` segundos entre la primera y la última palabra.

    Con el audio, los silencios se miden por energía: Whisper tiende a estirar el final de las
    palabras dentro del silencio, así que sus huecos subestiman las pausas. Sin audio se usan
    los huecos entre palabras.
    """
    if len(palabras) < 2:
        return []
    if y is None:
        tramos = [(a.fin, b.inicio) for a, b in zip(palabras, palabras[1:], strict=False)]
    else:
        tramos = _silencios(y, sr, palabras[0].inicio, palabras[-1].fin)
    lista = []
    for inicio, fin in tramos:
        if fin - inicio < umbral:
            continue
        previas = [p for p in palabras if p.inicio < inicio]
        tras = previas[-1].texto.strip(_PUNTUACION) if previas else ""
        lista.append({"t": round(inicio, 2), "dur": round(fin - inicio, 2), "tras": tras})
    return lista


def _silencios(y: np.ndarray, sr: int, desde: float, hasta: float) -> list[tuple[float, float]]:
    hop, frame = int(0.01 * sr), int(0.03 * sr)
    if len(y) < frame:
        return []
    ventanas = np.lib.stride_tricks.sliding_window_view(y, frame)[::hop]
    db = 10 * np.log10(np.maximum(np.mean(ventanas**2, axis=1), 1e-12))
    p10, p95 = np.percentile(db, [10, 95])
    umbral_db = max(p10 + 6, p95 - 35)
    i0, i1 = int(desde * sr / hop), int(np.ceil(hasta * sr / hop))
    silencio = db[i0:i1] < umbral_db
    bordes = np.diff(np.concatenate([[0], silencio.astype(int), [0]]))
    return [
        ((i0 + a) * hop / sr + frame / (2 * sr), (i0 + b) * hop / sr + frame / (2 * sr))
        for a, b in zip(np.flatnonzero(bordes == 1), np.flatnonzero(bordes == -1), strict=True)
    ]


def resumen_pausas(lista: list[dict], minutos: float, umbral: float) -> dict:
    datos: dict = {"umbral_s": umbral, "cantidad": len(lista)}
    if lista:
        datos["total_s"] = round(sum(p["dur"] for p in lista), 1)
        datos["max_s"] = max(p["dur"] for p in lista)
    if minutos > 0:
        datos["por_minuto"] = round(len(lista) / minutos, 1)
    datos["lista"] = lista
    return datos


# --- Muletillas ----------------------------------------------------------------------------


@dataclass
class ListasMuletillas:
    vocalizaciones: list[re.Pattern]
    expresiones: list[tuple[list[str], bool]]  # (tokens normalizados, exige "?")
    ambiguas: set[str]


def normalizar(texto: str) -> str:
    return texto.lower().strip().strip(_PUNTUACION).strip()


def cargar_listas(config: Config, idioma: str) -> ListasMuletillas | None:
    base = tomllib.loads(
        resources.files(__package__).joinpath("muletillas.toml").read_text("utf-8")
    )
    if config.muletillas:
        try:
            base.update(tomllib.loads(config.muletillas.read_text("utf-8")))
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise ErrorUsuario(
                f"No pude leer VOICE_COACH_MULETILLAS ({config.muletillas}): {e}"
            ) from e
    seccion = base.get(idioma)
    if not seccion:
        return None
    return ListasMuletillas(
        vocalizaciones=[re.compile(p) for p in seccion.get("vocalizaciones", [])],
        expresiones=[
            ([normalizar(t) for t in e.split()], "?" in e) for e in seccion.get("expresiones", [])
        ],
        ambiguas={normalizar(a) for a in seccion.get("ambiguas", [])},
    )


def muletillas(transcripcion: Transcripcion, listas: ListasMuletillas, minutos: float) -> dict:
    ocurrencias = []
    for segmento in transcripcion.segmentos:
        palabras = segmento.palabras
        normas = [normalizar(p.texto) for p in palabras]
        usadas: set[int] = set()
        for i, palabra in enumerate(palabras):
            if i in usadas or not normas[i]:
                continue
            encontrada = _expresion(palabras, normas, i, listas)
            if encontrada:
                n, texto = encontrada
                usadas.update(range(i, i + n))
            elif any(p.fullmatch(normas[i]) for p in listas.vocalizaciones):
                texto = normas[i]
            elif normas[i] in listas.ambiguas and _aislada(palabras, i):
                texto = normas[i]
            else:
                continue
            ocurrencias.append({"t": round(palabra.inicio, 2), "texto": texto})

    por_tipo = Counter(_tipo(o["texto"], listas) for o in ocurrencias)
    datos: dict = {"total": len(ocurrencias)}
    if minutos > 0:
        datos["por_minuto"] = round(len(ocurrencias) / minutos, 1)
    datos["por_tipo"] = dict(por_tipo.most_common())
    datos["ocurrencias"] = ocurrencias
    return datos


def _tipo(texto: str, listas: ListasMuletillas) -> str:
    """Agrupa variantes de vocalizaciones ("ehh", "eeh") bajo un mismo patrón."""
    for patron in listas.vocalizaciones:
        if patron.fullmatch(texto):
            compacto = re.sub(r"(.)\1+", r"\1", texto)
            return compacto * 3 if len(compacto) == 1 else compacto  # "mmmm" → "mmm"
    return texto


def _expresion(palabras: list[Palabra], normas: list[str], i: int, listas: ListasMuletillas):
    for tokens, pregunta in listas.expresiones:
        n = len(tokens)
        if normas[i : i + n] != tokens:
            continue
        if pregunta and "?" not in palabras[i + n - 1].texto:
            continue
        return n, " ".join(tokens) + ("?" if pregunta else "")
    return None


def _aislada(palabras: list[Palabra], i: int) -> bool:
    palabra = palabras[i]
    if i == 0 or palabra.texto.rstrip().endswith((",", "...", "…")):
        return True
    anterior = palabras[i - 1]
    if anterior.texto.rstrip().endswith((",", ".", "...", "…")):
        return True
    if palabra.inicio - anterior.fin >= PAUSA_AISLAMIENTO_S:
        return True
    return i + 1 < len(palabras) and palabras[i + 1].inicio - palabra.fin >= PAUSA_AISLAMIENTO_S


# --- Tono y volumen ------------------------------------------------------------------------


def _mascara_habla(n_frames: int, palabras: list[Palabra], fps: float) -> np.ndarray:
    mascara = np.zeros(n_frames, dtype=bool)
    for p in palabras:
        mascara[int(p.inicio * fps) : int(np.ceil(p.fin * fps))] = True
    return mascara


def tono(y: np.ndarray, palabras: list[Palabra], sr: int = SAMPLE_RATE) -> dict:
    """Variación de la frecuencia fundamental durante el habla, en semitonos."""
    import librosa

    hop = 160
    f0, voz, _ = librosa.pyin(y, fmin=60, fmax=500, sr=sr, frame_length=1024, hop_length=hop)
    fps = sr / hop
    valido = voz & np.isfinite(f0) & _mascara_habla(len(f0), palabras, fps)
    if valido.sum() < fps:  # menos de 1 s con voz
        return {"frames_con_voz_s": round(valido.sum() / fps, 1)}
    mediana = float(np.median(f0[valido]))
    st = np.full(len(f0), np.nan)
    st[valido] = 12 * np.log2(f0[valido] / mediana)
    desv = float(np.nanstd(st))
    p10, p90 = np.nanpercentile(st, [10, 90])
    return {
        "f0_mediana_hz": round(mediana),
        "desv_semitonos": round(desv, 2),
        "rango_p10_p90_semitonos": round(float(p90 - p10), 1),
        "monotono": desv < MONOTONO_ST,
        "tramos_monotonos": _tramos_monotonos(st, fps),
    }


def _tramos_monotonos(st: np.ndarray, fps: float) -> list[dict]:
    ventana, paso = int(VENTANA_TONO_S * fps), int(PASO_TONO_S * fps)
    tramos: list[dict] = []
    for inicio in range(0, max(1, len(st) - ventana + 1), paso):
        trozo = st[inicio : inicio + ventana]
        if np.sum(np.isfinite(trozo)) < fps or np.nanstd(trozo) >= MONOTONO_ST:
            continue
        t0, t1 = inicio / fps, min(len(st), inicio + ventana) / fps
        if tramos and t0 <= tramos[-1]["fin"]:
            tramos[-1]["fin"] = round(t1, 1)
        else:
            tramos.append({"t": round(t0, 1), "fin": round(t1, 1)})
    return tramos


def volumen(y: np.ndarray, palabras: list[Palabra], sr: int = SAMPLE_RATE) -> dict:
    """Nivel por palabra (dBFS) y cuánto varía entre palabras."""
    niveles = []
    for p in palabras:
        trozo = y[int(p.inicio * sr) : int(p.fin * sr)]
        if len(trozo):
            niveles.append(10 * np.log10(max(float(np.mean(trozo**2)), 1e-12)))
    if len(niveles) < 3:
        return {}
    niveles = np.array(niveles)
    desv = float(np.std(niveles))
    p10, p90 = np.percentile(niveles, [10, 90])
    return {
        "media_dbfs": round(float(np.mean(niveles)), 1),
        "desv_entre_palabras_db": round(desv, 1),
        "rango_p10_p90_db": round(float(p90 - p10), 1),
        "variacion_baja": desv < VOLUMEN_PLANO_DB,
    }
