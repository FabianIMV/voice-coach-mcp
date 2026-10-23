import pytest

from voice_coach_mcp import progreso
from voice_coach_mcp.errores import ErrorUsuario


def test_registrar_y_leer(config):
    assert progreso.leer(config) == {
        "archivo": str(config.dir_base / "progreso.md"),
        "entradas_totales": 0,
        "entradas": [],
    }
    progreso.registrar(config, "## 2026-10-20 · Canto · Escala\n\n- % dentro de 25 cents: 70")
    r = progreso.registrar(config, "- foco: muletillas")  # sin título: se agrega la fecha
    assert r["entradas_totales"] == 2
    texto = (config.dir_base / "progreso.md").read_text()
    assert texto.startswith("# Progreso de voz")
    leido = progreso.leer(config, entradas=1)
    assert leido["entradas_totales"] == 2
    assert len(leido["entradas"]) == 1
    assert leido["entradas"][0].startswith("## ") and "muletillas" in leido["entradas"][0]


def test_leer_respeta_presupuesto(config):
    for i in range(10):
        progreso.registrar(config, f"## Sesión {i}\n\n" + "dato " * 120)
    leido = progreso.leer(config, entradas=10)
    assert leido["entradas_mostradas"] < 10
    assert leido["entradas"][-1].startswith("## Sesión 9")  # se conservan las más recientes


def test_entrada_invalida(config):
    with pytest.raises(ErrorUsuario):
        progreso.registrar(config, "   ")
    with pytest.raises(ErrorUsuario):
        progreso.registrar(config, "x" * 5000)
