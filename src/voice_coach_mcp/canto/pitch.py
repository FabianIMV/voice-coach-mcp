"""Extracción del contorno de pitch y segmentación en notas.

pYIN decide qué frames tienen voz y da una altura gruesa (bins de 10 cents). Luego cada frame
con voz se refina midiendo sus armónicos en un espectro con zero-padding e interpolación
parabólica, lo que da precisión de ~1 cent en todo el registro.
"""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d
from scipy.signal import find_peaks

from ..config import SAMPLE_RATE
from .teoria import hz_a_midi

HOP = 160  # 10 ms a 16 kHz
FRAME = 1024
VENTANA_FINA = 1024
NFFT_FINO = 8192
ARMONICOS = 8
FMIN, FMAX = 65.4, 1046.5  # C2–C6
DURACION_MIN_NOTA = 0.08
# La ventana de análisis hace que la voz "aparezca" antes y "termine" después de lo real.
BORDE_S = FRAME / 4 / SAMPLE_RATE
SALTO_NOTA = 0.5  # semitonos sostenidos durante...
SALTO_MIN_S = 0.06  # ...este tiempo para considerar una nota nueva
VENTANA_SUAVE_S = 0.2  # ~1 ciclo de vibrato: el suavizado lo anula para segmentar
PROB_VOZ_MIN = 0.2  # notas con menos probabilidad media de voz se descartan (ruido)
ENERGIA_RELATIVA_MIN_DB = -35.0  # respecto de las partes más fuertes del audio
CAIDA_ENERGIA_DB = 9.0  # una caída así entre dos notas iguales (consonante, respiro) separa notas
VIBRATO_HZ = (4.0, 8.0)
ESTABLE_MAX_CENTS = 15.0


@dataclass
class Contorno:
    midi: np.ndarray  # altura en MIDI fraccional; nan sin voz
    prob_voz: np.ndarray
    energia_db: np.ndarray
    sr: int = SAMPLE_RATE
    hop: int = HOP

    @property
    def fps(self) -> float:
        return self.sr / self.hop

    def tiempo(self, frame: int) -> float:
        return frame / self.fps


@dataclass
class Nota:
    inicio: float
    fin: float
    midi: float  # altura representativa (mediana de la parte central)
    desv_std_cents: float
    estabilidad: str  # "estable" | "vibrato" | "inestable"
    deriva_cents: float
    vibrato_hz: float | None = None
    vibrato_pp_cents: float | None = None
    prob_voz: float = 1.0

    @property
    def duracion(self) -> float:
        return self.fin - self.inicio


def extraer_contorno(y: np.ndarray, sr: int = SAMPLE_RATE, a4: float = 440.0) -> Contorno:
    import librosa

    if len(y) < FRAME:
        y = np.pad(y, (0, FRAME - len(y)))
    f0, voz, prob = librosa.pyin(
        y, fmin=FMIN, fmax=FMAX, sr=sr, frame_length=FRAME, hop_length=HOP, resolution=0.1
    )
    f0 = np.where(voz, f0, np.nan)
    fino = _refinar_hz(y, sr, f0)
    grueso = hz_a_midi(f0, a4)
    refinado = hz_a_midi(fino, a4)
    # El refinamiento solo se acepta si coincide con pYIN (evita saltos de armónico).
    midi = np.where(np.abs(refinado - grueso) < 0.5, refinado, grueso)
    rms = librosa.feature.rms(y=y, frame_length=2 * HOP, hop_length=HOP)[0]
    energia = 20 * np.log10(np.maximum(np.pad(rms, (0, max(0, len(midi) - len(rms)))), 1e-5))
    return Contorno(midi=midi, prob_voz=prob, energia_db=energia[: len(midi)], sr=sr)


