"""The whole server through an in-memory MCP client."""

import json
import sys

import pytest
from mcp.client import Client

from tests import fake_sounddevice
from tests import fake_transcript as ft
from tests import synthetic as s
from voice_coach_mcp.server import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_lists_tools_and_prompts():
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        prompts = {p.name for p in (await client.list_prompts()).prompts}
    assert set(tools) == {
        "record_audio", "analyze_pitch", "transcribe", "speech_metrics",
        "assess_pronunciation", "read_progress", "log_progress",
    }  # fmt: skip
    assert all(t.annotations and t.annotations.title for t in tools.values())
    assert tools["read_progress"].annotations.read_only_hint
    assert prompts == {"singing_session", "pronunciation_session", "speaking_session"}


async def test_analyze_pitch(config, tmp_path):
    path = s.save(tmp_path / "a.wav", s.sequence([(69.2, 0.6), (71, 0.6)]))
    async with Client(mcp) as client:
        r = await client.call_tool("analyze_pitch", {"audio": str(path)})
    assert not r.is_error
    data = json.loads(r.content[0].text)
    assert [n["note"] for n in data["notes"]] == ["A4", "B4"]
    assert data["notes"][0]["cents"] == pytest.approx(20, abs=3)


async def test_errors_are_readable(config):
    async with Client(mcp) as client:
        r = await client.call_tool("analyze_pitch", {"audio": "missing.wav"})
        r2 = await client.call_tool("analyze_pitch", {"audio": "missing.wav", "key": "X"})
    assert r.is_error and "Audio file not found" in r.content[0].text
    assert r2.is_error


async def test_record_and_analyze_by_name(config, monkeypatch):
    fake_sounddevice.install(monkeypatch, samplerate=44_100)
    async with Client(mcp) as client:
        r = await client.call_tool("record_audio", {"seconds": 1.5, "name": "take1"})
        recording = json.loads(r.content[0].text)
        r2 = await client.call_tool("analyze_pitch", {"audio": "take1"})
    assert recording["audio"].endswith("take1.wav")
    data = json.loads(r2.content[0].text)
    assert data["notes"][0]["note"] == "A4"
    assert abs(data["notes"][0]["cents"]) <= 2


async def test_singing_prompt():
    async with Client(mcp) as client:
        r = await client.get_prompt(
            "singing_session", {"level": "beginner", "reference_midi": "x.mid"}
        )
    text = r.messages[0].content.text
    assert "beginner" in text and "x.mid" in text and "analyze_pitch" in text


async def test_speech_metrics_with_fake_transcript(config, tmp_path, monkeypatch):
    sentences = [
        ft.regular("So, uh, today we talk about voice."),
        ft.regular("I mean, practice helps.", start=3.5),
    ]
    monkeypatch.setattr(
        "voice_coach_mcp.speech.analysis.transcribe", lambda *a, **k: ft.build(sentences)
    )
    path = s.save(tmp_path / "speech.wav", s.sequence([(48, 2.5), (50, 1.6)], gap=1.0))
    async with Client(mcp) as client:
        r = await client.call_tool("speech_metrics", {"audio": str(path), "language": "en-US"})
    data = json.loads(r.content[0].text)
    assert data["language"] == "en"
    assert data["fillers"]["by_type"] == {"so": 1, "uh": 1, "i mean": 1}
    assert data["pauses"]["count"] == 1
    assert data["segments"][1]["text"].startswith("I mean")


async def test_transcribe_silence(config, tmp_path):
    path = s.save(tmp_path / "mute.wav", s.silence(2.0))
    async with Client(mcp) as client:
        r = await client.call_tool("transcribe", {"audio": str(path)})
    data = json.loads(r.content[0].text)
    assert data["confidence"]["value"] == 0
    assert "digital_silence" in {w["code"] for w in data["warnings"]}


async def test_missing_speech_extra_explains_how_to_install(config, tmp_path, monkeypatch):
    from voice_coach_mcp.speech import transcription

    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # simulates it is not installed
    monkeypatch.setattr(transcription, "_models", {})
    path = s.save(tmp_path / "a.wav", s.sequence([(60, 1.0)]))
    async with Client(mcp) as client:
        r = await client.call_tool("transcribe", {"audio": str(path)})
    assert r.is_error and "uv sync --extra speech" in r.content[0].text


class _FakeBackend:
    """Simulates what the model would detect: "very" with b and "things" with s."""

    name = "fake"

    def assess(self, y, text, language, config):
        from voice_coach_mcp.pronunciation import alignment
        from voice_coach_mcp.pronunciation.base import PronunciationResult

        words = ["The", "very", "best", "things"]
        expected = [["ð", "ə"], ["v", "ɛ", "ɹ", "i"], ["b", "ɛ", "s", "t"], ["θ", "ɪ", "ŋ", "z"]]
        detected = ["ð", "ə", "b", "ɛ", "ɹ", "i", "b", "ɛ", "s", "t", "s", "ɪ", "ŋ", "z"]
        flat = [p for ps in expected for p in ps]
        ops = alignment.align(flat, detected)
        r = alignment.by_word(words, expected, ops, [i * 0.1 for i in range(len(detected))])
        return PronunciationResult(
            "fake", r, alignment.overall_score(r), 0.9, 2 / 14, flat, detected
        )


async def test_assess_pronunciation_with_fake_backend(config, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "voice_coach_mcp.pronunciation.assessment.backend", lambda c: _FakeBackend()
    )
    path = s.save(tmp_path / "sentence.wav", s.sequence([(55, 1.5)]))
    async with Client(mcp) as client:
        r = await client.call_tool(
            "assess_pronunciation", {"audio": str(path), "expected_text": "The very best things"}
        )
    data = json.loads(r.content[0].text)
    summary = data["summary"]
    assert summary["overall_score"] == round(100 * (1 - 2 / 14))
    assert summary["words_with_errors"] == 2
    assert summary["errors"] == {"substitution": 2, "deletion": 0, "insertion": 0}
    assert {"expected": "θ", "detected": "s", "count": 1} in summary["frequent_confusions"]
    assert data["words"][1] == {
        "word": "very",
        "score": 75,
        "t": 0.2,
        "expected": "v ɛ ɹ i",
        "detected": "b ɛ ɹ i",
        "errors": [{"type": "substitution", "expected": "v", "detected": "b"}],
    }
    assert data["words"][0] == {"word": "The", "score": 100, "t": 0.0}


async def test_unknown_backend(config, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_COACH_PRONUNCIATION_BACKEND", "other")
    path = s.save(tmp_path / "sentence.wav", s.sequence([(55, 1.0)]))
    async with Client(mcp) as client:
        r = await client.call_tool(
            "assess_pronunciation", {"audio": str(path), "expected_text": "hi"}
        )
    assert r.is_error and "local" in r.content[0].text


async def test_progress_tools(config):
    async with Client(mcp) as client:
        await client.call_tool(
            "log_progress", {"entry": "## 2026-10-23 · Speaking\n\n- 3 fillers/min"}
        )
        r = await client.call_tool("read_progress", {})
    data = json.loads(r.content[0].text)
    assert data["total_entries"] == 1 and "fillers" in data["entries"][0]
