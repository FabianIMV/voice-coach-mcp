"""Real wav2vec2 phoneme model on neural speech synthesized with Piper."""

import json

import pytest

from tests import tts
from voice_coach_mcp.pronunciation.assessment import assess

pytestmark = [
    pytest.mark.models,
    pytest.mark.skipif(
        not (tts.espeak_available() and tts.piper_available()), reason="requires espeak-ng and uvx"
    ),
]

SENTENCE = "The very best things in life are free."


@pytest.fixture(scope="module", autouse=True)
def _extras():
    pytest.importorskip("transformers")
    pytest.importorskip("phonemizer")


def _assess(config, tmp_path, said, expected):
    path = tts.piper(said, tmp_path / "sentence.wav")
    return json.loads(assess(str(path), expected, config))


def test_correct_reading(config, tmp_path):
    r = _assess(config, tmp_path, SENTENCE, SENTENCE)
    assert r["summary"]["overall_score"] >= 90
    assert r["confidence"]["level"] == "high"
    assert r["warnings"] == []


def test_detects_substitutions(config, tmp_path):
    r = _assess(config, tmp_path, "The berry best sings in life are free.", SENTENCE)
    confusions = {(c["expected"], c["detected"]) for c in r["summary"]["frequent_confusions"]}
    assert ("v", "b") in confusions
    assert ("θ", "s") in confusions
    worst = {w["word"] for w in r["words"] if w["score"] < 100}
    assert {"very", "things"} <= worst


def test_different_text(config, tmp_path):
    r = _assess(config, tmp_path, "She sells sea shells by the sea shore.", SENTENCE)
    assert "text_mismatch" in {w["code"] for w in r["warnings"]}
    assert r["confidence"]["level"] == "low"
