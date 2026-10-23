import pytest
import soundfile as sf

from tests import fake_sounddevice
from voice_coach_mcp.audio.recording import file_name, record
from voice_coach_mcp.errors import UserError


def test_records_and_resamples_to_16k(config, monkeypatch):
    calls = fake_sounddevice.install(monkeypatch, samplerate=48_000)
    r = record(2.0, "test", config)
    assert calls["samplerate"] == 48_000 and calls["frames"] == 96_000
    info = sf.info(r["audio"])
    assert (info.samplerate, info.channels) == (16_000, 1)
    assert info.duration == pytest.approx(2.0, abs=0.01)
    assert r["audio"].endswith("recordings/test.wav")
    assert r["warnings"] == []
    assert r["confidence"]["level"] == "high"
    assert r["levels"]["peak_dbfs"] == pytest.approx(-10.5, abs=0.5)


def test_digital_silence_warns_about_microphone_permission(config, monkeypatch):
    fake_sounddevice.install(monkeypatch, mode="silence")
    r = record(1.0, None, config)
    assert r["warnings"][0]["code"] == "no_microphone_permission"
    assert "Privacy & Security" in r["warnings"][0]["detail"]
    assert r["confidence"]["value"] == 0


def test_portaudio_error_is_a_readable_error(config, monkeypatch):
    fake_sounddevice.install(monkeypatch, mode="error")
    with pytest.raises(UserError, match="microphone"):
        record(1.0, None, config)


@pytest.mark.parametrize("seconds", [0, -1, 500])
def test_validates_duration(config, monkeypatch, seconds):
    fake_sounddevice.install(monkeypatch)
    with pytest.raises(UserError, match="seconds"):
        record(seconds, None, config)


def test_file_name_is_sanitized_and_never_overwrites(tmp_path):
    assert file_name("../my take:1.wav", tmp_path).name == "my_take_1.wav"
    (tmp_path / "take.wav").touch()
    (tmp_path / "take-2.wav").touch()
    assert file_name("take", tmp_path).name == "take-3.wav"
    assert file_name("canción", tmp_path).name == "canción.wav"
    assert file_name(None, tmp_path).name.startswith("recording-")
