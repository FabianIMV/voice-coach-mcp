"""Regenerates the synthetic example audio and the real output of every tool.

The analysis tools are called through the real server over stdio (as Claude would do it).
`record_audio` needs a microphone: here it runs in-process with a simulated input device.
The speech examples are synthesized with espeak-ng and the pronunciation ones with Piper (the
public-domain LJSpeech voice, run through uvx). Requires `espeak-ng` and the `speech` and
`pronunciation` extras.

Usage: uv run python examples/generate_examples.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import anyio
import numpy as np
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests import fake_sounddevice, tts  # noqa: E402
from tests import synthetic as s  # noqa: E402

AUDIO = ROOT / "examples" / "audio"
OUTPUTS = ROOT / "examples" / "outputs"

SPEECH_EN = (
    'Um, so today I want to talk about, uh, public speaking. <break time="1000ms"/> You know, '
    "most people feel nervous, like, before a big talk. I mean, that is completely normal. "
    '<break time="800ms"/> The key is to practice with real feedback.'
)
SPEECH_ES = (
    'Bueno, eh, hoy quiero hablarles de un tema importante. <break time="1200ms"/> '
    "O sea, la forma en que comunicamos nuestras ideas cambia todo. Este, cuando hablamos en "
    'público, mmm, muchas veces nos ponemos nerviosos. <break time="900ms"/> Entonces, la '
    "clave está en practicar, ¿no? Y practicar con datos concretos."
)

SENTENCE = "I think the very best things in life are free."
SENTENCE_WITH_ERRORS = "I sink the berry best sings in life are free."  # θ→s and v→b

PROGRESS_ENTRY = """## 2026-10-23 · Singing · C major scale (intermediate)

