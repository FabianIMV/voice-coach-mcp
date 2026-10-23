import json

from voice_coach_mcp.output import Trimmable, fit, size


def test_no_trimming_when_it_fits(config, tmp_path):
    text = fit({"x": [1, 2, 3]}, audio=tmp_path / "a.wav", tool="t", config=config)
    assert json.loads(text) == {"x": [1, 2, 3]}
    assert not (tmp_path / "a.t.json").exists()


def test_trims_by_priority_and_saves_details(config, tmp_path):
    items = [{"i": i, "cents": (i * 7) % 50, "padding": "x" * 40} for i in range(100)]
    result = {"summary": {"n": 100}, "notes": items}
    text = fit(
        result,
        audio=tmp_path / "a.wav",
        tool="pitch",
        config=config,
        trimmable=[Trimmable("notes", lambda it: it["cents"])],
    )
    out = json.loads(text)
    assert len(text.encode()) <= config.max_response_bytes
    details = tmp_path / "a.pitch.json"
    assert out["full_details"] == str(details)
    assert json.loads(details.read_text())["notes"] == items
    shown = out["notes"]
    assert 0 < len(shown) < 100
    assert out["notes_shown"] == f"{len(shown)} of 100"
    # the highest-priority items are kept, in their original order
    assert min(it["cents"] for it in shown) >= max(it["cents"] for it in items if it not in shown)
    assert [it["i"] for it in shown] == sorted(it["i"] for it in shown)


def test_size_counts_utf8_bytes():
    assert size("ñ") == len('"ñ"'.encode())


def test_trims_nested_lists_and_texts(config, tmp_path):
    result = {
        "text": "word " * 600,
        "pauses": {"count": 50, "items": [{"t": i, "dur": i / 10} for i in range(50)]},
    }
    text = fit(
        result,
        audio=tmp_path / "b.wav",
        tool="speech",
        config=config,
        trimmable=[Trimmable("pauses.items", lambda p: p["dur"]), "text"],
    )
    out = json.loads(text)
    assert len(text.encode()) <= config.max_response_bytes
    assert out["pauses"]["items"] == []
    assert out["pauses"]["items_shown"] == "0 of 50"
    assert out["text"].endswith("…") and len(out["text"]) > 100
    assert result["pauses"]["items"][0] == {"t": 0, "dur": 0.0}  # the original is not mutated
