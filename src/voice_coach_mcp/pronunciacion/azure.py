"""Backend opcional: Azure Pronunciation Assessment (requiere clave y región de Azure Speech).

Se activa con VOICE_COACH_PRONUNCIACION_BACKEND=azure, AZURE_SPEECH_KEY y AZURE_SPEECH_REGION.
El audio se envía a Azure; el backend local no envía nada fuera del equipo.
"""

import json
import os
import tempfile
from pathlib import Path

import numpy as np

from ..audio import calidad as cal
from ..audio.io import guardar_wav
from ..config import SAMPLE_RATE, Config
from ..errores import ErrorUsuario
from .base import ErrorFonema, ResultadoPalabra, ResultadoPronunciacion

UMBRAL_FONEMA = 60  # AccuracyScore de fonema por debajo del cual se reporta como error
MAX_SEGUNDOS = 30.0  # recognize_once evalúa un solo enunciado
TICKS_POR_SEGUNDO = 10_000_000


def parsear(respuesta: dict) -> ResultadoPronunciacion:
    """Convierte el JSON de Azure (SpeechServiceResponse_JsonResult) al esquema común."""
    if respuesta.get("RecognitionStatus") != "Success" or not respuesta.get("NBest"):
        raise ErrorUsuario(
            f"Azure no reconoció habla (estado: {respuesta.get('RecognitionStatus')})."
        )
    mejor = respuesta["NBest"][0]
    evaluacion = mejor.get("PronunciationAssessment", {})
    palabras: list[ResultadoPalabra] = []
    for w in mejor.get("Words", []):
        pa = w.get("PronunciationAssessment", {})
        tipo = pa.get("ErrorType", "None")
        inicio = round(w["Offset"] / TICKS_POR_SEGUNDO, 2) if "Offset" in w else None
        if tipo == "Insertion":
            if palabras:
                palabras[-1].errores.append(ErrorFonema("insercion", detectado=w["Word"]))
            continue
        esperados, detectados, errores = [], [], []
        for f in w.get("Phonemes", []):
            fonema = f["Phoneme"]
            esperados.append(fonema)
            fpa = f.get("PronunciationAssessment", {})
            nbest = fpa.get("NBestPhonemes") or []
            alternativa = nbest[0]["Phoneme"] if nbest else fonema
            detectados.append(alternativa)
            if fpa.get("AccuracyScore", 100) < UMBRAL_FONEMA:
                errores.append(
                    ErrorFonema(
                        "sustitucion", fonema, alternativa if alternativa != fonema else None
                    )
                )
        omitida = tipo == "Omission"
        if omitida:
            errores = [ErrorFonema("omision", f) for f in esperados] or [ErrorFonema("omision")]
            detectados = []
        palabras.append(
            ResultadoPalabra(
                palabra=w["Word"],
                puntaje=0.0 if omitida else float(pa.get("AccuracyScore", 0)),
                esperados=esperados,
                detectados=detectados,
                errores=errores,
                inicio=None if omitida else inicio,
                omitida=omitida,
            )
        )
    completitud = float(evaluacion.get("CompletenessScore", 100))
    advertencias = []
    if completitud < 40:
        advertencias.append(
            cal.advertencia(
                "texto_no_coincide", f"Azure reporta completitud {completitud:.0f}/100."
            )
        )
    return ResultadoPronunciacion(
        backend="azure",
        palabras=palabras,
        puntaje_global=float(evaluacion.get("AccuracyScore", 0)),
        confianza_modelo=float(mejor.get("Confidence", 0)),
        distancia_relativa=1 - completitud / 100,
        fonemas_esperados=[f for p in palabras for f in p.esperados],
        fonemas_detectados=[f for p in palabras for f in p.detectados],
        advertencias=advertencias,
        extra={
            k: evaluacion[c]
            for k, c in (
                ("fluidez", "FluencyScore"),
                ("completitud", "CompletenessScore"),
                ("prosodia", "ProsodyScore"),
            )
            if c in evaluacion
        },
    )


class BackendAzure:
    nombre = "azure"

    def evaluar(
        self, y: np.ndarray, texto: str, idioma: str, config: Config
    ) -> ResultadoPronunciacion:
        clave, region = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
        if not clave or not region:
            raise ErrorUsuario("El backend azure requiere AZURE_SPEECH_KEY y AZURE_SPEECH_REGION.")
        if len(y) / SAMPLE_RATE > MAX_SEGUNDOS:
            raise ErrorUsuario(
                f"Con Azure, cada evaluación admite hasta {MAX_SEGUNDOS:.0f} s de audio."
            )
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as e:
            raise ErrorUsuario("Falta el SDK de Azure. Instálalo con: uv sync --extra azure") from e

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "audio.wav"
            guardar_wav(ruta, y)
            speech_config = speechsdk.SpeechConfig(subscription=clave, region=region)
            speech_config.speech_recognition_language = idioma
            evaluacion = speechsdk.PronunciationAssessmentConfig(
                reference_text=texto,
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                enable_miscue=True,
            )
            evaluacion.phoneme_alphabet = "IPA"
            evaluacion.nbest_phoneme_count = 1
            reconocedor = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=speechsdk.audio.AudioConfig(filename=str(ruta)),
            )
            evaluacion.apply_to(reconocedor)
            resultado = reconocedor.recognize_once()
        if resultado.reason == speechsdk.ResultReason.Canceled:
            detalle = resultado.cancellation_details
            raise ErrorUsuario(
                f"Azure canceló la evaluación: {detalle.reason} {detalle.error_details}"
            )
        crudo = resultado.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
        return parsear(json.loads(crudo))
