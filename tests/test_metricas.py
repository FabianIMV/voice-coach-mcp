import numpy as np
import pytest

from tests import falsa_transcripcion as ft
from tests import sintetico as s
from voice_coach_mcp.errores import ErrorUsuario
from voice_coach_mcp.habla import metricas
from voice_coach_mcp.habla.transcripcion import codigo_idioma


def _textos(resultado):
    return [o["texto"] for o in resultado["ocurrencias"]]


def test_ritmo_y_pausas_por_huecos():
    t = ft.armar([ft.regular("uno dos tres cuatro"), ft.regular("cinco seis", inicio=2.6)])
    palabras = t.palabras
    lista = metricas.pausas(palabras, umbral=0.7)
    assert lista == [{"t": 1.5, "dur": 1.1, "tras": "cuatro"}]
    r = metricas.ritmo(palabras, lista)
    assert r["palabras"] == 6
    assert r["tiempo_habla_s"] == pytest.approx(3.3)
    assert r["palabras_por_minuto"] == round(60 * 6 / 3.3)
    assert r["ppm_sin_pausas_largas"] == round(60 * 6 / 2.2)


def test_pausas_por_energia_miden_el_silencio_real():
    # "palabras" = tonos; Whisper diría que la 2.ª palabra termina 0,4 s después de lo real
    y = np.concatenate([s.tono(50, 0.5), s.tono(52, 0.5), s.silencio(1.2), s.tono(50, 0.5)])
    t = ft.armar([[("a", 0.0, 0.5), ("b", 0.5, 1.4), ("c", 2.2, 2.7)]])
    assert metricas.pausas(t.palabras, 0.7) == [{"t": 1.4, "dur": 0.8, "tras": "b"}]
    (pausa,) = metricas.pausas(t.palabras, 0.7, y)
    assert pausa["dur"] == pytest.approx(1.2, abs=0.05)
    assert pausa["t"] == pytest.approx(1.0, abs=0.05)
    assert pausa["tras"] == "b"


def test_muletillas_es(config):
    listas = metricas.cargar_listas(config, "es")
    t = ft.armar(
        [
            ft.regular("Bueno, eh, quiero leer este libro."),
            ft.regular("O sea, ehhh es importante, ¿no?", inicio=3),
            ft.regular("Lo hice como me dijeron, mmm, y pues bien", inicio=6),
        ]
    )
    r = metricas.muletillas(t, listas, minutos=0.5)
    # "este libro" y "como me dijeron" son usos normales; "pues" no está aislada
    assert _textos(r) == ["bueno", "eh", "o sea", "ehhh", "no?", "mmm"]
    assert r["total"] == 6 and r["por_minuto"] == 12.0
    assert r["por_tipo"]["eh"] == 2  # "eh" y "ehhh" se agrupan


def test_muletillas_en_y_aislamiento_por_pausa(config):
    listas = metricas.cargar_listas(config, "en")
    frase = [
        ("I", 0.0, 0.2),
        ("like", 0.3, 0.5),
        ("it", 0.6, 0.8),
        ("and", 1.0, 1.2),
        ("like", 1.6, 1.8),
        ("you", 1.9, 2.0),
        ("know", 2.0, 2.2),
        ("um", 2.3, 2.6),
    ]
    r = metricas.muletillas(ft.armar([frase], "en"), listas, minutos=0)
    assert _textos(r) == ["like", "you know", "um"]
    assert r["ocurrencias"][0]["t"] == 1.6
    assert "por_minuto" not in r


def test_lista_de_muletillas_propia(config, tmp_path, monkeypatch):
    propia = tmp_path / "m.toml"
    propia.write_text('[es]\nvocalizaciones = []\nexpresiones = ["cachai"]\nambiguas = []\n')
    monkeypatch.setenv("VOICE_COACH_MULETILLAS", str(propia))
    from voice_coach_mcp.config import cargar_config

    listas = metricas.cargar_listas(cargar_config(), "es")
    r = metricas.muletillas(ft.armar([ft.regular("eh vamos cachai")]), listas, minutos=0)
    assert _textos(r) == ["cachai"]
    assert metricas.cargar_listas(cargar_config(), "en") is not None  # el resto se mantiene
    assert metricas.cargar_listas(cargar_config(), "fr") is None


def _habla(variacion_st: float, niveles_db: list[float]) -> tuple[np.ndarray, list]:
    """Una "palabra" por nivel: tonos de 0,4 s alrededor de 120 Hz con la variación pedida."""
    rng = np.random.default_rng(0)
    partes, frase, t = [], [], 0.0
    for i, nivel in enumerate(niveles_db):
        midi = 46.8 + rng.uniform(-1, 1) * variacion_st * 1.7
        partes += [s.tono(midi, 0.4, amplitud=10 ** (nivel / 20)), s.silencio(0.1)]
        frase.append((f"p{i}", t, t + 0.4))
        t += 0.5
    return np.concatenate(partes), ft.armar([frase]).palabras


def test_tono_monotono_vs_expresivo():
    y, palabras = _habla(0.3, [-20] * 30)
    plano = metricas.tono(y, palabras)
    assert plano["monotono"] and plano["desv_semitonos"] < 1
    assert plano["f0_mediana_hz"] == pytest.approx(120, abs=5)
    assert plano["tramos_monotonos"] and plano["tramos_monotonos"][0]["t"] == 0.0
    y, palabras = _habla(5, [-20] * 30)
    expresivo = metricas.tono(y, palabras)
    assert not expresivo["monotono"] and expresivo["desv_semitonos"] > 3
    assert expresivo["tramos_monotonos"] == []


def test_volumen():
    y, palabras = _habla(1, [-20] * 12)
    assert metricas.volumen(y, palabras)["variacion_baja"]
    y, palabras = _habla(1, [-30, -12, -24, -8, -28, -16] * 2)
    v = metricas.volumen(y, palabras)
    assert not v["variacion_baja"]
    assert v["desv_entre_palabras_db"] > 5
    assert v["rango_p10_p90_db"] > 15


@pytest.mark.parametrize(
    ("texto", "codigo"),
    [
        ("es", "es"),
        ("es-CL", "es"),
        ("en-US", "en"),
        ("English", "en"),
        ("Español", "es"),
        (None, None),
        ("fr", "fr"),
    ],
)
def test_codigo_idioma(texto, codigo):
    assert codigo_idioma(texto) == codigo


def test_codigo_idioma_invalido():
    with pytest.raises(ErrorUsuario):
        codigo_idioma("klingon")
