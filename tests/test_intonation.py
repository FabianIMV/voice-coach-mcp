import json

import numpy as np
import pytest

from tests import synthetic as s
from voice_coach_mcp.errors import UserError
from voice_coach_mcp.singing.intonation import analyze


def _analyze(config, y, tmp_path, **kwargs):
    path = s.save(tmp_path / "singing.wav", y)
    text = analyze(str(path), config, **kwargs)
    assert len(text.encode()) <= config.max_response_bytes
    return json.loads(text)


def test_without_reference_measures_against_equal_temperament(config, tmp_path):
    deviations = [0, -40, 30, -12, -35]
    y = s.sequence([(60 + 2 * i + d / 100, 0.5) for i, d in enumerate(deviations)])
    r = _analyze(config, y, tmp_path)
    assert r["mode"] == "equal_temperament"
    assert [n["cents"] for n in r["notes"]] == pytest.approx(deviations, abs=3)
    assert [n["note"] for n in r["notes"]] == ["C4", "D4", "E4", "F#4", "G#4"]
    summary = r["summary"]
    assert summary["notes"] == 5
    assert summary["pct_within_25_cents"] == 40.0
    assert summary["tendency"] == "flat"
    assert summary["range"] == "C4–G#4"
    assert r["confidence"]["level"] == "high"
    assert r["warnings"] == []


def test_sharp_tendency_and_drift(config, tmp_path):
    y = s.sequence([(62 + d / 100, 0.5) for d in (5, 10, 25, 35, 40, 45)])
    summary = _analyze(config, y, tmp_path)["summary"]
    assert summary["tendency"] == "sharp"
    assert summary["drift_cents"] > 20


def test_with_key(config, tmp_path):
    # 61.4 is C#4 + 40 cents; in C major the nearest scale note is D4 (-60 cents)
    y = s.sequence([(60, 0.5), (61.4, 0.5)])
    r = _analyze(config, y, tmp_path, key="C major")
    assert r["mode"] == "key" and r["key"] == "C major"
    assert r["notes"][1]["note"] == "D4"
    assert r["notes"][1]["cents"] == pytest.approx(-60, abs=3)


MELODY = [60, 62, 64, 65, 67, 67, 64, 60]


def _sing(pitches, *, start=0.8, late=None, skip=None, octave=0):
    """Sings MELODY (0.5 s per note) with deviations; late = {index: seconds}."""
    late, skip = late or {}, skip or set()
    parts, t = [s.silence(start)], start
    for i, pitch in enumerate(pitches):
        onset = start + i * 0.5 + late.get(i, 0.0)
        parts.append(s.silence(onset - t))
        dur = 0.45 - late.get(i, 0.0)
        parts.append(s.silence(dur) if i in skip else s.tone(pitch + 12 * octave, dur))
        t = onset + dur
    parts.append(s.silence(0.5))
    return np.concatenate(parts)


@pytest.fixture
def reference(tmp_path):
    return s.melody_midi(
        tmp_path / "ref.mid", [(m, i * 0.5, i * 0.5 + 0.45) for i, m in enumerate(MELODY)]
    )


def test_reference_octave_offset_and_late_onset(config, tmp_path, reference):
    pitches = [m + d / 100 for m, d in zip(MELODY, [0, 0, -25, 0, 0, 0, 40, 0], strict=True)]
    y = _sing(pitches, start=1.1, late={4: 0.15}, octave=-1)
    r = _analyze(config, y, tmp_path, reference_midi=str(reference))
    summary = r["summary"]
    assert r["mode"] == "midi_reference"
    assert summary["octave_shift"] == -1
    assert summary["start_offset_ms"] == pytest.approx(1100, abs=40)
    assert summary["relative_tempo"] == pytest.approx(1.0, abs=0.03)
    assert summary["missed"] == 0 and summary["extra_notes"] == 0
    notes = r["notes"]
    assert [n["expected"] for n in notes] == ["C3", "D3", "E3", "F3", "G3", "G3", "E3", "C3"]
    assert [n["cents"] for n in notes] == pytest.approx([0, 0, -25, 0, 0, 0, 40, 0], abs=3)
    assert notes[4]["onset"] == "late" and notes[4]["onset_ms"] == pytest.approx(150, abs=40)
    assert summary["onsets"]["late"] == 1


def test_reference_missed_and_wrong_note(config, tmp_path, reference):
    pitches = list(MELODY)
    pitches[6] = 65  # sings F4 where E4 was expected
    r = _analyze(config, _sing(pitches, skip={3}), tmp_path, reference_midi=str(reference))
    summary = r["summary"]
    assert summary["missed"] == 1
    assert summary["wrong_notes"] == 1
    missed = next(n for n in r["notes"] if n.get("status") == "missed")
    assert missed["expected"] == "F4"
    wrong = next(n for n in r["notes"] if n.get("wrong_note"))
    assert wrong["expected"] == "E4" and wrong["sung"] == "F4"


def test_polyphonic_reference_warns(config, tmp_path):
    ref = s.melody_midi(
        tmp_path / "poly.mid",
        [(m, i * 0.5, i * 0.5 + 0.45) for i, m in enumerate(MELODY)],
        accompaniment=True,
    )
    r = _analyze(config, _sing(MELODY), tmp_path, reference_midi=str(ref))
    assert "polyphonic_reference" in {w["code"] for w in r["warnings"]}
    assert r["summary"]["wrong_notes"] == 0


def test_many_notes_are_trimmed_and_details_saved(config, tmp_path):
    rng = np.random.default_rng(1)
    deviations = rng.integers(-45, 45, size=40)
    y = s.sequence([(55 + (i % 12) + d / 100, 0.3) for i, d in enumerate(deviations)])
    r = _analyze(config, y, tmp_path)
    assert r["summary"]["notes"] == 40
    assert r["notes_shown"].endswith("of 40")
    with open(r["full_details"]) as f:
        assert len(json.load(f)["notes"]) == 40
    worst = max(abs(int(d)) for d in deviations)
    assert max(abs(n["cents"]) for n in r["notes"]) == pytest.approx(worst, abs=3)


def test_silence(config, tmp_path):
    r = _analyze(config, s.silence(2.0), tmp_path)
    assert r["summary"]["notes"] == 0
    assert r["confidence"]["value"] == 0
    assert "digital_silence" in {w["code"] for w in r["warnings"]}


def test_missing_file(config):
    with pytest.raises(UserError, match="not found"):
        analyze("/does/not/exist.wav", config)
