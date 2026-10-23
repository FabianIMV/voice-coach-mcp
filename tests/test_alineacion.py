import pytest

from voice_coach_mcp.pronunciacion.alineacion import (
    alinear,
    distancia,
    por_palabra,
    puntaje,
    puntaje_global,
)
from voice_coach_mcp.pronunciacion.base import ErrorFonema
from voice_coach_mcp.pronunciacion.fonemas import normalizar, palabras_de, tolerado


def _tipos(ops):
    return [(o.tipo, o.esperado, o.detectado) for o in ops]


def test_alineacion_identica():
    ops = alinear(list("abc"), list("abc"))
    assert [o.tipo for o in ops] == ["ok"] * 3
    assert distancia(ops) == 0


def test_sustitucion_omision_insercion():
    assert _tipos(alinear(["θ", "ɪ", "ŋ", "k"], ["s", "ɪ", "ŋ", "k"]))[0] == (
        "sustitucion",
        "θ",
        "s",
    )
    assert ("omision", "t", None) in _tipos(alinear(["b", "ɛ", "s", "t"], ["b", "ɛ", "s"]))
    ops = alinear(["f", "ɹ", "iː"], ["f", "ə", "ɹ", "iː"])
    assert _tipos(ops) == [
        ("ok", "f", "f"),
        ("insercion", None, "ə"),
        ("ok", "ɹ", "ɹ"),
        ("ok", "iː", "iː"),
    ]


def test_ship_sheep_es_sustitucion():
    assert _tipos(alinear(["ʃ", "iː", "p"], ["ʃ", "ɪ", "p"]))[1] == ("sustitucion", "iː", "ɪ")


def test_prefiere_sustituir_dentro_de_la_clase():
    # "street" leído "estreet": la e se inserta, no reemplaza a la s
    ops = alinear(["s", "t", "ɹ", "iː", "t"], ["ɛ", "s", "t", "ɹ", "iː", "t"])
    assert _tipos(ops)[0] == ("insercion", None, "ɛ")
    # una vocal distinta se alinea con la vocal, no con una consonante vecina
    ops = alinear(["k", "æ", "t"], ["k", "ʌ", "t"])
    assert _tipos(ops) == [("ok", "k", "k"), ("sustitucion", "æ", "ʌ"), ("ok", "t", "t")]


def test_tolerancias_y_r_de_enlace():
    assert tolerado("ɾ", "t") and tolerado("ə", "i") and not tolerado("ɪ", "iː")
    ops = alinear(["w", "ɛ", "ð", "ɚ", "ɪ", "z"], ["w", "ɛ", "ð", "ɚ", "ɹ", "ɪ", "z"])
    assert all(o.tipo == "ok" for o in ops)
    ops = alinear(["b", "ʌ", "ɾ", "ɚ"], ["b", "ʌ", "t", "ɚ"])
    assert all(o.tipo == "ok" for o in ops)


def test_normalizar():
    assert normalizar(["k", "ˈɑːɹ"]) == ["k", "ɑː", "ɹ"]
    assert normalizar(["l", "ɪ", "ɾ", "əl"]) == ["l", "ɪ", "ɾ", "ə", "l"]
    assert normalizar(["ɐ", "b", "aʊ", "t"]) == ["ə", "b", "aʊ", "t"]
    assert normalizar(["f", "oːɹ"]) == ["f", "oʊ", "ɹ"]


def test_palabras_de():
    assert palabras_de("Hello, world! It's 5 o'clock — “really”?") == [
        "Hello", "world", "It's", "5", "o'clock", "really"
    ]  # fmt: skip


def test_por_palabra_reparte_errores_e_inserciones():
    palabras = ["the", "very", "best"]
    esperados = [["ð", "ə"], ["v", "ɛ", "ɹ", "i"], ["b", "ɛ", "s", "t"]]
    detectados = ["ð", "ə", "b", "ɛ", "ɹ", "i", "ə", "b", "ɛ", "s"]
    tiempos = [i * 0.1 for i in range(len(detectados))]
    ops = alinear([f for fs in esperados for f in fs], detectados)
    r = por_palabra(palabras, esperados, ops, tiempos)
    assert r[0].puntaje == 100 and r[0].inicio == 0.0
    assert [e.a_dict() for e in r[1].errores] == [
        {"tipo": "sustitucion", "esperado": "v", "detectado": "b"},
        {"tipo": "insercion", "detectado": "ə"},
    ]
    assert r[1].puntaje == pytest.approx(100 * (1 - 1.5 / 4))
    assert r[2].errores == [ErrorFonema("omision", "t", None)]
    assert r[2].inicio == pytest.approx(0.7)
    assert puntaje_global(r) == pytest.approx(100 * (1 - 2.5 / 10))


def test_palabra_omitida():
    esperados = [["aɪ"], ["θ", "ɪ", "ŋ", "k"], ["s", "oʊ"]]
    ops = alinear([f for fs in esperados for f in fs], ["aɪ", "s", "oʊ"])
    r = por_palabra(["I", "think", "so"], esperados, ops)
    assert r[1].omitida and r[1].puntaje == 0
    assert not r[0].omitida and not r[2].omitida


def test_puntaje_acotado():
    assert puntaje(2, [ErrorFonema("omision")] * 5) == 0
    assert puntaje(0, []) == 100
