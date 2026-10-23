"""Análisis de afinación: notas cantadas vs. temperamento, tonalidad o una melodía MIDI."""

from dataclasses import dataclass

import numpy as np

from ..audio import calidad as cal
from ..audio.io import cargar, resolver_ruta
from ..config import Config
from ..salida import Recortable, ajustar
from .pitch import Contorno, Nota, extraer_contorno, segmentar
from .referencia import Melodia, NotaRef, cargar_melodia
from .teoria import nombre_nota, nota_objetivo, parsear_tonalidad

TOLERANCIA_CENTS = 25
TENDENCIA_CENTS = 10
INCORRECTA_CENTS = 50
ENTRADA_TOLERANCIA_MS = 80
OCTAVAS = (0, -1, 1, -2, 2)  # en orden de preferencia ante empates
COSTO_OMITIDA = 2.0
COSTO_EXTRA = 1.5


def analizar(
    audio: str,
    config: Config,
    referencia_midi: str | None = None,
    tonalidad: str | None = None,
    pista_midi: int | None = None,
) -> str:
    ruta = resolver_ruta(audio, config)
    y = cargar(ruta)
    calidad = cal.evaluar(y, duracion_minima=1.0)
    advertencias = list(calidad.advertencias)
    resultado: dict = {"audio": str(ruta), "duracion_s": calidad.duracion_s}

    escala, nombre_tonalidad = None, None
    if tonalidad and referencia_midi:
        advertencias.append(
            cal.advertencia(
                "tonalidad_ignorada", "Con referencia MIDI se usa la melodía, no la tonalidad."
            )
        )
    elif tonalidad:
        escala, nombre_tonalidad = parsear_tonalidad(tonalidad)
    melodia = (
        cargar_melodia(resolver_ruta(referencia_midi, config), pista_midi)
        if referencia_midi
        else None
    )

    contorno = extraer_contorno(y, a4=config.a4_hz) if calidad.factor > 0 else None
    notas = segmentar(contorno) if contorno is not None else []

    if melodia:
        resultado["modo"] = "referencia_midi"
        resumen, items, factor_alineacion, adv = _con_referencia(notas, contorno, melodia)
        advertencias += adv
    else:
        resultado["modo"] = "tonalidad" if escala else "temperado"
        if nombre_tonalidad:
            resultado["tonalidad"] = nombre_tonalidad
        resumen, items = _sin_referencia(notas, escala)
        factor_alineacion = 1.0

    confianza = calidad.factor * factor_alineacion * _factor_voz(notas)
    if contorno is not None:
        voz = float(np.mean(np.isfinite(contorno.midi)))
        if voz < 0.2 and calidad.duracion_s > 2:
            advertencias.append(
                cal.advertencia(
                    "poca_voz", f"Solo {voz:.0%} del audio tiene voz con altura definida."
                )
            )
    if len(notas) < 2 and calidad.factor > 0:
        advertencias.append(
            cal.advertencia("pocas_notas_detectadas", f"Se detectaron {len(notas)} notas.")
        )
        confianza *= 0.5

    resultado["resumen"] = resumen
    resultado["notas"] = items
    resultado["confianza"] = cal.nivel_confianza(confianza)
    resultado["advertencias"] = advertencias
    return ajustar(
        resultado,
        audio=ruta,
        tool="afinacion",
        config=config,
        recortables=[Recortable("notas", _prioridad)],
    )


def _prioridad(item: dict) -> float:
    if item.get("estado") == "omitida" or item.get("nota_incorrecta"):
        return 1000.0
    if item.get("estado") == "extra":
        return 60.0
    extra = 50.0 if item.get("entrada", "a_tiempo") != "a_tiempo" else 0.0
    extra += 30.0 if item.get("estabilidad") == "inestable" else 0.0
    return abs(item.get("cents", 0)) + extra


def _factor_voz(notas: list[Nota]) -> float:
    if not notas:
        return 0.0
    duraciones = np.array([n.duracion for n in notas])
    prob = float(np.average([n.prob_voz for n in notas], weights=duraciones))
    return min(1.0, prob / 0.7)


def _item_nota(nota: Nota, objetivo: int, clave_nota: str = "nota") -> dict:
    item = {
        "t": round(nota.inicio, 2),
        "dur": round(nota.duracion, 2),
        clave_nota: nombre_nota(objetivo),
        "cents": int(round(100 * (nota.midi - objetivo))),
        "estabilidad": nota.estabilidad,
    }
    if nota.estabilidad == "vibrato":
        item["vibrato_hz"] = round(nota.vibrato_hz, 1)
        item["vibrato_pp_cents"] = int(round(nota.vibrato_pp_cents))
    elif nota.estabilidad == "inestable":
        item["desv_cents"] = int(round(nota.desv_std_cents))
    if abs(nota.deriva_cents) >= 15:
        item["deriva_cents"] = int(round(nota.deriva_cents))
    return item


