import pytest

from voice_coach_mcp.canto.teoria import (
    hz_a_midi,
    midi_a_hz,
    nombre_nota,
    nota_objetivo,
    parsear_tonalidad,
)
from voice_coach_mcp.errores import ErrorUsuario


def test_conversiones():
    assert hz_a_midi(440.0) == pytest.approx(69)
    assert hz_a_midi(261.6256) == pytest.approx(60, abs=1e-4)
    assert midi_a_hz(81) == pytest.approx(880)
    assert hz_a_midi(442.0, a4=442.0) == pytest.approx(69)


@pytest.mark.parametrize(
    ("midi", "nombre"), [(60, "C4"), (69, "A4"), (61, "C#4"), (40, "E2"), (84, "C6")]
)
def test_nombre_nota(midi, nombre):
    assert nombre_nota(midi) == nombre


@pytest.mark.parametrize(
    ("texto", "nombre", "contiene"),
    [
        ("A minor", "A menor", {9, 11, 0, 2, 4, 5, 7}),
        ("Am", "A menor", {9, 0, 4}),
        ("La menor", "A menor", {9, 0, 4}),
        ("Sol mayor", "G mayor", {7, 11, 2, 6}),
        ("F#", "F# mayor", {6, 10, 1}),
        ("Bb major", "A# mayor", {10, 2, 5, 3}),
        ("sib menor", "A# menor", {10, 1, 5}),
        ("Do", "C mayor", {0, 4, 7}),
        ("re menor", "D menor", {2, 5, 9, 10}),
    ],
)
def test_parsear_tonalidad(texto, nombre, contiene):
    escala, normalizado = parsear_tonalidad(texto)
    assert normalizado == nombre
    assert contiene <= escala
    assert len(escala) == 7


def test_tonalidad_invalida():
    with pytest.raises(ErrorUsuario):
        parsear_tonalidad("H dórico")


def test_nota_objetivo_con_escala():
    do_mayor, _ = parsear_tonalidad("C")
    assert nota_objetivo(61.4) == 61  # C#4 temperado
    assert nota_objetivo(61.4, do_mayor) == 62  # en Do mayor, lo más cercano es D4
    assert nota_objetivo(60.6, do_mayor) == 60
