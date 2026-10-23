import pytest

from voice_coach_mcp import progress
from voice_coach_mcp.errors import UserError


def test_log_and_read(config):
    assert progress.read(config) == {
        "file": str(config.base_dir / "progress.md"),
        "total_entries": 0,
        "entries": [],
    }
    progress.log(config, "## 2026-10-20 · Singing · Scale\n\n- % within 25 cents: 70")
    r = progress.log(config, "- focus: fillers")  # no title: the date is added
    assert r["total_entries"] == 2
    assert (config.base_dir / "progress.md").read_text().startswith("# Voice progress")
    read = progress.read(config, entries=1)
    assert read["total_entries"] == 2
    assert len(read["entries"]) == 1
    assert read["entries"][0].startswith("## ") and "fillers" in read["entries"][0]


def test_read_respects_the_budget(config):
    for i in range(10):
        progress.log(config, f"## Session {i}\n\n" + "data " * 120)
    read = progress.read(config, entries=10)
    assert read["entries_shown"] < 10
    assert read["entries"][-1].startswith("## Session 9")  # the most recent ones are kept


def test_invalid_entry(config):
    with pytest.raises(UserError):
        progress.log(config, "   ")
    with pytest.raises(UserError):
        progress.log(config, "x" * 5000)
