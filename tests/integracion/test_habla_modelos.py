"""Whisper real (modelo tiny) sobre voz sintética de espeak-ng."""

import json

import pytest

from tests import tts
from voice_coach_mcp.habla.discurso import analizar_discurso, analizar_transcripcion

pytestmark = [
    pytest.mark.modelos,
    pytest.mark.skipif(not tts.disponible(), reason="requiere espeak-ng"),
]


@pytest.fixture
def config_tiny(config, monkeypatch):
    pytest.importorskip("faster_whisper")
    monkeypatch.setenv("VOICE_COACH_WHISPER_MODEL", "tiny")
    from voice_coach_mcp.config import cargar_config

    return cargar_config()


def test_transcribir_en(config_tiny, tmp_path):
    ruta = tts.sintetizar(
        "The key is to practice every day with real feedback.", "en", tmp_path / "en.wav"
    )
    r = json.loads(analizar_transcripcion(str(ruta), config_tiny))
    assert r["idioma"] == "en"
    assert "practice" in r["texto"].lower()
    assert r["segmentos"][0]["t"] < 1.0
    assert r["palabras"][0]["p"]


def test_metricas_discurso_es_detecta_pausa(config_tiny, tmp_path):
    texto = (
        'Hoy quiero hablar de comunicación. <break time="1500ms"/> Practicar con datos ayuda mucho.'
    )
    ruta = tts.sintetizar(texto, "es", tmp_path / "es.wav")
    r = json.loads(analizar_discurso(str(ruta), config_tiny, "es"))
    assert r["pausas"]["cantidad"] == 1
    assert r["pausas"]["lista"][0]["dur"] == pytest.approx(1.5, abs=0.2)
    assert 80 < r["ritmo"]["palabras_por_minuto"] < 220
    assert {"tono", "volumen", "muletillas", "segmentos"} <= r.keys()