- **Goal**: tune the high part of the scale.
- **Takes**: 3 (`c-scale-take1` … `take3`)
- **Metrics**: within ±25 cents 62% → 75%; B4 −58 → −42 cents; E4 −30 cents unchanged.
- **What improved**: the final C5 was centered (−2 cents) with a steady 5.5 Hz vibrato.
- **Next focus**: B4 and E4 within ±20 cents with sustained notes on *ng*."""

# Original 8-bar melody (no copyright), 0.5 s per quarter note.
MELODY = [
    (67, 1),
    (69, 1),
    (71, 2),
    (69, 1),
    (67, 1),
    (64, 2),
    (62, 1),
    (64, 1),
    (67, 1),
    (69, 1),
    (67, 4),
]


def _existing_or_piper(path: Path, text: str) -> Path:
    # Piper is not deterministic: existing audio is reused so the examples stay stable.
    return path if path.exists() else tts.piper(text, path)


def prepare_audio() -> dict[str, Path]:
    AUDIO.mkdir(parents=True, exist_ok=True)
    paths = {}

    # 1) C major scale with known deviations (cents) and a vibrato note.
    deviations = [0, -8, -30, 5, 22, -15, -42, 3]
    scale = [60, 62, 64, 65, 67, 69, 71, 72]
    parts = [s.silence(0.4)]
    for i, (m, d) in enumerate(zip(scale, deviations, strict=True)):
        vibrato = 45 if i == 7 else 0
        parts += [
            s.tone(m + d / 100, 1.4 if i == 7 else 0.6, vibrato_cents=vibrato),
            s.silence(0.12),
        ]
    parts.append(s.silence(0.4))
    paths["scale"] = s.save(AUDIO / "c_major_scale.wav", s.with_noise(np.concatenate(parts), 35))

    # 2) MIDI reference and a "sung" version one octave lower that starts 1 s late, with a
    #    flat note, a late onset, an unstable note and vibrato on the final note.
    t, ref = 0.0, []
    for m, quarters in MELODY:
        ref.append((m, t, t + quarters * 0.5 - 0.05))
        t += quarters * 0.5
    paths["midi"] = s.melody_midi(AUDIO / "reference_melody.mid", ref)

    parts, cursor, start = [s.silence(1.0)], 1.0, 1.0
    for i, (m, ref_start, ref_end) in enumerate(ref):
        delay = 0.14 if i == 5 else 0.0
        onset = start + ref_start + delay
        parts.append(s.silence(onset - cursor))
        pitch = m - 12 + (-0.33 if i == 2 else 0.0) + (0.18 if i == 8 else 0.0)
        tone = s.tone(
            pitch,
            ref_end - ref_start - delay,
            vibrato_cents=40 if i == len(ref) - 1 else 0,
            jitter_cents=30 if i == 6 else 0,
            seed=i,
        )
        parts.append(tone)
        cursor = onset + len(tone) / s.SR
    parts.append(s.silence(0.6))
    paths["sung"] = s.save(AUDIO / "sung_melody.wav", s.with_noise(np.concatenate(parts), 35))
    paths["speech_en"] = tts.espeak(SPEECH_EN, "en", AUDIO / "speech_en.wav", 160)
    paths["speech_es"] = tts.espeak(SPEECH_ES, "es", AUDIO / "speech_es.wav")
    paths["pron_correct"] = _existing_or_piper(AUDIO / "pronunciation_correct.wav", SENTENCE)
    paths["pron_errors"] = _existing_or_piper(
        AUDIO / "pronunciation_errors.wav", SENTENCE_WITH_ERRORS
    )
    return paths


def _clean(text: str, temp: str) -> dict:
    """Absolute paths → repo-relative so the example is readable."""
    return json.loads(text.replace(str(ROOT) + "/", "").replace(temp, "~/VoiceCoach"))


async def call_over_stdio(paths: dict[str, Path], temp: str) -> dict[str, dict]:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "voice_coach_mcp"],
        env={**os.environ, "VOICE_COACH_DIR": temp},
        cwd=str(ROOT),
    )
    calls = [
        ("analyze_pitch_equal_temperament", "analyze_pitch", {"audio": str(paths["scale"])}),
        ("analyze_pitch_key", "analyze_pitch", {"audio": str(paths["scale"]), "key": "G major"}),
        (
            "analyze_pitch_midi_reference",
            "analyze_pitch",
            {"audio": str(paths["sung"]), "reference_midi": str(paths["midi"])},
        ),
        ("transcribe_en", "transcribe", {"audio": str(paths["speech_en"])}),
        (
            "speech_metrics_en",
            "speech_metrics",
            {"audio": str(paths["speech_en"]), "language": "en"},
        ),
        (
            "speech_metrics_es",
            "speech_metrics",
            {"audio": str(paths["speech_es"]), "language": "es"},
        ),
        (
            "assess_pronunciation_correct",
            "assess_pronunciation",
            {"audio": str(paths["pron_correct"]), "expected_text": SENTENCE},
        ),
        (
            "assess_pronunciation_with_errors",
            "assess_pronunciation",
            {"audio": str(paths["pron_errors"]), "expected_text": SENTENCE},
        ),
        ("log_progress", "log_progress", {"entry": PROGRESS_ENTRY}),
        ("read_progress", "read_progress", {"entries": 3}),
    ]
    outputs = {}
    async with Client(server, read_timeout_seconds=600) as client:
        for name, tool, args in calls:
            r = await client.call_tool(tool, args)
            text = r.content[0].text
            print(f"{name}: {len(text.encode())} bytes", file=sys.stderr)
            outputs[name] = {
                "call": {"tool": tool, "arguments": args},
                "response": _clean(text, temp),
            }
    return outputs


async def simulated_recording(temp: str) -> dict[str, dict]:
    import pytest

    from voice_coach_mcp.server import mcp

    outputs = {}
    for mode, name in (
        ("tone", "record_audio_simulated"),
        ("silence", "record_audio_no_permission"),
    ):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("VOICE_COACH_DIR", temp)
            fake_sounddevice.install(mp, mode=mode)
            async with Client(mcp) as client:
                args = {"seconds": 3, "name": "take"}
                r = await client.call_tool("record_audio", args)
        outputs[name] = {
            "note": "Simulated input device (the environment that generated this has no microphone).",
            "call": {"tool": "record_audio", "arguments": args},
            "response": _clean(r.content[0].text, temp),
        }
    return outputs


async def main() -> None:
    paths = {k: v.relative_to(ROOT) for k, v in prepare_audio().items()}
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        outputs = await call_over_stdio(paths, temp)
        outputs |= await simulated_recording(temp)
    for name, content in outputs.items():
        (OUTPUTS / f"{name}.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n"
        )


if __name__ == "__main__":
    anyio.run(main)
