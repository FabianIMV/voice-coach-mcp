"""Modelo de fonemas wav2vec2 real sobre voz neural sintetizada con Piper."""

import json

import pytest

from tests import tts
from voice_coach_mcp.pronunciacion.evaluacion import evaluar

pytestmark = [
    pytest.mark.modelos,
    pytest.mark.skipif(
        not (tts.disponible() and tts.piper_disponible()), reason="requiere espeak-ng y uvx"
    ),
]

FRASE = "The very best things in life are free."


@pytest.fixture(scope="module", autouse=True)
def _extras():
    pytest.importorskip("transformers")
    pytest.importorskip("phonemizer")


def _evaluar(config, tmp_path, dicho, esperado):
    ruta = tts.sintetizar_piper(dicho, tmp_path / "frase.wav")
    return json.loads(evaluar(str(ruta), esperado, config))


def test_lectura_correcta(config, tmp_path):
    r = _evaluar(config, tmp_path, FRASE, FRASE)
    assert r["resumen"]["puntaje_global"] >= 90
    assert r["confianza"]["nivel"] == "alta"
    assert r["advertencias"] == []


def test_detecta_sustituciones(config, tmp_path):
    r = _evaluar(config, tmp_path, "The berry best sings in life are free.", FRASE)
    confusiones = {(c["esperado"], c["detectado"]) for c in r["resumen"]["confusiones_frecuentes"]}
    assert ("v", "b") in confusiones
    assert ("θ", "s") in confusiones
    peores = {p["palabra"] for p in r["palabras"] if p["puntaje"] < 100}
    assert {"very", "things"} <= peores


def test_texto_distinto(config, tmp_path):
    r = _evaluar(config, tmp_path, "She sells sea shells by the sea shore.", FRASE)
    assert "texto_no_coincide" in {a["codigo"] for a in r["advertencias"]}
    assert r["confianza"]["nivel"] == "baja"
