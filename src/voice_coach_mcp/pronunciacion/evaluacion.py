"""Tool evaluar_pronunciacion: elige backend, evalúa y arma la respuesta compacta."""

from collections import Counter

from ..audio import calidad as cal
from ..audio.io import cargar, resolver_ruta
from ..config import Config
from ..errores import ErrorUsuario
from ..salida import Recortable, ajustar
from .base import BackendPronunciacion, ResultadoPalabra


def backend(config: Config) -> BackendPronunciacion:
    if config.pronunciacion_backend == "local":
        from .wav2vec2 import BackendWav2Vec2

        return BackendWav2Vec2()
    if config.pronunciacion_backend == "azure":
        from .azure import BackendAzure

        return BackendAzure()
    raise ErrorUsuario(
        f"VOICE_COACH_PRONUNCIACION_BACKEND='{config.pronunciacion_backend}' no existe; usa 'local' o 'azure'."
    )


def _item(r: ResultadoPalabra) -> dict:
    item: dict = {"palabra": r.palabra, "puntaje": round(r.puntaje)}
    if r.inicio is not None:
        item["t"] = r.inicio
    if r.omitida:
        item["omitida"] = True
    elif r.errores:
        item["esperado"] = " ".join(r.esperados)
        item["detectado"] = " ".join(r.detectados)
        item["errores"] = [e.a_dict() for e in r.errores]
    return item


def evaluar(audio: str, texto_esperado: str, config: Config, idioma: str = "en-US") -> str:
    ruta = resolver_ruta(audio, config)
    y = cargar(ruta)
    calidad = cal.evaluar(y, duracion_minima=0.5)
    resultado: dict = {"audio": str(ruta), "duracion_s": calidad.duracion_s, "idioma": idioma}
    advertencias = list(calidad.advertencias)
    confianza = 0.0
    if calidad.factor > 0:
        motor = backend(config)
        r = motor.evaluar(y, texto_esperado, idioma, config)
        advertencias += r.advertencias
        conteo = Counter(e.tipo for p in r.palabras for e in p.errores)
        confusiones = Counter(
            (e.esperado, e.detectado)
            for p in r.palabras
            for e in p.errores
            if e.tipo == "sustitucion" and e.esperado and e.detectado
        )
        resultado["backend"] = r.backend
        resultado["resumen"] = {
            "puntaje_global": round(r.puntaje_global),
            "palabras": len(r.palabras),
            "palabras_con_errores": sum(bool(p.errores) for p in r.palabras),
            "errores": {t: conteo.get(t, 0) for t in ("sustitucion", "omision", "insercion")},
            "confusiones_frecuentes": [
                {"esperado": a, "detectado": b, "veces": n}
                for (a, b), n in confusiones.most_common(5)
            ],
            **r.extra,
        }
        resultado["palabras"] = [_item(p) for p in r.palabras]
        resultado["fonemas"] = {
            "esperados": " ".join(r.fonemas_esperados),
            "detectados": " ".join(r.fonemas_detectados),
        }
        confianza = calidad.factor * min(1.0, r.confianza_modelo / 0.8)
        if r.distancia_relativa > 0.6:
            confianza *= 0.3
    resultado["confianza"] = cal.nivel_confianza(confianza)
    resultado["advertencias"] = advertencias
    return ajustar(
        resultado,
        audio=ruta,
        tool="pronunciacion",
        config=config,
        recortables=[
            "fonemas.detectados",
            "fonemas.esperados",
            Recortable("palabras", lambda p: 100 - p["puntaje"]),
        ],
    )
