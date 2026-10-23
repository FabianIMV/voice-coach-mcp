import numpy as np
import pytest

from tests import fake_transcript as ft
from tests import synthetic as s
from voice_coach_mcp.errors import UserError
from voice_coach_mcp.speech import metrics
from voice_coach_mcp.speech.transcription import language_code


def _texts(result):
    return [o["text"] for o in result["occurrences"]]


def test_pace_and_pauses_from_word_gaps():
    t = ft.build([ft.regular("one two three four"), ft.regular("five six", start=2.6)])
    words = t.words
    items = metrics.pauses(words, threshold=0.7)
    assert items == [{"t": 1.5, "dur": 1.1, "after": "four"}]
    r = metrics.pace(words, items)
    assert r["words"] == 6
    assert r["speaking_time_s"] == pytest.approx(3.3)
    assert r["words_per_minute"] == round(60 * 6 / 3.3)
    assert r["wpm_excluding_long_pauses"] == round(60 * 6 / 2.2)


def test_energy_based_pauses_measure_the_real_silence():
    # "words" = tones; Whisper would say the 2nd word ends 0.4 s later than it really does
    y = np.concatenate([s.tone(50, 0.5), s.tone(52, 0.5), s.silence(1.2), s.tone(50, 0.5)])
    t = ft.build([[("a", 0.0, 0.5), ("b", 0.5, 1.4), ("c", 2.2, 2.7)]])
    assert metrics.pauses(t.words, 0.7) == [{"t": 1.4, "dur": 0.8, "after": "b"}]
    (pause,) = metrics.pauses(t.words, 0.7, y)
    assert pause["dur"] == pytest.approx(1.2, abs=0.05)
    assert pause["t"] == pytest.approx(1.0, abs=0.05)
    assert pause["after"] == "b"


def test_english_fillers_and_isolation_by_pause(config):
    lists = metrics.load_filler_lists(config, "en")
    sentence = [
        ("I", 0.0, 0.2), ("like", 0.3, 0.5), ("it", 0.6, 0.8), ("and", 1.0, 1.2),
        ("like", 1.6, 1.8), ("you", 1.9, 2.0), ("know", 2.0, 2.2), ("um", 2.3, 2.6),
    ]  # fmt: skip
    r = metrics.fillers(ft.build([sentence]), lists, minutes=0)
    # "I like it" is a normal use; the second "like" follows a 0.4 s pause
    assert _texts(r) == ["like", "you know", "um"]
    assert r["occurrences"][0]["t"] == 1.6
    assert "per_minute" not in r


def test_english_fillers_by_comma(config):
    lists = metrics.load_filler_lists(config, "en")
    t = ft.build(
        [
            ft.regular("So, uh, I think, like, it works."),
            ft.regular("Well, I mean, it is, umm, fine", start=4),
        ]
    )
    r = metrics.fillers(t, lists, minutes=0.5)
    assert _texts(r) == ["so", "uh", "like", "well", "i mean", "umm"]
    assert r["total"] == 6 and r["per_minute"] == 12.0
    assert r["by_type"]["um"] == 1  # "umm" is grouped as "um"


def test_spanish_fillers(config):
    lists = metrics.load_filler_lists(config, "es")
    t = ft.build(
        [
            ft.regular("Bueno, eh, quiero leer este libro."),
            ft.regular("O sea, ehhh es importante, ¿no?", start=3),
            ft.regular("Lo hice como me dijeron, mmm, y pues bien", start=6),
        ],
        language="es",
    )
    r = metrics.fillers(t, lists, minutes=0.5)
    # "este libro" and "como me dijeron" are normal uses; "pues" is not isolated
    assert _texts(r) == ["bueno", "eh", "o sea", "ehhh", "no?", "mmm"]
    assert r["by_type"]["eh"] == 2  # "eh" and "ehhh" are grouped


def test_custom_filler_list(config, tmp_path, monkeypatch):
    custom = tmp_path / "fillers.toml"
    custom.write_text('[en]\nvocalizations = []\nphrases = ["basically"]\nambiguous = []\n')
    monkeypatch.setenv("VOICE_COACH_FILLERS", str(custom))
    from voice_coach_mcp.config import load_config

    lists = metrics.load_filler_lists(load_config(), "en")
    r = metrics.fillers(ft.build([ft.regular("uh basically yes")]), lists, minutes=0)
    assert _texts(r) == ["basically"]
    assert metrics.load_filler_lists(load_config(), "es") is not None  # the rest is kept
    assert metrics.load_filler_lists(load_config(), "fr") is None


def _speech(variation_st: float, levels_db: list[float]) -> tuple[np.ndarray, list]:
    """One "word" per level: 0.4 s tones around 120 Hz with the requested variation."""
    rng = np.random.default_rng(0)
    parts, sentence, t = [], [], 0.0
    for i, level in enumerate(levels_db):
        midi = 46.8 + rng.uniform(-1, 1) * variation_st * 1.7
        parts += [s.tone(midi, 0.4, amplitude=10 ** (level / 20)), s.silence(0.1)]
        sentence.append((f"w{i}", t, t + 0.4))
        t += 0.5
    return np.concatenate(parts), ft.build([sentence]).words


def test_monotone_vs_expressive_pitch():
    y, words = _speech(0.3, [-20] * 30)
    flat = metrics.pitch(y, words)
    assert flat["monotone"] and flat["std_semitones"] < 1
    assert flat["median_f0_hz"] == pytest.approx(120, abs=5)
    assert flat["monotone_stretches"] and flat["monotone_stretches"][0]["t"] == 0.0
    y, words = _speech(5, [-20] * 30)
    expressive = metrics.pitch(y, words)
    assert not expressive["monotone"] and expressive["std_semitones"] > 3
    assert expressive["monotone_stretches"] == []


def test_volume():
    y, words = _speech(1, [-20] * 12)
    assert metrics.volume(y, words)["low_variation"]
    y, words = _speech(1, [-30, -12, -24, -8, -28, -16] * 2)
    v = metrics.volume(y, words)
    assert not v["low_variation"]
    assert v["std_between_words_db"] > 5
    assert v["range_p10_p90_db"] > 15


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("en", "en"),
        ("en-US", "en"),
        ("English", "en"),
        ("es-CL", "es"),
        ("Spanish", "es"),
        (None, None),
        ("fr", "fr"),
    ],
)
def test_language_code(text, code):
    assert language_code(text) == code


def test_invalid_language_code():
    with pytest.raises(UserError):
        language_code("klingon")
