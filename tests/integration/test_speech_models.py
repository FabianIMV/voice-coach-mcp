"""Real Whisper (tiny model) on synthetic espeak-ng speech."""

import json

import pytest

from tests import tts
from voice_coach_mcp.speech.analysis import speech_metrics, transcribe_audio

pytestmark = [
    pytest.mark.models,
    pytest.mark.skipif(not tts.espeak_available(), reason="requires espeak-ng"),
]


@pytest.fixture
def tiny_config(config, monkeypatch):
    pytest.importorskip("faster_whisper")
    monkeypatch.setenv("VOICE_COACH_WHISPER_MODEL", "tiny")
    from voice_coach_mcp.config import load_config

    return load_config()


def test_transcribe_english(tiny_config, tmp_path):
    path = tts.espeak(
        "The key is to practice every day with real feedback.", "en", tmp_path / "en.wav"
    )
    r = json.loads(transcribe_audio(str(path), tiny_config))
    assert r["language"] == "en"
    assert "practice" in r["text"].lower()
    assert r["segments"][0]["t"] < 1.0
    assert r["words"][0]["w"]


def test_speech_metrics_detects_pause(tiny_config, tmp_path):
    text = 'Today I want to talk about communication. <break time="1500ms"/> Practicing with data helps a lot.'
    path = tts.espeak(text, "en", tmp_path / "en.wav")
    r = json.loads(speech_metrics(str(path), tiny_config, "en"))
    assert r["pauses"]["count"] == 1
    assert r["pauses"]["items"][0]["dur"] == pytest.approx(1.5, abs=0.2)
    assert 80 < r["pace"]["words_per_minute"] < 220
    assert {"pitch", "volume", "fillers", "segments"} <= r.keys()


def test_spanish_speech_metrics(tiny_config, tmp_path):
    text = (
        'Hoy quiero hablar de comunicación. <break time="1200ms"/> Practicar con datos ayuda mucho.'
    )
    path = tts.espeak(text, "es", tmp_path / "es.wav")
    r = json.loads(speech_metrics(str(path), tiny_config, "es"))
    assert r["language"] == "es"
    assert r["pauses"]["count"] == 1
