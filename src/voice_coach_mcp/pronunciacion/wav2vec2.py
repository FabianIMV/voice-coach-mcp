"""Backend local: modelo de fonemas wav2vec2 (CTC) + alineación con los fonemas esperados."""

import os
import threading

import numpy as np

from ..audio import calidad as cal
from ..config import SAMPLE_RATE, Config
from ..errores import ErrorUsuario
from . import alineacion, fonemas
from .base import ResultadoPronunciacion

MODELO = "facebook/wav2vec2-lv-60-espeak-cv-ft"
SEGUNDOS_POR_FRAME = 0.02
MAX_SEGUNDOS = 60.0

_cache: dict[str, tuple] = {}
_candado = threading.Lock()


def _dispositivo() -> str:
    import torch

    pedido = os.environ.get("VOICE_COACH_PRONUNCIACION_DEVICE", "auto")
    if pedido != "auto":
        return pedido
    return "mps" if torch.backends.mps.is_available() else "cpu"


def cargar_modelo():
    with _candado:
        if "modelo" not in _cache:
            try:
                from transformers import AutoModelForCTC, AutoProcessor
            except ImportError as e:
                raise ErrorUsuario(
                    "Faltan torch/transformers. Instálalos con: uv sync --extra pronunciacion"
                ) from e
            dispositivo = _dispositivo()
            procesador = AutoProcessor.from_pretrained(MODELO)
            modelo = AutoModelForCTC.from_pretrained(MODELO).eval().to(dispositivo)
            _cache["modelo"] = (procesador, modelo, dispositivo)
        return _cache["modelo"]


def reconocer(y: np.ndarray) -> tuple[list[str], list[float], list[float]]:
    """Decodificación CTC greedy: fonemas, tiempo de inicio y probabilidad media de cada uno."""
    import torch

    procesador, modelo, dispositivo = cargar_modelo()
    entrada = procesador(y, sampling_rate=SAMPLE_RATE, return_tensors="pt").input_values.to(
        dispositivo
    )
    with _candado, torch.no_grad():
        prob = modelo(entrada).logits[0].float().softmax(-1).cpu().numpy()
    ids = prob.argmax(-1)
    tokenizador = procesador.tokenizer
    blanco = tokenizador.pad_token_id
    fonos, tiempos, confianzas = [], [], []
    inicio = 0
    for t in range(1, len(ids) + 1):
        if t < len(ids) and ids[t] == ids[inicio]:
            continue
        if ids[inicio] != blanco:
            fonos.append(tokenizador.convert_ids_to_tokens(int(ids[inicio])))
            tiempos.append(round(inicio * SEGUNDOS_POR_FRAME, 2))
            confianzas.append(float(prob[inicio:t, ids[inicio]].mean()))
        inicio = t
    return fonos, tiempos, confianzas


class BackendWav2Vec2:
    nombre = "wav2vec2-local"

    def evaluar(
        self, y: np.ndarray, texto: str, idioma: str, config: Config
    ) -> ResultadoPronunciacion:
        if len(y) / SAMPLE_RATE > MAX_SEGUNDOS:
            raise ErrorUsuario(
                f"El audio dura más de {MAX_SEGUNDOS:.0f} s; graba frases más cortas."
            )
        palabras = fonemas.palabras_de(texto)
        if not palabras:
            raise ErrorUsuario("texto_esperado no tiene palabras.")
        esperados = fonemas.esperados_por_palabra(palabras, idioma)
        crudos, tiempos_crudos, confianzas = reconocer(y)

        # La normalización puede partir un token en dos; cada parte hereda tiempo y confianza.
        detectados, tiempos = [], []
        for f, t in zip(crudos, tiempos_crudos, strict=True):
            partes = fonemas.normalizar([f])
            detectados += partes
            tiempos += [t] * len(partes)

        plano = [f for fs in esperados for f in fs]
        ops = alineacion.alinear(plano, detectados)
        resultados = alineacion.por_palabra(palabras, esperados, ops, tiempos)
        distancia = alineacion.distancia(ops) / max(1, len(plano))
        advertencias = []
        if distancia > 0.6:
            advertencias.append(
                cal.advertencia(
                    "texto_no_coincide",
                    f"Lo detectado difiere del texto esperado en {distancia:.0%} de los fonemas: ¿se leyó otro texto?",
                )
            )
        return ResultadoPronunciacion(
            backend=self.nombre,
            palabras=resultados,
            puntaje_global=alineacion.puntaje_global(resultados),
            confianza_modelo=float(np.mean(confianzas)) if confianzas else 0.0,
            distancia_relativa=distancia,
            fonemas_esperados=plano,
            fonemas_detectados=detectados,
            advertencias=advertencias,
        )
