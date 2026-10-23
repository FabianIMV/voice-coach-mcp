import pytest

from voice_coach_mcp.errors import UserError
from voice_coach_mcp.singing.theory import hz_to_midi, midi_to_hz, note_name, parse_key, target_note


def test_conversions():
    assert hz_to_midi(440.0) == pytest.approx(69)
    assert hz_to_midi(261.6256) == pytest.approx(60, abs=1e-4)
    assert midi_to_hz(81) == pytest.approx(880)
    assert hz_to_midi(442.0, a4=442.0) == pytest.approx(69)


@pytest.mark.parametrize(
    ("midi", "name"), [(60, "C4"), (69, "A4"), (61, "C#4"), (40, "E2"), (84, "C6")]
)
def test_note_name(midi, name):
    assert note_name(midi) == name


@pytest.mark.parametrize(
    ("text", "name", "contains"),
    [
        ("A minor", "A minor", {9, 11, 0, 2, 4, 5, 7}),
        ("Am", "A minor", {9, 0, 4}),
        ("G major", "G major", {7, 11, 2, 6}),
        ("F#", "F# major", {6, 10, 1}),
        ("Bb major", "A# major", {10, 2, 5, 3}),
        ("E flat minor", "D# minor", {3, 6, 10}),
        ("C", "C major", {0, 4, 7}),
        ("La menor", "A minor", {9, 0, 4}),  # Spanish names are accepted too
        ("Sol mayor", "G major", {7, 11, 2, 6}),
        ("sib menor", "A# minor", {10, 1, 5}),
    ],
)
def test_parse_key(text, name, contains):
    scale, normalized = parse_key(text)
    assert normalized == name
    assert contains <= scale
    assert len(scale) == 7


def test_invalid_key():
    with pytest.raises(UserError):
        parse_key("H dorian")


def test_target_note_with_scale():
    c_major, _ = parse_key("C")
    assert target_note(61.4) == 61  # equal-tempered C#4
    assert target_note(61.4, c_major) == 62  # in C major the nearest note is D4
    assert target_note(60.6, c_major) == 60
