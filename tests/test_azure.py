import json
from pathlib import Path

import numpy as np
import pytest

from voice_coach_mcp.errors import UserError
from voice_coach_mcp.pronunciation.azure import AzureBackend, parse

RESPONSE = json.loads((Path(__file__).parent / "data" / "azure_response.json").read_text())


def test_parses_words_errors_and_scores():
    r = parse(RESPONSE)
    assert r.backend == "azure"
    assert r.overall_score == 71.0
    assert r.model_confidence == 0.91
    assert r.extra == {"fluency": 88.0, "completeness": 75.0}
    assert r.relative_distance == pytest.approx(0.25)
    assert [w.word for w in r.words] == ["i", "think", "so", "much"]

    i, think, so, much = r.words
    assert i.start == 0.3 and i.errors == []
    assert think.score == 62.0
    assert [e.to_dict() for e in think.errors] == [
        {"type": "substitution", "expected": "θ", "detected": "s"},
        {"type": "substitution", "expected": "ŋ"},  # inaccurate, no different alternative
        {"type": "insertion", "detected": "really"},  # word inserted after "think"
    ]
    assert think.detected == ["s", "ɪ", "ŋ", "k"]
    assert so.score == 100 and so.errors == []
    assert much.missing and much.score == 0 and much.start is None
    assert [e.type for e in much.errors] == ["deletion"] * 3


def test_no_recognition_is_a_readable_error():
    with pytest.raises(UserError, match="NoMatch"):
        parse({"RecognitionStatus": "NoMatch"})


def test_requires_credentials(config, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    with pytest.raises(UserError, match="AZURE_SPEECH_KEY"):
        AzureBackend().assess(np.zeros(16000, dtype=np.float32), "hi", "en-US", config)
