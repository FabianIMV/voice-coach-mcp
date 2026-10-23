import json

import numpy as np
import pytest

from tests import sintetico as s
from voice_coach_mcp.canto.afinacion import analizar
from voice_coach_mcp.errores import ErrorUsuario


def _analizar(config, y, tmp_path, **kwargs):
    ruta = s.guardar(tmp_path / "canto.wav", y)
    texto = analizar(str(ruta), config, **kwargs)
    assert len(texto.encode()) <= config.max_bytes_respuesta
    return json.loads(texto)


def test_sin_referencia_mide_contra_temperado(config, tmp_path):
    desv = [0, -40, 30, -12, -35]
    y = s.secuencia([(60 + 2 * i + d / 100, 0.5) for i, d in enumerate(desv)])
    r = _analizar(config, y, tmp_path)
    assert r["modo"] == "temperado"
    assert [n["cents"] for n in r["notas"]] == pytest.approx(desv, abs=3)
    assert [n["nota"] for n in r["notas"]] == ["C4", "D4", "E4", "F#4", "G#4"]
    res = r["resumen"]
    assert res["notas"] == 5
    assert res["porcentaje_dentro_25_cents"] == 40.0
    assert res["tendencia"] == "plano"
    assert res["rango"] == "C4–G#4"
    assert r["confianza"]["nivel"] == "alta"
    assert r["advertencias"] == []


def test_tendencia_sostenida_y_deriva(config, tmp_path):
    y = s.secuencia([(62 + d / 100, 0.5) for d in (5, 10, 25, 35, 40, 45)])
    res = _analizar(config, y, tmp_path)["resumen"]
    assert res["tendencia"] == "sostenido"
    assert res["deriva_cents"] > 20


def test_con_tonalidad(config, tmp_path):
    # 61.4 es C#4 + 40 cents; en Do mayor lo más cercano de la escala es D4 (-60 cents)
    y = s.secuencia([(60, 0.5), (61.4, 0.5)])
    r = _analizar(config, y, tmp_path, tonalidad="Do mayor")
    assert r["modo"] == "tonalidad" and r["tonalidad"] == "C mayor"
    assert r["notas"][1]["nota"] == "D4"
    assert r["notas"][1]["cents"] == pytest.approx(-60, abs=3)


MELODIA = [60, 62, 64, 65, 67, 67, 64, 60]


def _cantar(alturas, *, inicio=0.8, tarde=None, saltar=None, octava=0):
    """Canta MELODIA (0,5 s por nota) con desviaciones; tarde = {índice: segundos}."""
    tarde, saltar = tarde or {}, saltar or set()
    partes, t = [s.silencio(inicio)], inicio
    for i, altura in enumerate(alturas):
        ini = inicio + i * 0.5 + tarde.get(i, 0.0)
        partes.append(s.silencio(ini - t))
        dur = 0.45 - tarde.get(i, 0.0)
        partes.append(s.silencio(dur) if i in saltar else s.tono(altura + 12 * octava, dur))
        t = ini + dur
    partes.append(s.silencio(0.5))
    return np.concatenate(partes)


@pytest.fixture
def referencia(tmp_path):
    return s.midi_melodia(
        tmp_path / "ref.mid", [(m, i * 0.5, i * 0.5 + 0.45) for i, m in enumerate(MELODIA)]
    )


def test_con_referencia_octava_desfase_y_entrada_tarde(config, tmp_path, referencia):
    alturas = [m + d / 100 for m, d in zip(MELODIA, [0, 0, -25, 0, 0, 0, 40, 0], strict=True)]
    y = _cantar(alturas, inicio=1.1, tarde={4: 0.15}, octava=-1)
    r = _analizar(config, y, tmp_path, referencia_midi=str(referencia))
    res = r["resumen"]
    assert r["modo"] == "referencia_midi"
    assert res["transposicion_octavas"] == -1
    assert res["desfase_inicio_ms"] == pytest.approx(1100, abs=40)
    assert res["tempo_relativo"] == pytest.approx(1.0, abs=0.03)
    assert res["omitidas"] == 0 and res["notas_extra"] == 0
    notas = r["notas"]
    assert [n["esperada"] for n in notas] == ["C3", "D3", "E3", "F3", "G3", "G3", "E3", "C3"]
    assert [n["cents"] for n in notas] == pytest.approx([0, 0, -25, 0, 0, 0, 40, 0], abs=3)
    assert notas[4]["entrada"] == "tarde" and notas[4]["entrada_ms"] == pytest.approx(150, abs=40)
    assert res["entradas"]["tarde"] == 1


def test_con_referencia_nota_omitida_e_incorrecta(config, tmp_path, referencia):
    alturas = list(MELODIA)
    alturas[6] = 65  # canta F4 donde iba E4
    y = _cantar(alturas, saltar={3})
    r = _analizar(config, y, tmp_path, referencia_midi=str(referencia))
    res = r["resumen"]
    assert res["omitidas"] == 1
    assert res["notas_incorrectas"] == 1
    omitida = next(n for n in r["notas"] if n.get("estado") == "omitida")
    assert omitida["esperada"] == "F4"
    incorrecta = next(n for n in r["notas"] if n.get("nota_incorrecta"))
    assert incorrecta["esperada"] == "E4" and incorrecta["cantada"] == "F4"


def test_referencia_polifonica_avisa(config, tmp_path):
    ref = s.midi_melodia(
        tmp_path / "poli.mid",
        [(m, i * 0.5, i * 0.5 + 0.45) for i, m in enumerate(MELODIA)],
        acompanamiento=True,
    )
    r = _analizar(config, _cantar(MELODIA), tmp_path, referencia_midi=str(ref))
    assert "referencia_polifonica" in {a["codigo"] for a in r["advertencias"]}
    assert r["resumen"]["notas_incorrectas"] == 0


def test_muchas_notas_recorta_y_guarda_detalle(config, tmp_path):
    rng = np.random.default_rng(1)
    desv = rng.integers(-45, 45, size=40)
    y = s.secuencia([(55 + (i % 12) + d / 100, 0.3) for i, d in enumerate(desv)])
    r = _analizar(config, y, tmp_path)
    assert r["resumen"]["notas"] == 40
    assert r["notas_mostradas"].endswith("de 40")
    detalle = json.loads(open(r["detalle_completo"]).read())
    assert len(detalle["notas"]) == 40
    peor = max(abs(int(d)) for d in desv)
    assert max(abs(n["cents"]) for n in r["notas"]) == pytest.approx(peor, abs=3)


def test_silencio_y_ruido(config, tmp_path):
    r = _analizar(config, s.silencio(2.0), tmp_path)
    assert r["resumen"]["notas"] == 0
    assert r["confianza"]["valor"] == 0
    assert "silencio_digital" in {a["codigo"] for a in r["advertencias"]}


def test_archivo_inexistente(config):
    with pytest.raises(ErrorUsuario, match="No encuentro"):
        analizar("/no/existe.wav", config)
