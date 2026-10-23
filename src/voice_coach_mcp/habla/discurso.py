"""Tools de habla: transcribir y metricas_discurso."""

import numpy as np

from ..audio import calidad as cal
from ..audio.io import cargar, resolver_ruta
from ..config import Config
from ..salida import Recortable, ajustar
from . import metricas
from .transcripcion import Transcripcion, codigo_idioma, transcribir

DURACION_MIN_DISCURSO_S = 5.0


def _segmentos(t: Transcripcion) -> list[dict]:
    return [
        {"t": round(s.inicio, 2), "fin": round(s.fin, 2), "texto": s.texto} for s in t.segmentos
    ]


def _confianza_y_avisos(t: Transcripcion, idioma_pedido: str | None, factor_calidad: float):
    advertencias = []
    palabras = t.palabras
    if not palabras:
        advertencias.append(cal.advertencia("sin_habla", "No se detectó habla en el audio."))
        return 0.0, advertencias
    prob = float(np.mean([p.prob for p in palabras]))
    confianza = factor_calidad * min(1.0, prob / 0.85)
    if prob < 0.6:
        advertencias.append(
            cal.advertencia("transcripcion_dudosa", f"Probabilidad media por palabra {prob:.2f}.")
        )
    if idioma_pedido is None and t.prob_idioma < 0.6:
        advertencias.append(
            cal.advertencia(
                "idioma_incierto",
                f"Idioma detectado '{t.idioma}' con probabilidad {t.prob_idioma:.2f}.",
            )
        )
        confianza *= 0.7
    return confianza, advertencias


def analizar_transcripcion(audio: str, config: Config, idioma: str | None = None) -> str:
    ruta = resolver_ruta(audio, config)
    y = cargar(ruta)
    calidad = cal.evaluar(y, duracion_minima=1.0)
    resultado: dict = {"audio": str(ruta), "duracion_s": calidad.duracion_s}
    advertencias = list(calidad.advertencias)
    confianza = 0.0
    if calidad.factor > 0:
        t = transcribir(y, config, idioma)
        confianza, avisos = _confianza_y_avisos(t, codigo_idioma(idioma), calidad.factor)
        advertencias += avisos
        resultado |= {
            "idioma": t.idioma,
            "prob_idioma": round(t.prob_idioma, 2),
            "texto": t.texto,
            "segmentos": _segmentos(t),
            "palabras": [
                {"p": p.texto, "t": round(p.inicio, 2), "fin": round(p.fin, 2)} for p in t.palabras
            ],
        }
    resultado["confianza"] = cal.nivel_confianza(confianza)
    resultado["advertencias"] = advertencias
    return ajustar(
        resultado,
        audio=ruta,
        tool="transcripcion",
        config=config,
        recortables=[Recortable("palabras"), Recortable("segmentos")],
        textos=["texto"],
    )


def analizar_discurso(
    audio: str, config: Config, idioma: str, umbral_pausa_s: float = metricas.UMBRAL_PAUSA_S
) -> str:
    ruta = resolver_ruta(audio, config)
    y = cargar(ruta)
    calidad = cal.evaluar(y, duracion_minima=DURACION_MIN_DISCURSO_S)
    codigo = codigo_idioma(idioma)
    resultado: dict = {"audio": str(ruta), "duracion_s": calidad.duracion_s, "idioma": codigo}
    advertencias = list(calidad.advertencias)
    confianza = 0.0

    if calidad.factor > 0:
        t = transcribir(y, config, codigo, conservar_muletillas=True)
        confianza, avisos = _confianza_y_avisos(t, codigo, calidad.factor)
        advertencias += avisos
        palabras = t.palabras
        lista_pausas = metricas.pausas(palabras, umbral_pausa_s, y)
        datos_ritmo = metricas.ritmo(palabras, lista_pausas)
        minutos = datos_ritmo.get("tiempo_habla_s", 0.0) / 60
        resultado["ritmo"] = datos_ritmo
        resultado["pausas"] = metricas.resumen_pausas(lista_pausas, minutos, umbral_pausa_s)
        listas = metricas.cargar_listas(config, codigo)
        if listas:
            resultado["muletillas"] = metricas.muletillas(t, listas, minutos)
        else:
            advertencias.append(
                cal.advertencia(
                    "sin_lista_muletillas", f"No hay lista de muletillas para '{codigo}'."
                )
            )
        if palabras:
            resultado["tono"] = metricas.tono(y, palabras)
            resultado["volumen"] = metricas.volumen(y, palabras)
        resultado["segmentos"] = _segmentos(t)

    resultado["confianza"] = cal.nivel_confianza(confianza)
    resultado["advertencias"] = advertencias
    return ajustar(
        resultado,
        audio=ruta,
        tool="discurso",
        config=config,
        recortables=[
            Recortable("segmentos"),
            Recortable("muletillas.ocurrencias"),
            Recortable("pausas.lista", lambda p: p["dur"]),
            Recortable("tono.tramos_monotonos"),
        ],
    )
