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
