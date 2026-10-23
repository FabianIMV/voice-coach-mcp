import numpy as np

from tests import synthetic as s
from voice_coach_mcp.audio.quality import assess, confidence


def _codes(quality):
    return {w["code"] for w in quality.warnings}


def test_clean_audio_has_no_warnings():
    q = assess(s.sequence([(60, 0.8), (64, 0.8)]))
    assert _codes(q) == set()
    assert q.factor == 1.0
    assert q.snr_db is not None and q.snr_db > 40


def test_clipping():
    q = assess(np.clip(s.sequence([(60, 1.0)]) * 6, -1, 1))
    assert "clipping" in _codes(q)
    assert q.factor < 1


def test_background_noise():
    q = assess(s.with_noise(s.sequence([(60, 0.8), (64, 0.8)], gap=0.3), snr_db=6))
    assert "noise" in _codes(q)
    assert q.snr_db < 15


def test_continuous_note_without_pauses_is_not_flagged_as_noise():
    assert "noise" not in _codes(assess(s.tone(60, 3.0)))


def test_short_audio():
    assert "short_audio" in _codes(assess(s.tone(60, 0.5), min_duration=1.0))


def test_digital_silence_and_silence():
    assert "digital_silence" in _codes(assess(np.zeros(16000, dtype=np.float32)))
    q = assess(s.tone(60, 1.0, amplitude=1e-4))
    assert "silence" in _codes(q)
    assert q.factor == 0


def test_confidence_levels():
    assert confidence(0.9) == {"value": 0.9, "level": "high"}
    assert confidence(0.5)["level"] == "medium"
    assert confidence(1.7)["value"] == 1.0
