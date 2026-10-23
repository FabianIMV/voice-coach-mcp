import pytest

from voice_coach_mcp.pronunciation.alignment import align, by_word, distance, overall_score, score
from voice_coach_mcp.pronunciation.base import PhonemeError
from voice_coach_mcp.pronunciation.phonemes import normalize, tolerated, words_of


def _types(ops):
    return [(o.type, o.expected, o.detected) for o in ops]


def test_identical_alignment():
    ops = align(list("abc"), list("abc"))
    assert [o.type for o in ops] == ["ok"] * 3
    assert distance(ops) == 0


def test_substitution_deletion_insertion():
    assert _types(align(["θ", "ɪ", "ŋ", "k"], ["s", "ɪ", "ŋ", "k"]))[0] == (
        "substitution",
        "θ",
        "s",
    )
    assert ("deletion", "t", None) in _types(align(["b", "ɛ", "s", "t"], ["b", "ɛ", "s"]))
    ops = align(["f", "ɹ", "iː"], ["f", "ə", "ɹ", "iː"])
    assert _types(ops) == [
        ("ok", "f", "f"),
        ("insertion", None, "ə"),
        ("ok", "ɹ", "ɹ"),
        ("ok", "iː", "iː"),
    ]


def test_ship_sheep_is_a_substitution():
    assert _types(align(["ʃ", "iː", "p"], ["ʃ", "ɪ", "p"]))[1] == ("substitution", "iː", "ɪ")


def test_prefers_substituting_within_the_class():
    # "street" read as "estreet": the e is inserted, it does not replace the s
    ops = align(["s", "t", "ɹ", "iː", "t"], ["ɛ", "s", "t", "ɹ", "iː", "t"])
    assert _types(ops)[0] == ("insertion", None, "ɛ")
    # a different vowel aligns with the vowel, not with a neighboring consonant
    ops = align(["k", "æ", "t"], ["k", "ʌ", "t"])
    assert _types(ops) == [("ok", "k", "k"), ("substitution", "æ", "ʌ"), ("ok", "t", "t")]


def test_tolerances_and_linking_r():
    assert tolerated("ɾ", "t") and tolerated("ə", "i") and not tolerated("ɪ", "iː")
    ops = align(["w", "ɛ", "ð", "ɚ", "ɪ", "z"], ["w", "ɛ", "ð", "ɚ", "ɹ", "ɪ", "z"])
    assert all(o.type == "ok" for o in ops)
    ops = align(["b", "ʌ", "ɾ", "ɚ"], ["b", "ʌ", "t", "ɚ"])
    assert all(o.type == "ok" for o in ops)


def test_normalize():
    assert normalize(["k", "ˈɑːɹ"]) == ["k", "ɑː", "ɹ"]
    assert normalize(["l", "ɪ", "ɾ", "əl"]) == ["l", "ɪ", "ɾ", "ə", "l"]
    assert normalize(["ɐ", "b", "aʊ", "t"]) == ["ə", "b", "aʊ", "t"]
    assert normalize(["f", "oːɹ"]) == ["f", "oʊ", "ɹ"]


def test_words_of():
    assert words_of("Hello, world! It's 5 o'clock — “really”?") == [
        "Hello", "world", "It's", "5", "o'clock", "really"
    ]  # fmt: skip


def test_by_word_distributes_errors_and_insertions():
    words = ["the", "very", "best"]
    expected = [["ð", "ə"], ["v", "ɛ", "ɹ", "i"], ["b", "ɛ", "s", "t"]]
    detected = ["ð", "ə", "b", "ɛ", "ɹ", "i", "ə", "b", "ɛ", "s"]
    times = [i * 0.1 for i in range(len(detected))]
    ops = align([p for ps in expected for p in ps], detected)
    r = by_word(words, expected, ops, times)
    assert r[0].score == 100 and r[0].start == 0.0
    assert [e.to_dict() for e in r[1].errors] == [
        {"type": "substitution", "expected": "v", "detected": "b"},
        {"type": "insertion", "detected": "ə"},
    ]
    assert r[1].score == pytest.approx(100 * (1 - 1.5 / 4))
    assert r[2].errors == [PhonemeError("deletion", "t", None)]
    assert r[2].start == pytest.approx(0.7)
    assert overall_score(r) == pytest.approx(100 * (1 - 2.5 / 10))


def test_missing_word():
    expected = [["aɪ"], ["θ", "ɪ", "ŋ", "k"], ["s", "oʊ"]]
    ops = align([p for ps in expected for p in ps], ["aɪ", "s", "oʊ"])
    r = by_word(["I", "think", "so"], expected, ops)
    assert r[1].missing and r[1].score == 0
    assert not r[0].missing and not r[2].missing


def test_score_is_bounded():
    assert score(2, [PhonemeError("deletion")] * 5) == 0
    assert score(0, []) == 100
