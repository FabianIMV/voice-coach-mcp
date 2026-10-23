import pytest

from tests import sintetico as s
from voice_coach_mcp.canto.pitch import extraer_contorno, segmentar


def _notas(y):
    return segmentar(extraer_contorno(y))


@pytest.mark.parametrize("midi", [40.0, 45.25, 57.0, 69.3, 72.0 - 0.4, 81.1])
def test_altura_precisa_en_todo_el_registro(midi):
    (nota,) = _notas(s.secuencia([(midi, 1.0)]))
    assert nota.midi * 100 == pytest.approx(midi * 100, abs=3)
    assert nota.estabilidad == "estable"


def test_secuencia_y_tiempos():
    notas = _notas(s.secuencia([(60, 0.5), (64.3, 0.5), (67, 0.5)], pausa=0.2, inicio=0.5))
    assert [round(n.midi, 1) for n in notas] == [60.0, 64.3, 67.0]
    assert notas[0].inicio == pytest.approx(0.5, abs=0.03)
    assert notas[1].inicio == pytest.approx(1.2, abs=0.03)
    assert notas[2].duracion == pytest.approx(0.5, abs=0.05)


def test_legato_sin_pausa_separa_notas():
    notas = _notas(s.secuencia([(60, 0.6), (62, 0.6), (64, 0.6)], pausa=0.0))
    assert [round(n.midi) for n in notas] == [60, 62, 64]


def test_notas_repetidas_con_hueco_corto():
    notas = _notas(s.secuencia([(67, 0.4), (67, 0.4)], pausa=0.05))
    assert len(notas) == 2


def test_vibrato():
    (nota,) = _notas(s.aislada(s.tono(64, 1.5, vibrato_cents=50)))
    assert nota.estabilidad == "vibrato"
    assert nota.vibrato_hz == pytest.approx(5.5, abs=0.3)
    assert nota.vibrato_pp_cents == pytest.approx(100, abs=20)
    assert nota.midi == pytest.approx(64, abs=0.05)


def test_inestable():
    notas = _notas(s.aislada(s.tono(62, 1.5, jitter_cents=35, semilla=3)))
    assert notas and all(n.estabilidad == "inestable" for n in notas)


def test_descarta_fragmentos_muy_cortos():
    assert _notas(s.secuencia([(60, 0.04)])) == []


def test_ruido_de_fondo_no_genera_notas_fantasma():
    notas = _notas(
        s.con_ruido(s.secuencia([(60, 0.6), (64, 0.6)], inicio=1.0), snr_db=30, semilla=2)
    )
    assert [round(n.midi) for n in notas] == [60, 64]