def _resumen_base(
    cents: list[float], duraciones: list[float], tiempos: list[float], notas: list[Nota]
) -> dict:
    resumen: dict = {"notas": len(notas)}
    if not notas:
        return resumen
    c = np.array(cents, dtype=float)
    w = np.array(duraciones, dtype=float)
    media = float(np.average(c, weights=w))
    resumen["rango"] = (
        f"{nombre_nota(round(min(n.midi for n in notas)))}–{nombre_nota(round(max(n.midi for n in notas)))}"
    )
    resumen["porcentaje_dentro_25_cents"] = round(
        100 * float(np.mean(np.abs(c) <= TOLERANCIA_CENTS)), 1
    )
    resumen["desviacion_media_cents"] = round(media, 1)
    resumen["desviacion_abs_media_cents"] = round(float(np.average(np.abs(c), weights=w)), 1)
    resumen["tendencia"] = (
        "sostenido"
        if media > TENDENCIA_CENTS
        else "plano"
        if media < -TENDENCIA_CENTS
        else "centrado"
    )
    if len(c) >= 4:
        orden = np.argsort(tiempos)
        mitad = len(orden) // 2
        resumen["deriva_cents"] = round(
            float(np.mean(c[orden[mitad:]]) - np.mean(c[orden[:mitad]])), 1
        )
    resumen["estabilidad"] = {
        e: sum(n.estabilidad == e for n in notas) for e in ("estable", "vibrato", "inestable")
    }
    return resumen


def _sin_referencia(notas: list[Nota], escala: frozenset[int] | None) -> tuple[dict, list[dict]]:
    items, cents = [], []
    for nota in notas:
        item = _item_nota(nota, nota_objetivo(nota.midi, escala))
        items.append(item)
        cents.append(item["cents"])
    resumen = _resumen_base(cents, [n.duracion for n in notas], [n.inicio for n in notas], notas)
    return resumen, items


# --- Con referencia MIDI -------------------------------------------------------------------


@dataclass
class _Alineacion:
    pares: list[tuple[int | None, int | None]]  # (índice cantada, índice referencia)
    escala_t: float  # tiempo_cantado ≈ escala_t * tiempo_ref + desfase
    desfase: float


def _desfase_inicial(contorno: Contorno, melodia: Melodia) -> tuple[int, float, float]:
    """Octava y desfase temporal que mejor superponen el contorno cantado sobre la referencia."""
    fps = contorno.fps
    cantado = contorno.midi
    fin_ref = int(np.ceil(melodia.notas[-1].fin * fps)) + 1
    ref = np.full(fin_ref, np.nan)
    for n in melodia.notas:
        ref[int(n.inicio * fps) : int(n.fin * fps)] = n.midi
    frames_ref = max(1, int(np.sum(np.isfinite(ref))))

    max_atraso = len(cantado)
    max_adelanto = int(min(5.0 * fps, fin_ref))
    mejor = (0, 0.0, -1.0)
    for octava in OCTAVAS:
        r = ref + 12 * octava
        for d in range(-max_adelanto, max_atraso, 2):
            # el frame t de la referencia se compara con el frame t + d de la grabación
            ini_ref, ini_c = max(0, -d), max(0, d)
            n = min(len(r) - ini_ref, len(cantado) - ini_c)
            if n <= 0:
                continue
            dif = np.abs(cantado[ini_c : ini_c + n] - r[ini_ref : ini_ref + n])
            puntaje = float(np.sum(dif < 1.0)) / frames_ref
            if puntaje > mejor[2] + 1e-9:
                mejor = (octava, d / fps, puntaje)
    return mejor


def _alinear(
    notas: list[Nota], ref: list[NotaRef], escala_t: float, desfase: float
) -> list[tuple[int | None, int | None]]:
    """Needleman-Wunsch entre notas cantadas y de referencia (altura + tiempo de entrada)."""
    n, m = len(notas), len(ref)
    costo = np.zeros((n + 1, m + 1))
    costo[1:, 0] = np.arange(1, n + 1) * COSTO_EXTRA
    costo[0, 1:] = np.arange(1, m + 1) * COSTO_OMITIDA
    paso = np.zeros((n + 1, m + 1), dtype=np.int8)  # 0 diagonal, 1 extra, 2 omitida
    paso[1:, 0], paso[0, 1:] = 1, 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s, r = notas[i - 1], ref[j - 1]
            dt = abs(s.inicio - (escala_t * r.inicio + desfase))
            match = min(abs(s.midi - r.midi), 3.0) + 0.5 * min(dt / 0.3, 4.0)
            opciones = (
                costo[i - 1, j - 1] + match,
                costo[i - 1, j] + COSTO_EXTRA,
                costo[i, j - 1] + COSTO_OMITIDA,
            )
            paso[i, j] = int(np.argmin(opciones))
            costo[i, j] = opciones[paso[i, j]]
    pares: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if paso[i, j] == 0:
            pares.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif paso[i, j] == 1:
            pares.append((i - 1, None))
            i -= 1
        else:
            pares.append((None, j - 1))
            j -= 1
    return pares[::-1]


