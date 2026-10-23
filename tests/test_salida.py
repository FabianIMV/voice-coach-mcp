import json

from voice_coach_mcp.salida import Recortable, ajustar, tamano


def test_no_recorta_si_cabe(config, tmp_path):
    audio = tmp_path / "a.wav"
    texto = ajustar({"x": [1, 2, 3]}, audio=audio, tool="t", config=config)
    assert json.loads(texto) == {"x": [1, 2, 3]}
    assert not (tmp_path / "a.t.json").exists()


def test_recorta_por_prioridad_y_guarda_detalle(config, tmp_path):
    audio = tmp_path / "a.wav"
    items = [{"i": i, "cents": (i * 7) % 50, "relleno": "x" * 40} for i in range(100)]
    resultado = {"resumen": {"n": 100}, "notas": items}
    texto = ajustar(
        resultado,
        audio=audio,
        tool="afinacion",
        config=config,
        recortables=[Recortable("notas", lambda it: it["cents"])],
    )
    salida = json.loads(texto)
    assert len(texto.encode()) <= config.max_bytes_respuesta
    detalle = tmp_path / "a.afinacion.json"
    assert salida["detalle_completo"] == str(detalle)
    assert json.loads(detalle.read_text())["notas"] == items
    mostradas = salida["notas"]
    assert 0 < len(mostradas) < 100
    assert salida["notas_mostradas"] == f"{len(mostradas)} de 100"
    # se quedan las de mayor prioridad, en su orden original
    assert min(it["cents"] for it in mostradas) >= max(
        it["cents"] for it in items if it not in mostradas
    )
    assert [it["i"] for it in mostradas] == sorted(it["i"] for it in mostradas)


def test_tamano_cuenta_bytes_utf8():
    assert tamano("ñ") == len('"ñ"'.encode())


def test_recorta_listas_anidadas_y_textos(config, tmp_path):
    resultado = {
        "texto": "palabra " * 400,
        "pausas": {"cantidad": 50, "lista": [{"t": i, "dur": i / 10} for i in range(50)]},
    }
    texto = ajustar(
        resultado,
        audio=tmp_path / "b.wav",
        tool="discurso",
        config=config,
        recortables=[Recortable("pausas.lista", lambda p: p["dur"])],
        textos=["texto"],
    )
    salida = json.loads(texto)
    assert len(texto.encode()) <= config.max_bytes_respuesta
    assert salida["pausas"]["lista"] == []
    assert salida["pausas"]["lista_mostradas"] == "0 de 50"
    assert salida["texto"].endswith("…") and len(salida["texto"]) > 100
    assert resultado["pausas"]["lista"][0] == {"t": 0, "dur": 0.0}  # no muta el original