def _refinar_hz(y: np.ndarray, sr: int, f0: np.ndarray) -> np.ndarray:
    """Frecuencia fundamental fina por frame, a partir de los picos de sus armónicos."""
    fino = np.full(len(f0), np.nan)
    frames = np.flatnonzero(np.isfinite(f0))
    if len(frames) == 0:
        return fino
    medio = VENTANA_FINA // 2
    relleno = np.pad(y, medio)
    ventana = np.hanning(VENTANA_FINA)
    bin_hz = sr / NFFT_FINO
    for lote in np.array_split(frames, max(1, len(frames) // 256)):
        segmentos = np.stack([relleno[f * HOP : f * HOP + VENTANA_FINA] for f in lote]) * ventana
        magnitud = np.abs(np.fft.rfft(segmentos, NFFT_FINO, axis=1)) + 1e-12
        log_mag = np.log(magnitud)
        for k, frame in enumerate(lote):
            estimaciones, pesos = [], []
            for h in range(1, ARMONICOS + 1):
                centro = h * f0[frame] / bin_hz
                if centro * 1.03 >= NFFT_FINO // 2 - 1:
                    break
                lo, hi = int(centro * 0.97), int(np.ceil(centro * 1.03)) + 1
                j = lo + int(np.argmax(log_mag[k, lo:hi]))
                if j in (lo, hi - 1):  # sin máximo local en la ventana de búsqueda
                    continue
                a, b, c = log_mag[k, j - 1 : j + 2]
                curvatura = a - 2 * b + c
                delta = 0.5 * (a - c) / curvatura if curvatura < 0 else 0.0
                estimaciones.append((j + delta) * bin_hz / h)
                pesos.append(magnitud[k, j])
            if estimaciones:
                fino[frame] = np.average(estimaciones, weights=pesos)
    return fino


def _tramos(mascara: np.ndarray) -> list[tuple[int, int]]:
    """Intervalos [inicio, fin) donde la máscara es verdadera."""
    bordes = np.diff(np.concatenate([[0], mascara.astype(int), [0]]))
    return list(zip(np.flatnonzero(bordes == 1), np.flatnonzero(bordes == -1), strict=True))


def _subtramos(voz: np.ndarray, energia_db: np.ndarray, min_frames: int) -> list[tuple[int, int]]:
    """Tramos con voz, partidos además en las caídas marcadas de energía (notas repetidas)."""
    tramos = []
    for a, b in _tramos(voz):
        valles, _ = find_peaks(
            -energia_db[a:b], prominence=CAIDA_ENERGIA_DB, distance=max(1, min_frames)
        )
        limites = [a, *(a + v for v in valles), b]
        tramos += list(zip(limites[:-1], limites[1:], strict=True))
    return tramos


def _cortes(suave: np.ndarray, crudo: np.ndarray, min_frames: int) -> list[int]:
    """Puntos de cambio de nota dentro de un tramo con voz."""
    cortes, ref, inicio_nota, fuera = [], suave[0], 0, 0
    for i in range(1, len(suave)):
        if abs(suave[i] - ref) > SALTO_NOTA:
            fuera += 1
            if fuera >= min_frames:
                candidato = i - fuera + 1
                cortes.append(_refinar_corte(crudo, candidato, inicio_nota, ref, suave[i]))
                inicio_nota, ref, fuera = cortes[-1], suave[i], 0
        else:
            fuera = 0
            ref = np.median(suave[inicio_nota : i + 1])
    return cortes


def _refinar_corte(
    crudo: np.ndarray, candidato: int, minimo: int, antes: float, despues: float
) -> int:
    """Ubica el cambio donde el contorno crudo cruza el punto medio entre ambas notas."""
    medio = (antes + despues) / 2
    signo = np.sign(despues - antes)
    radio = 15
    for i in range(max(minimo + 1, candidato - radio), min(len(crudo), candidato + radio)):
        if signo * (crudo[i] - medio) > 0:
            return i
    return candidato


def _estadisticas(cents: np.ndarray, fps: float) -> dict:
    """Estabilidad sobre el contorno (en cents) de la parte central de una nota."""
    t = np.arange(len(cents)) / fps
    pendiente, origen = np.polyfit(t, cents, 1) if len(cents) > 2 else (0.0, float(np.mean(cents)))
    residuo = cents - (pendiente * t + origen)
    std = float(np.std(residuo))
    datos = {"std": std, "deriva": float(pendiente * t[-1]) if len(t) else 0.0, "estabilidad": None}

    if len(cents) / fps >= 0.3 and std > 5:
        n_fft = max(1024, len(residuo))
        potencia = np.abs(np.fft.rfft(residuo * np.hanning(len(residuo)), n_fft)) ** 2
        freqs = np.fft.rfftfreq(n_fft, 1 / fps)
        banda = (freqs >= VIBRATO_HZ[0]) & (freqs <= VIBRATO_HZ[1])
        total = potencia[1:].sum()
        if total > 0 and potencia[banda].sum() / total > 0.5:
            pico = freqs[banda][np.argmax(potencia[banda])]
            pp = 2 * np.sqrt(2) * std  # pico a pico de una sinusoide con esa desviación
            if 20 <= pp <= 300:
                datos.update(estabilidad="vibrato", vibrato_hz=float(pico), vibrato_pp=float(pp))
    if datos["estabilidad"] is None:
        datos["estabilidad"] = "estable" if std <= ESTABLE_MAX_CENTS else "inestable"
    return datos


def segmentar(contorno: Contorno) -> list[Nota]:
    fps = contorno.fps
    midi = contorno.midi
    voz = np.isfinite(midi)
    min_frames = max(1, round(SALTO_MIN_S * fps))
    ventana = max(1, round(VENTANA_SUAVE_S * fps))
    notas: list[Nota] = []
    piso_energia = np.percentile(contorno.energia_db, 95) + ENERGIA_RELATIVA_MIN_DB

    for a, b in _subtramos(voz, contorno.energia_db, round(DURACION_MIN_NOTA * fps)):
        crudo = median_filter(midi[a:b], size=5, mode="nearest")
        suave = uniform_filter1d(crudo, size=ventana, mode="nearest")
        limites = [0, *_cortes(suave, crudo, min_frames), b - a]
        for i0, i1 in zip(limites[:-1], limites[1:], strict=True):
            empieza_voz = i0 == 0 and (a == 0 or not voz[a - 1])
            termina_voz = a + i1 == b and (b == len(voz) or not voz[b])
            inicio = contorno.tiempo(a + i0) + (BORDE_S if empieza_voz else 0.0)
            fin = contorno.tiempo(a + i1) - (BORDE_S if termina_voz else 0.0)
            prob = float(np.mean(contorno.prob_voz[a + i0 : a + i1]))
            if (
                fin - inicio < DURACION_MIN_NOTA
                or prob < PROB_VOZ_MIN
                or np.median(contorno.energia_db[a + i0 : a + i1]) < piso_energia
            ):
                continue
            tramo = midi[a + i0 : a + i1]
            n = len(tramo)
            centro = tramo[int(0.2 * n) : max(int(0.2 * n) + 1, int(0.9 * n))]
            altura = float(np.median(centro))
            stats = _estadisticas((centro - altura) * 100, fps)
            notas.append(
                Nota(
                    inicio=inicio,
                    fin=fin,
                    midi=altura,
                    desv_std_cents=stats["std"],
                    estabilidad=stats["estabilidad"],
                    deriva_cents=stats["deriva"],
                    vibrato_hz=stats.get("vibrato_hz"),
                    vibrato_pp_cents=stats.get("vibrato_pp"),
                    prob_voz=prob,
                )
            )
    return notas