def _ajustar_tiempo(
    pares, notas: list[Nota], ref: list[NotaRef], escala_t: float, desfase: float
) -> tuple[float, float]:
    """Recta tiempo_cantado = a·tiempo_ref + b sobre los pares con la altura correcta."""
    buenos = [
        (ref[j].inicio, notas[i].inicio)
        for i, j in pares
        if i is not None and j is not None and abs(notas[i].midi - ref[j].midi) < 1.0
    ]
    if len(buenos) >= 3:
        x, yv = np.array(buenos).T
        if np.ptp(x) > 0:
            a, b = np.polyfit(x, yv, 1)
            if 0.5 < a < 2.0:
                return float(a), float(b)
    if buenos:
        return escala_t, float(np.median([t_c - escala_t * t_r for t_r, t_c in buenos]))
    return escala_t, desfase


def _con_referencia(notas: list[Nota], contorno: Contorno | None, melodia: Melodia):
    adv = []
    if melodia.era_polifonica:
        adv.append(
            cal.advertencia(
                "referencia_polifonica",
                f"La pista {melodia.pista} tiene acordes; se usó la línea superior.",
            )
        )
    if not notas or contorno is None:
        return (
            {"notas": 0, "notas_referencia": len(melodia.notas), "pista_midi": melodia.pista},
            [],
            0.0,
            adv,
        )

    octava, desfase, puntaje = _desfase_inicial(contorno, melodia)
    ref = [NotaRef(n.inicio, n.fin, n.midi + 12 * octava) for n in melodia.notas]
    escala_t = 1.0
    for _ in range(2):
        pares = _alinear(notas, ref, escala_t, desfase)
        escala_t, desfase = _ajustar_tiempo(pares, notas, ref, escala_t, desfase)

    items, cents, duraciones, tiempos, cantadas = [], [], [], [], []
    entradas = {"a_tiempo": 0, "tarde": 0, "temprano": 0}
    omitidas = extra = incorrectas = 0
    for i, j in pares:
        if j is None:
            extra += 1
            nota = notas[i]
            items.append(
                {
                    "t": round(nota.inicio, 2),
                    "dur": round(nota.duracion, 2),
                    "cantada": nombre_nota(round(nota.midi)),
                    "estado": "extra",
                }
            )
            continue
        r = ref[j]
        if i is None:
            omitidas += 1
            items.append(
                {
                    "t_ref": round(escala_t * r.inicio + desfase, 2),
                    "esperada": nombre_nota(r.midi),
                    "estado": "omitida",
                }
            )
            continue
        nota = notas[i]
        item = _item_nota(nota, r.midi, clave_nota="esperada")
        cantada = round(nota.midi)
        if cantada != r.midi:
            item["cantada"] = nombre_nota(cantada)
        if abs(item["cents"]) > INCORRECTA_CENTS:
            item["nota_incorrecta"] = True
            incorrectas += 1
        entrada_ms = int(round(1000 * (nota.inicio - (escala_t * r.inicio + desfase))))
        item["entrada_ms"] = entrada_ms
        item["entrada"] = (
            "tarde"
            if entrada_ms > ENTRADA_TOLERANCIA_MS
            else "temprano"
            if entrada_ms < -ENTRADA_TOLERANCIA_MS
            else "a_tiempo"
        )
        entradas[item["entrada"]] += 1
        items.append(item)
        cents.append(item["cents"])
        duraciones.append(nota.duracion)
        tiempos.append(nota.inicio)
        cantadas.append(nota)

    resumen = _resumen_base(cents, duraciones, tiempos, cantadas)
    resumen.update(
        {
            "notas_referencia": len(ref),
            "omitidas": omitidas,
            "notas_extra": extra,
            "notas_incorrectas": incorrectas,
            "entradas": entradas,
            "transposicion_octavas": octava,
            "desfase_inicio_ms": int(round(1000 * desfase)),
            "tempo_relativo": round(escala_t, 3),
            "pista_midi": melodia.pista,
        }
    )
    if puntaje < 0.3:
        adv.append(
            cal.advertencia(
                "alineacion_debil", f"Solo {puntaje:.0%} de la referencia coincide con lo cantado."
            )
        )
    factor = (0.5 + 0.5 * len(cantadas) / len(ref)) * min(1.0, 0.5 + puntaje)
    return resumen, items, factor, adv
