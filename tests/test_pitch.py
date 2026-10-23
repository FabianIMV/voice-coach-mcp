import pytest

from tests import synthetic as s
from voice_coach_mcp.singing.pitch import extract_contour, segment


def _notes(y):
    return segment(extract_contour(y))


@pytest.mark.parametrize("midi", [40.0, 45.25, 57.0, 69.3, 72.0 - 0.4, 81.1])
def test_accurate_pitch_across_the_range(midi):
    (note,) = _notes(s.sequence([(midi, 1.0)]))
    assert note.midi * 100 == pytest.approx(midi * 100, abs=3)
    assert note.stability == "stable"


def test_sequence_and_timing():
    notes = _notes(s.sequence([(60, 0.5), (64.3, 0.5), (67, 0.5)], gap=0.2, start=0.5))
    assert [round(n.midi, 1) for n in notes] == [60.0, 64.3, 67.0]
    assert notes[0].start == pytest.approx(0.5, abs=0.03)
    assert notes[1].start == pytest.approx(1.2, abs=0.03)
    assert notes[2].duration == pytest.approx(0.5, abs=0.05)


def test_legato_without_gap_splits_notes():
    notes = _notes(s.sequence([(60, 0.6), (62, 0.6), (64, 0.6)], gap=0.0))
    assert [round(n.midi) for n in notes] == [60, 62, 64]


def test_repeated_notes_with_short_gap():
    assert len(_notes(s.sequence([(67, 0.4), (67, 0.4)], gap=0.05))) == 2


def test_vibrato():
    (note,) = _notes(s.padded(s.tone(64, 1.5, vibrato_cents=50)))
    assert note.stability == "vibrato"
    assert note.vibrato_hz == pytest.approx(5.5, abs=0.3)
    assert note.vibrato_pp_cents == pytest.approx(100, abs=20)
    assert note.midi == pytest.approx(64, abs=0.05)


def test_unstable():
    notes = _notes(s.padded(s.tone(62, 1.5, jitter_cents=35, seed=3)))
    assert notes and all(n.stability == "unstable" for n in notes)


def test_drops_very_short_fragments():
    assert _notes(s.sequence([(60, 0.04)])) == []


def test_background_noise_creates_no_ghost_notes():
    notes = _notes(s.with_noise(s.sequence([(60, 0.6), (64, 0.6)], start=1.0), snr_db=30, seed=2))
    assert [round(n.midi) for n in notes] == [60, 64]
