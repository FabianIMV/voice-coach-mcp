import json
from pathlib import Path

import pytest

from voice_coach_mcp.errores import ErrorUsuario
from voice_coach_mcp.pronunciacion.azure import BackendAzure, parsear

RESPUESTA = json.loads((Path(__file__).parent / "datos" / "azure_respuesta.json").read_text())


def test_parsea_palabras_errores_y_puntajes():
    r = parsear(RESPUESTA)
    assert r.backend == "azure"
    assert r.puntaje_global == 71.0
    assert r.confianza_modelo == 0.91
    assert r.extra == {"fluidez": 88.0, "completitud": 75.0}
    assert r.distancia_relativa == pytest.approx(0.25)
    assert [p.palabra for p in r.palabras] == ["i", "think", "so", "much"]

    i, think, so, much = r.palabras
    assert i.inicio == 0.3 and i.errores == []
    assert think.puntaje == 62.0
    assert [e.a_dict() for e in think.errores] == [
        {"tipo": "sustitucion", "esperado": "θ", "detectado": "s"},
        {"tipo": "sustitucion", "esperado": "ŋ"},  # imprecisa, sin alternativa distinta
        {"tipo": "insercion", "detectado": "really"},  # palabra insertada tras "think"
    ]
    assert think.detectados == ["s", "ɪ", "ŋ", "k"]
    assert so.puntaje == 100 and so.errores == []
    assert much.omitida and much.puntaje == 0 and much.inicio is None
    assert [e.tipo for e in much.errores] == ["omision"] * 3


def test_sin_reconocimiento_es_error_legible():
    with pytest.raises(ErrorUsuario, match="NoMatch"):
        parsear({"RecognitionStatus": "NoMatch"})


def test_requiere_credenciales(config, monkeypatch):
    import numpy as np

    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    with pytest.raises(ErrorUsuario, match="AZURE_SPEECH_KEY"):
        BackendAzure().evaluar(np.zeros(16000, dtype=np.float32), "hi", "en-US", config)
